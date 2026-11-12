"""Proof-of-concept requirement extraction (POC-C) using section detection.

POC-C Pipeline (3-Stage Section-Aware Extraction):
1. Section Detection: Use spaCy SpanRuler to identify target sections
   (REQUIREMENTS, QUALIFICATIONS, TECHNICAL_SKILLS, NICE_TO_HAVE, EDUCATION)
   and filter sections (BENEFITS, COMPENSATION, HIRING_PROCESS)

2. Target Extraction: Extract requirements from detected sections using
   Phase 8a trigger patterns (20 patterns, Tier 1-3)

3. Classification & Boost: Apply section-specific confidence adjustments
   (+0.15 for REQUIREMENTS sections, -0.50 for BENEFITS, etc.)

Output: RequirementWithSection + SimpleRequirementExtractionOutputWithSections
(full metadata including source section, section display name, section boost)

Reuses from existing POC-B (Phase 2+ implementation):
- REQUIREMENT_PATTERNS (20 patterns, Phase 8a) - from extract_requirements_b.py
- classify_sentence_as_requirement() - from extract_requirements_b.py
- extract_company_name_enhanced() - from extract_requirements_b.py
- normalize_bullet_points() - from bullet_point_preprocessor.py

Architecture goal: Simpler than Phase 8a/8b pipeline while providing section-aware
confidence boosting for higher precision extraction.

Issue #265: Refactored to use parameterized patterns (src.poc.patterns module).
Enables testing with different pattern configurations.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import spacy
from pydantic import BaseModel, Field
from spacy.language import Language
from spacy.tokens import Doc

from .bullet_point_preprocessor import (
    contains_bullets,
    normalize_markdown_artifacts_complete,
    split_by_bullet_markers,
)
from .company_extractor import extract_company_name_enhanced
from .extract_requirements_b import classify_sentence_as_requirement
from .patterns import (
    CONFIDENCE_ADJUSTMENT_BY_SECTION as DEFAULT_ADJUSTMENTS,
)
from .patterns import (
    DEFAULT_TARGET_SECTIONS,
)
from .patterns import (
    SECTION_DISPLAY_NAMES as DEFAULT_DISPLAY_NAMES,
)

# Pattern imports (Issue #265: modular pattern definitions)
from .patterns import (
    SECTION_RULER_PATTERNS as DEFAULT_SECTION_PATTERNS,
)
from .requirement_patterns import REQUIREMENT_PATTERNS

logger = logging.getLogger(__name__)


class RequirementWithSection(BaseModel):
    """Requirement with section-aware metadata."""

    text: str = Field(..., description="Requirement text")
    trigger_word: str = Field(..., description="Trigger word (required, must, years of, etc.)")
    base_confidence: float = Field(..., ge=0.0, le=1.0, description="Base confidence from pattern matching")
    section_boost: float = Field(..., ge=-0.5, le=0.5, description="Section-specific confidence adjustment")
    final_confidence: float = Field(..., ge=0.0, le=1.0, description="Final confidence (base + boost, clamped)")
    source_section: str = Field(..., description="Source section label (SECTION_REQUIREMENTS, etc.)")
    section_display_name: str = Field(..., description="Human-readable section name")


class SimpleRequirementExtractionOutputWithSections(BaseModel):
    """JSON output schema for POC-C section-aware extraction."""

    company: Optional[str] = Field(None, description="Company name (extracted from markdown)")
    requirements: List[str] = Field(
        default_factory=list,
        description="Simple list of requirement texts (backward compatible with POC-B)",
    )
    requirements_detailed: List[RequirementWithSection] = Field(
        default_factory=list,
        description="Full requirement metadata including section source and confidence breakdown",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Pipeline metadata: sections_detected (dict), requirements_by_section (dict), "
            "spacy_model, pipeline_components, min_confidence_threshold, "
            "max_requirements_limit, patterns_count"
        ),
    )


def _initialize_doc_extensions() -> None:
    """Register custom doc extensions for section metadata.

    Called once at module load time to add:
    - doc._.detected_sections: List[Dict] with section labels, text, start, end
    - doc._.section_labels: Set[str] of unique section labels found
    """
    if not Doc.has_extension("detected_sections"):
        Doc.set_extension("detected_sections", default=[])
    if not Doc.has_extension("section_labels"):
        Doc.set_extension("section_labels", default=set())


_initialize_doc_extensions()


def _clamp_confidence(value: float) -> float:
    """Clamp confidence value to [0.0, 1.0] range.

    Args:
        value: Confidence value (may exceed [0.0, 1.0] after adjustments)

    Returns:
        Confidence value clamped to [0.0, 1.0]
    """
    return max(0.0, min(1.0, value))


def load_spacy_model(
    model_name: str = "en_core_web_md",
    patterns: Optional[List[Dict[str, Any]]] = None,
) -> Language:
    """Load spaCy model, add section_ruler pipe, and configure for section detection.

    Args:
        model_name: spaCy model to load (default: en_core_web_sm)
        patterns: Custom SpanRuler patterns (default: from patterns.py)

    Returns:
        Loaded and configured spaCy Language object with section_ruler

    Raises:
        RuntimeError: If model not found or fails to load
    """
    logger.debug(f"Loading spaCy model: {model_name}")

    try:
        nlp = spacy.load(model_name)
        logger.debug(f"Successfully loaded model: {model_name}")
    except OSError as e:
        msg = f"Failed to load spaCy model '{model_name}'. Install with: python -m spacy download {model_name}"
        logger.error(msg)
        raise RuntimeError(msg) from e

    if patterns is None:
        patterns = DEFAULT_SECTION_PATTERNS

    if "span_ruler" not in nlp.pipe_names:
        logger.debug("Adding span_ruler to pipeline")
        ruler = nlp.add_pipe("span_ruler")
        ruler.add_patterns(patterns)  # type: ignore
        logger.debug(f"Configured span_ruler with {len(patterns)} patterns")
    else:
        logger.debug("span_ruler already present in pipeline")

    logger.info(f"Model loaded and configured. Pipeline: {nlp.pipe_names}")
    return nlp


def detect_sections(
    nlp: Language,
    text: str,
    display_names: Optional[Dict[str, str]] = None,
) -> Doc:
    """Detect target/filter sections in text using SpanRuler.

    Processes text through spaCy pipeline (including SpanRuler), then:
    - Extracts section spans from doc.spans["ruler"]
    - Attaches metadata to doc:
      - doc._.detected_sections: List[Dict] with label, text, start, end
      - doc._.section_labels: Set[str] of unique labels

    Args:
        nlp: Loaded spaCy Language object with section_ruler pipe
        text: Job description text (plain text or markdown)
        display_names: Custom section display names (default: from patterns.py)

    Returns:
        spaCy Doc with detected sections attached as metadata

    Raises:
        ValueError: If text is empty or None
    """
    if not text or not text.strip():
        logger.warning("detect_sections: empty or None text provided")
        return nlp("")

    logger.debug(f"detect_sections: processing {len(text)} characters")

    if display_names is None:
        display_names = DEFAULT_DISPLAY_NAMES

    doc = nlp(text)

    # Extract section spans from SpanRuler output
    detected_sections = []
    section_labels = set()

    if "ruler" in doc.spans:
        for span in doc.spans["ruler"]:
            section_dict = {
                "label": span.label_,
                "text": span.text,
                "start": span.start,
                "end": span.end,
                "display_name": display_names.get(span.label_, span.label_),
            }
            detected_sections.append(section_dict)
            section_labels.add(span.label_)
            logger.debug(f"Detected section: {span.label_} at tokens {span.start}-{span.end}")
    else:
        logger.debug("No 'ruler' span key found in doc.spans")

    # Attach metadata to doc
    doc._.detected_sections = detected_sections
    doc._.section_labels = section_labels

    logger.info(f"Detected {len(detected_sections)} sections: {sorted(section_labels) if section_labels else 'none'}")

    return doc


def extract_target_section_content(
    doc: Doc,
    target_sections: Optional[List[str]] = None,
    split_by_bullets: bool = True,
) -> List[Tuple[str, str, int]]:
    """Extract text content from target sections only.

    Iterates through doc._.detected_sections, filters by target_sections,
    and extracts text from each section to the next section boundary or end of doc.

    If split_by_bullets=True and section text contains bullet markers, splits
    each bullet into a separate tuple for granular requirement extraction.

    Args:
        doc: spaCy Doc with detected sections (from detect_sections)
        target_sections: Sections to extract from (default: DEFAULT_TARGET_SECTIONS)
                        Filter sections (BENEFITS, COMPENSATION, etc.) automatically excluded
        split_by_bullets: If True, split bullet-point sections into individual items (default: True)

    Returns:
        List of tuples: (text, section_label, section_index)
        where text is extracted content (single bullet or full section),
        section_label is SECTION_*, section_index is position in detected_sections

    Raises:
        ValueError: If doc has no detected_sections metadata
    """
    if target_sections is None:
        target_sections = DEFAULT_TARGET_SECTIONS

    logger.debug(f"Extracting from target sections: {target_sections}")

    if not hasattr(doc._, "detected_sections") or not doc._.detected_sections:
        logger.warning("No detected_sections found in doc. Returning empty list.")
        return []

    extracted_content = []

    # Sorted by start so the next section's start is this section's content_end.
    sorted_sections = sorted(doc._.detected_sections, key=lambda s: s["start"])

    # A section contained within another is skipped; the containing one keeps the content.
    non_overlapping_sections = []
    for section in sorted_sections:
        is_contained = False
        for other in sorted_sections:
            if other is section:
                continue
            if other["start"] <= section["start"] and section["end"] <= other["end"]:
                if other["start"] != section["start"] or other["end"] != section["end"]:
                    is_contained = True
                    logger.debug(f"Skipping contained section {section['label']} within {other['label']}")
                    break
        if not is_contained:
            non_overlapping_sections.append(section)

    sorted_sections = non_overlapping_sections

    for idx, section in enumerate(sorted_sections):
        section_label = section["label"]

        if section_label not in target_sections:
            logger.debug(f"Skipping filter section: {section_label}")
            continue

        content_start = section["end"]  # Start AFTER the section header

        if idx + 1 < len(sorted_sections):
            content_end = sorted_sections[idx + 1]["start"]
        else:
            content_end = len(doc)

        if content_start < content_end:
            content_tokens = doc[content_start:content_end]
            content_text = content_tokens.text.strip()

            if content_text:
                if split_by_bullets and contains_bullets(content_text):
                    logger.debug(f"Section {section_label} contains bullets, splitting...")
                    bullets = split_by_bullet_markers(content_text)
                    for bullet_idx, bullet in enumerate(bullets):
                        if bullet.strip():
                            extracted_content.append((bullet.strip(), section_label, idx))
                            logger.debug(f"Added bullet {bullet_idx + 1} from {section_label}: {bullet[:60]}...")
                else:
                    extracted_content.append((content_text, section_label, idx))
                    logger.debug(
                        f"Extracted {len(content_text)} chars from {section_label} "
                        f"(tokens {content_start}-{content_end})"
                    )
        else:
            logger.debug(f"Empty content for section {section_label}")

    if not extracted_content:
        logger.warning("No target section content extracted")
    else:
        logger.info(f"Extracted text from {len(extracted_content)} target sections")

    return extracted_content


def classify_sentence_with_section_boost(
    sentence: str,
    section_label: str,
    nlp: Language,
    adjustments: Optional[Dict[str, float]] = None,
    display_names: Optional[Dict[str, str]] = None,
) -> Optional[Dict[str, Any]]:
    """Classify sentence with section-specific confidence boost.

    Reuses classify_sentence_as_requirement() from POC-B, applies
    section-specific confidence adjustment from confidence adjustments dict.

    Pipeline:
    1. Call classify_sentence_as_requirement() from POC-B
    2. If no requirement detected, return None
    3. Extract base_confidence from POC-B result
    4. Look up section_boost from adjustments dict
    5. Calculate final_confidence = clamp(base + boost, 0.0, 1.0)
    6. Look up section_display_name from display_names dict
    7. Return enriched dict with section metadata

    Args:
        sentence: Single sentence text
        section_label: Section label (SECTION_REQUIREMENTS, etc.)
        nlp: Loaded spaCy Language object (for API consistency; used in POC-B call)
        adjustments: Custom confidence adjustments (default: from patterns.py)
        display_names: Custom section display names (default: from patterns.py)

    Returns:
        Dict with keys:
          - text: Sentence text
          - trigger_word: Trigger word from pattern (required, must, years of, etc.)
          - base_confidence: Base confidence from POC-B pattern matching
          - section_boost: Section-specific adjustment
          - final_confidence: Final confidence (base + boost, clamped to [0.0, 1.0])
          - source_section: Section label (SECTION_REQUIREMENTS, etc.)
          - section_display_name: Human-readable section name
        or None if no requirement detected by POC-B patterns

    Raises:
        ValueError: If section_label is invalid (logs warning and uses default boost 0.0)
    """
    if not sentence or not sentence.strip():
        return None

    if adjustments is None:
        adjustments = DEFAULT_ADJUSTMENTS
    if display_names is None:
        display_names = DEFAULT_DISPLAY_NAMES

    poc_b_result = classify_sentence_as_requirement(sentence, nlp)

    if poc_b_result is None:
        logger.debug(f"No requirement detected in sentence: {sentence[:60]}...")
        return None

    base_confidence = poc_b_result.get("confidence", 0.0)
    trigger_word = poc_b_result.get("trigger_word", "unknown")

    if section_label not in adjustments:
        logger.warning(
            f"Unknown section_label '{section_label}', using default boost 0.0. "
            f"Valid sections: {list(adjustments.keys())}"
        )
        section_boost = 0.0
    else:
        section_boost = adjustments[section_label]

    final_confidence = _clamp_confidence(base_confidence + section_boost)

    section_display_name = display_names.get(section_label, section_label)

    result = {
        "text": sentence,
        "trigger_word": trigger_word,
        "base_confidence": base_confidence,
        "section_boost": section_boost,
        "final_confidence": final_confidence,
        "source_section": section_label,
        "section_display_name": section_display_name,
    }

    logger.debug(
        f"Classified sentence with boost: [{trigger_word}] "
        f"base={base_confidence:.2f} boost={section_boost:+.2f} final={final_confidence:.2f}"
    )

    return result


def extract_requirements_c(
    markdown: str,
    min_confidence: float = 0.50,
    max_requirements: int = 20,
    target_sections: Optional[List[str]] = None,
    patterns: Optional[List[Dict[str, Any]]] = None,
    adjustments: Optional[Dict[str, float]] = None,
    display_names: Optional[Dict[str, str]] = None,
) -> SimpleRequirementExtractionOutputWithSections:
    """Full extraction pipeline (POC-C: section-aware).

    Pipeline:
    1. Load spaCy model + SpanRuler
    2. Detect sections (REQUIREMENTS, QUALIFICATIONS, etc.)
    3. Extract content from target sections
    4. Classify sentences with section boost
    5. Deduplicate and filter
    6. Extract company
    7. Return JSON with section metadata

    Args:
        markdown: Raw markdown job description
        min_confidence: Minimum final confidence threshold (default 0.50)
        max_requirements: Maximum requirements to return (default 20)
        target_sections: Sections to extract from (default: DEFAULT_TARGET_SECTIONS)
        patterns: Custom SpanRuler patterns (default: from patterns.py)
        adjustments: Custom confidence adjustments (default: from patterns.py)
        display_names: Custom section display names (default: from patterns.py)

    Returns:
        SimpleRequirementExtractionOutputWithSections with requirements + metadata

    (Implementation: Phase 4 - Full Pipeline)
    """
    logger.info("Phase 4: Starting POC-C extraction pipeline")
    logger.debug(f"Parameters: min_confidence={min_confidence}, max_requirements={max_requirements}")

    if patterns is None:
        patterns = DEFAULT_SECTION_PATTERNS
    if adjustments is None:
        adjustments = DEFAULT_ADJUSTMENTS
    if display_names is None:
        display_names = DEFAULT_DISPLAY_NAMES
    if target_sections is None:
        target_sections = DEFAULT_TARGET_SECTIONS

    nlp = load_spacy_model("en_core_web_md", patterns=patterns)
    logger.debug(f"Loaded spaCy model: {nlp.meta.get('name', 'unknown')}")

    cleaned_markdown = normalize_markdown_artifacts_complete(markdown)
    logger.debug("Cleaned markdown artifacts and unicode characters")
    # Skip normalize_bullet_points() so bullet markers survive for Phase B bullet splitting.
    normalized_markdown = cleaned_markdown

    doc = detect_sections(nlp, normalized_markdown, display_names=display_names)
    logger.debug(f"Detected sections: {sorted(doc._.section_labels) if doc._.section_labels else 'none'}")

    extracted_sections = extract_target_section_content(doc, target_sections, split_by_bullets=True)
    logger.info(f"Extracted text from {len(extracted_sections)} target sections/bullets")

    candidate_requirements: List[Dict[str, Any]] = []

    for section_text, section_label, section_index in extracted_sections:
        logger.debug(f"Processing section {section_index} ({section_label}): {len(section_text)} chars")

        section_doc = nlp(section_text)
        sentences = list(section_doc.sents)
        logger.debug(f"Split into {len(sentences)} sentences")

        for sent in sentences:
            sentence_text = sent.text.strip()
            if not sentence_text:
                continue

            result = classify_sentence_with_section_boost(
                sentence_text, section_label, nlp, adjustments=adjustments, display_names=display_names
            )

            if result and result.get("final_confidence", 0.0) >= min_confidence:
                candidate_requirements.append(result)
                logger.debug(
                    f"Added requirement: confidence={result['final_confidence']:.2f}, "
                    f"trigger={result['trigger_word']}, section={section_label}"
                )

    logger.info(f"Classified {len(candidate_requirements)} requirements (confidence >= {min_confidence})")

    dedup_dict: Dict[str, Dict[str, Any]] = {}

    for req in candidate_requirements:
        normalized_key = req["text"].lower().strip()

        if normalized_key not in dedup_dict:
            dedup_dict[normalized_key] = req
        else:
            if req["final_confidence"] > dedup_dict[normalized_key]["final_confidence"]:
                dedup_dict[normalized_key] = req

    unique_reqs = sorted(
        dedup_dict.values(),
        key=lambda r: r["final_confidence"],
        reverse=True,
    )

    unique_reqs = unique_reqs[:max_requirements]

    logger.info(f"Deduplicated to {len(unique_reqs)} unique requirements")

    company = extract_company_name_enhanced(markdown)
    logger.info(f"Extracted company: {company if company else 'unknown'}")

    sections_detected: Dict[str, int] = {}
    for section in doc._.detected_sections:
        label = section["label"]
        sections_detected[label] = sections_detected.get(label, 0) + 1

    requirements_by_section: Dict[str, int] = {}
    for req in unique_reqs:
        section = req["source_section"]
        requirements_by_section[section] = requirements_by_section.get(section, 0) + 1

    sentences_analyzed = 0
    for section_text, _, _ in extracted_sections:
        section_doc = nlp(section_text)
        sentences_analyzed += len(list(section_doc.sents))

    metadata: Dict[str, Any] = {
        "sections_detected": sections_detected,
        "requirements_by_section": requirements_by_section,
        "total_sections": len(doc._.section_labels),
        "target_sections_used": len(extracted_sections),
        "sentences_analyzed": sentences_analyzed,
        "requirements_extracted": len(unique_reqs),
        "spacy_model": nlp.meta.get("name", "unknown"),
        "pipeline_components": nlp.pipe_names,
        "min_confidence_threshold": min_confidence,
        "max_requirements_limit": max_requirements,
        "patterns_count": len(REQUIREMENT_PATTERNS),
    }

    logger.debug(f"Built metadata: {len(metadata)} fields")

    requirements_simple = [r["text"] for r in unique_reqs]

    requirements_detailed = [
        RequirementWithSection(
            text=r["text"],
            trigger_word=r["trigger_word"],
            base_confidence=r["base_confidence"],
            section_boost=r["section_boost"],
            final_confidence=r["final_confidence"],
            source_section=r["source_section"],
            section_display_name=r["section_display_name"],
        )
        for r in unique_reqs
    ]

    output = SimpleRequirementExtractionOutputWithSections(
        company=company,
        requirements=requirements_simple,
        requirements_detailed=requirements_detailed,
        metadata=metadata,
    )

    logger.info(
        f"Phase 4 complete: {len(output.requirements)} requirements, "
        f"company={company}, confidence_range=[{min_confidence}, 1.0]"
    )

    return output


def extract_requirements(
    markdown_text: str,
    min_confidence: float = 0.50,
    max_requirements: int = 20,
) -> SimpleRequirementExtractionOutputWithSections:
    """Convenience function for single-pass extraction (POC-C).

    Args:
        markdown_text: Markdown job description
        min_confidence: Minimum confidence threshold
        max_requirements: Maximum requirements to return

    Returns:
        SimpleRequirementExtractionOutputWithSections with structured results
    """
    return extract_requirements_c(markdown_text, min_confidence, max_requirements)


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m src.poc.extract_requirements_c <markdown_file>")
        sys.exit(1)

    markdown_file = sys.argv[1]
    with open(markdown_file) as f:
        markdown_text = f.read()

    result = extract_requirements_c(markdown_text)
    print(json.dumps(result.model_dump(), indent=2))
