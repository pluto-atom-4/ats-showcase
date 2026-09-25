"""Section-based requirement extraction with semantic deduplication (Issue #281 S3).

Extracts requirements from detected job description sections with section-specific
confidence adjustments and semantic deduplication.

POC-D Promotion: Production API replacing src/poc/extract_requirements_d.py.
Uses section_detector.py + section_patterns.py + requirement_patterns.py.

Defaults:
- DEFAULT_MIN_CONFIDENCE = 0.50
- DEFAULT_MAX_REQUIREMENTS = 20
- MAX_INPUT_CHARS = 200_000
- MAX_COMPARE_CHARS = 500 (dedup comparison text limit)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Mapping

import spacy
from spacy.language import Language

from src.preprocessing.requirement_patterns import classify_sentence
from src.preprocessing.section_detector import SectionDetector
from src.preprocessing.section_patterns import (
    CONFIDENCE_ADJUSTMENT_BY_SECTION,
    SECTION_DISPLAY_NAMES,
    SectionLabel,
)

logger = logging.getLogger(__name__)

__all__ = [
    "MAX_INPUT_CHARS",
    "MAX_COMPARE_CHARS",
    "DEFAULT_MIN_CONFIDENCE",
    "DEFAULT_MAX_REQUIREMENTS",
    "RequirementItem",
    "SectionedResult",
    "split_bullets",
    "extract_sectioned",
]

MAX_INPUT_CHARS: int = 200_000
MAX_COMPARE_CHARS: int = 500
DEFAULT_MIN_CONFIDENCE: float = 0.50
DEFAULT_MAX_REQUIREMENTS: int = 20

# Precompiled normalization regexes for dedup
_PARENTHETICAL_PATTERN = re.compile(r"\s*\(.*?\)\s*$")
_WORKING_WITH_PATTERN = re.compile(r"working\s+with\s+and/or\s+", re.IGNORECASE)
_WORKING_PATTERN = re.compile(r"working\s+with\s+", re.IGNORECASE)
_ADJECTIVE_PATTERN = re.compile(r"\b(deep|strong|extensive|proven|demonstrated)\s+experience\b", re.IGNORECASE)
_HANDS_ON_PATTERN = re.compile(r"\bhands-?on\s+", re.IGNORECASE)
_YEARS_PATTERN = re.compile(r"(\d+)\+?\s+years?\s+(?:of\s+)?experience\s+", re.IGNORECASE)
_WHITESPACE_PATTERN = re.compile(r"\s+")

# Module-level cached sentencizer (initialized lazily)
_SENTENCIZER: Language | None = None


def _get_sentencizer() -> Language:
    """Get or create cached spaCy blank pipeline with sentencizer."""
    global _SENTENCIZER
    if _SENTENCIZER is None:
        _SENTENCIZER = spacy.blank("en")
        _SENTENCIZER.add_pipe("sentencizer")
    return _SENTENCIZER


def _normalize_requirement_for_comparison(req: str) -> str:
    """Normalize requirement text for semantic comparison.

    Handles:
    - Parenthetical notes at end: "(Preferred)" → removed
    - Verbose alternatives: "working with and/or" → ""
    - Adjective variations: "deep experience" → "experience"
    - Hands-on prefix: "Hands-on" → removed
    - Years standardization: "2+ years" → "2+ years of experience"
    - Multiple spaces: collapsed

    Args:
        req: Requirement text (may include parentheticals, verbose forms)

    Returns:
        Normalized text for comparison
    """
    req = req.strip()

    # Remove parenthetical notes at end (e.g., "(Preferred)")
    req = _PARENTHETICAL_PATTERN.sub("", req)

    # Collapse verbose alternatives (and/or patterns)
    req = _WORKING_WITH_PATTERN.sub("", req)
    req = _WORKING_PATTERN.sub("", req)

    # Simplify adjectives before "experience"
    req = _ADJECTIVE_PATTERN.sub("experience", req)

    # Remove "hands-on" prefix
    req = _HANDS_ON_PATTERN.sub("", req)

    # Standardize years patterns
    req = _YEARS_PATTERN.sub(r"\1+ years of experience ", req)

    # Collapse multiple spaces
    req = _WHITESPACE_PATTERN.sub(" ", req).strip()

    return req


def _find_matching_requirement(
    target: str,
    candidates: list[str],
    threshold: float = 0.8,
) -> tuple[str | None, float]:
    """Find best semantic match from candidates using fuzzy matching.

    Algorithm:
    1. Normalize both target and each candidate
    2. Check for exact match (highest confidence 1.0)
    3. Use SequenceMatcher fuzzy ratio
    4. Boost ratio for substring matches (overlap_len / union_len)
    5. Weight substring boost higher for longer strings (>40 chars)
    6. Return best match if score >= threshold

    Args:
        target: Requirement text to match
        candidates: List of requirement texts to search
        threshold: Similarity threshold (0.0-1.0, default 0.8)

    Returns:
        Tuple of (best_match, similarity_score) or (None, 0.0) if no match >= threshold
    """
    normalized_target = _normalize_requirement_for_comparison(target)

    best_match: str | None = None
    best_score: float = 0.0

    for candidate in candidates:
        normalized_candidate = _normalize_requirement_for_comparison(candidate)

        # Check for exact match after normalization (highest confidence)
        if normalized_target.lower() == normalized_candidate.lower():
            return (candidate, 1.0)

        # Fuzzy string matching using SequenceMatcher
        target_lower = normalized_target.lower()
        candidate_lower = normalized_candidate.lower()

        # Base fuzzy ratio
        ratio = SequenceMatcher(None, target_lower, candidate_lower).ratio()

        # Boost score for substring matches
        if target_lower in candidate_lower or candidate_lower in target_lower:
            # Scale based on length overlap
            overlap_len = min(len(target_lower), len(candidate_lower))
            union_len = max(len(target_lower), len(candidate_lower))
            substring_score = overlap_len / union_len if union_len > 0 else 0

            # Weight substring match higher if both are long (more specific)
            if min(len(target_lower), len(candidate_lower)) > 40:
                ratio = max(ratio, substring_score * 1.1)
            else:
                ratio = max(ratio, substring_score)

        if ratio > best_score:
            best_score = ratio
            best_match = candidate

    if best_score >= threshold:
        return (best_match, best_score)

    return (None, 0.0)


def _clamp_confidence(value: float) -> float:
    """Clamp confidence value to [0.0, 1.0] range.

    Args:
        value: Confidence value (may exceed [0.0, 1.0] after adjustments)

    Returns:
        Confidence value clamped to [0.0, 1.0]
    """
    return max(0.0, min(1.0, value))


def _is_bullet_line(stripped: str) -> bool:
    """Check if a line starts with a bullet marker.

    Args:
        stripped: Left-stripped line text

    Returns:
        True if line has bullet marker, False otherwise
    """
    bullet_match = re.match(r"^[*\-•]\s+(.+)", stripped)
    numbered_match = re.match(r"^\d+[.)]\s+(.+)", stripped)
    return bool(bullet_match or numbered_match)


def _get_bullet_content(stripped: str) -> str | None:
    """Extract content after bullet marker.

    Args:
        stripped: Left-stripped line text

    Returns:
        Content after marker, or None if not a bullet line
    """
    bullet_match = re.match(r"^[*\-•]\s+(.+)", stripped)
    if bullet_match:
        return bullet_match.group(1)
    numbered_match = re.match(r"^\d+[.)]\s+(.+)", stripped)
    if numbered_match:
        return numbered_match.group(1)
    return None


def _save_current_item(current_item: list[str], bullets: list[str]) -> None:
    """Save current item to bullets list if non-empty.

    Args:
        current_item: Lines of current item
        bullets: Accumulator list
    """
    if current_item:
        item_text = " ".join(current_item).strip()
        if item_text:
            bullets.append(item_text)


def _process_bullet_line(stripped: str, current_item: list[str], bullets: list[str]) -> None:
    """Process a bullet marker line.

    Args:
        stripped: Left-stripped line
        current_item: Current item accumulator (modified)
        bullets: Bullets accumulator (modified)
    """
    _save_current_item(current_item, bullets)
    current_item.clear()
    bullet_content = _get_bullet_content(stripped)
    if bullet_content:
        current_item.append(bullet_content)


def _process_continuation_line(stripped: str, current_item: list[str]) -> None:
    """Process indented continuation line.

    Args:
        stripped: Left-stripped line
        current_item: Current item accumulator (modified)
    """
    if current_item:
        current_item.append(stripped)


def _process_non_bullet_line(current_item: list[str], bullets: list[str]) -> None:
    """Process non-indented non-bullet line.

    Args:
        current_item: Current item accumulator (modified)
        bullets: Bullets accumulator (modified)
    """
    _save_current_item(current_item, bullets)
    current_item.clear()


@dataclass(frozen=True)
class RequirementItem:
    """A single requirement with full metadata.

    Attributes:
        text: Requirement text
        trigger_word: Trigger word from pattern (required, must, years of, etc.)
        base_confidence: Base confidence from pattern matching
        section_boost: Section-specific confidence adjustment
        final_confidence: Final confidence (base + boost, clamped to [0.0, 1.0])
        source_section: Source section label (SectionLabel enum value)
        section_display_name: Human-readable section name
    """

    text: str
    trigger_word: str
    base_confidence: float
    section_boost: float
    final_confidence: float
    source_section: SectionLabel
    section_display_name: str

    def to_legacy_tuple(self) -> tuple[str, str, float]:
        """Return (text, trigger_word, final_confidence) for backward compatibility."""
        return (self.text, self.trigger_word, self.final_confidence)

    def to_json(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "text": self.text,
            "trigger_word": self.trigger_word,
            "base_confidence": self.base_confidence,
            "section_boost": self.section_boost,
            "final_confidence": self.final_confidence,
            "source_section": self.source_section.value,
            "section_display_name": self.section_display_name,
        }


@dataclass(frozen=True)
class SectionedResult:
    """Structured output from extract_sectioned().

    Attributes:
        requirements: Tuple of RequirementItem objects, sorted by final_confidence descending
        sections_detected: Tuple of detected section label values in detected order
        requirements_by_section: Dict mapping section label (str) to count of requirements
        schema_version: Schema version for this output (default "3.0")
        metadata: Additional metadata (pipeline version, parameters, etc.)
    """

    requirements: tuple[RequirementItem, ...]
    sections_detected: tuple[str, ...]
    requirements_by_section: dict[str, int]
    schema_version: str = "3.0"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "requirements": [r.to_json() for r in self.requirements],
            "sections_detected": list(self.sections_detected),
            "requirements_by_section": self.requirements_by_section,
            "schema_version": self.schema_version,
            "metadata": self.metadata or {},
        }


def split_bullets(text: str) -> list[str]:
    """Split section content into items by bullet markers.

    Handles:
    - -, *, • (unordered bullets)
    - digits + "." or ")" (numbered)

    Continuation lines (indented) join the previous item.
    Non-bullet paragraphs stay as lines; empties are dropped.

    Args:
        text: Section content (may include bullets and paragraphs)

    Returns:
        List of bullet items (markers stripped, non-bullet lines preserved)
    """
    bullets: list[str] = []
    lines = text.split("\n")
    current_item: list[str] = []

    for line in lines:
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        if _is_bullet_line(stripped):
            _process_bullet_line(stripped, current_item, bullets)
        elif stripped and indent > 0:
            _process_continuation_line(stripped, current_item)
        elif stripped and indent == 0:
            _process_non_bullet_line(current_item, bullets)
        elif not stripped and current_item:
            current_item.append("")

    _save_current_item(current_item, bullets)
    return bullets


def _classify_sentence_to_dict(
    sentence_text: str,
    section_label: SectionLabel,
    confidence_adjustments: Mapping[SectionLabel, float],
    display_names: Mapping[SectionLabel, str],
) -> dict[str, Any] | None:
    """Classify sentence and build requirement dict.

    Args:
        sentence_text: Sentence to classify
        section_label: Source section
        confidence_adjustments: Section boost mapping
        display_names: Display name mapping

    Returns:
        Requirement dict or None if classification fails
    """
    sentence_match = classify_sentence(sentence_text)
    if not sentence_match:
        return None

    base_confidence = sentence_match.confidence
    trigger_word = sentence_match.trigger_word
    section_boost = confidence_adjustments.get(section_label, 0.0)
    final_confidence = _clamp_confidence(base_confidence + section_boost)
    section_display_name = display_names.get(section_label, section_label.value)

    return {
        "text": sentence_text,
        "trigger_word": trigger_word,
        "base_confidence": base_confidence,
        "section_boost": section_boost,
        "final_confidence": final_confidence,
        "source_section": section_label,
        "section_display_name": section_display_name,
    }


def _process_item_sentences(
    item: str,
    section_label: SectionLabel,
    confidence_adjustments: Mapping[SectionLabel, float],
    display_names: Mapping[SectionLabel, str],
    sentencizer: Language,
    min_confidence: float,
) -> list[dict[str, Any]]:
    """Process sentences from item and return filtered candidates.

    Args:
        item: Bullet item text
        section_label: Source section
        confidence_adjustments: Section boost mapping
        display_names: Display name mapping
        sentencizer: spaCy sentencizer
        min_confidence: Min confidence threshold

    Returns:
        List of requirement dicts passing confidence threshold
    """
    if not item.strip():
        return []

    doc = sentencizer(item)
    candidates = []

    for sent in doc.sents:
        sentence_text = sent.text.strip()
        if not sentence_text:
            continue

        req_dict = _classify_sentence_to_dict(sentence_text, section_label, confidence_adjustments, display_names)
        if req_dict and req_dict["final_confidence"] >= min_confidence:
            candidates.append(req_dict)

    return candidates


def _dedup_and_replace(
    unique_reqs: list[dict[str, Any]],
    req_texts: list[str],
    req: dict[str, Any],
    dedup_threshold: float,
) -> None:
    """Check dedup and replace if higher confidence found.

    Args:
        unique_reqs: Deduped requirements (modified)
        req_texts: Deduped requirement texts (modified)
        req: Candidate requirement
        dedup_threshold: Similarity threshold
    """
    req_text = req["text"]
    matched_text, score = _find_matching_requirement(req_text, req_texts, threshold=dedup_threshold)

    if score < dedup_threshold:
        unique_reqs.append(req)
        req_texts.append(req_text)
    elif matched_text is not None:
        for idx, existing in enumerate(unique_reqs):
            if existing["text"] == matched_text:
                if req["final_confidence"] > existing["final_confidence"]:
                    unique_reqs[idx] = req
                    req_texts[req_texts.index(matched_text)] = req_text
                break


def _dedup_candidates(
    candidate_requirements: list[dict[str, Any]],
    dedup_threshold: float,
) -> list[dict[str, Any]]:
    """Deduplicate candidates semantically.

    Args:
        candidate_requirements: Candidate requirements
        dedup_threshold: Fuzzy dedup threshold

    Returns:
        Deduplicated unique requirements
    """
    unique_reqs: list[dict[str, Any]] = []
    req_texts: list[str] = []

    for req in sorted(candidate_requirements, key=lambda r: len(r["text"]), reverse=True):
        _dedup_and_replace(unique_reqs, req_texts, req, dedup_threshold)

    return unique_reqs


def _build_result(
    target: Any,
    unique_reqs: list[dict[str, Any]],
    min_confidence: float,
    max_requirements: int,
    dedup_threshold: float,
) -> SectionedResult:
    """Build final SectionedResult from deduped requirements.

    Args:
        target: Target sections
        unique_reqs: Deduped requirement dicts
        min_confidence: Min confidence threshold
        max_requirements: Max requirements limit
        dedup_threshold: Dedup threshold

    Returns:
        SectionedResult
    """
    # Cap at max_requirements
    unique_reqs = unique_reqs[:max_requirements]

    # Count by section
    requirements_by_section: dict[str, int] = {}
    for req in unique_reqs:
        section = req["source_section"].value
        requirements_by_section[section] = requirements_by_section.get(section, 0) + 1

    # Build items
    requirement_items = tuple(
        RequirementItem(
            text=r["text"],
            trigger_word=r["trigger_word"],
            base_confidence=r["base_confidence"],
            section_boost=r["section_boost"],
            final_confidence=r["final_confidence"],
            source_section=r["source_section"],
            section_display_name=r["section_display_name"],
        )
        for r in unique_reqs
    )

    # Build metadata
    metadata: dict[str, Any] = {
        "sections_detected": len(target),
        "requirements_extracted": len(requirement_items),
        "min_confidence": min_confidence,
        "max_requirements": max_requirements,
        "dedup_threshold": dedup_threshold,
        "dedup_algorithm": "semantic_fuzzy",
    }

    sections_detected_tuple = tuple(s.label.value for s in target)
    return SectionedResult(
        requirements=requirement_items,
        sections_detected=sections_detected_tuple,
        requirements_by_section=requirements_by_section,
        metadata=metadata,
    )


def _validate_and_detect(text: str, detector: SectionDetector | None) -> tuple[str, Any] | None:
    """Validate input and detect sections or return empty result.

    Args:
        text: Input text
        detector: Section detector

    Returns:
        Tuple of (text, detector) or None (early return with empty result)
    """
    if not text or not text.strip():
        return None

    if len(text) > MAX_INPUT_CHARS:
        logger.warning(f"Input text ({len(text)} chars) exceeds MAX_INPUT_CHARS; truncating.")
        text = text[:MAX_INPUT_CHARS]

    if detector is None:
        detector = SectionDetector()

    return (text, detector)


def extract_sectioned(
    text: str,
    *,
    detector: SectionDetector | None = None,
    confidence_adjustments: Mapping[SectionLabel, float] | None = None,
    display_names: Mapping[SectionLabel, str] | None = None,
    dedup_threshold: float = 0.8,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    max_requirements: int = DEFAULT_MAX_REQUIREMENTS,
) -> SectionedResult:
    """Extract sectioned requirements from job description text.

    Flow:
    1. Validate input (empty/whitespace → empty result)
    2. Create detector if not provided
    3. Detect sections
    4. Filter to target sections
    5. Split bullets; sentence-split each item
    6. Classify sentences with section boost
    7. Filter by min_confidence
    8. Deduplicate semantically
    9. Sort by final_confidence descending
    10. Cap at max_requirements
    11. Build metadata; return SectionedResult

    Args:
        text: Job description text
        detector: SectionDetector instance (default: new SectionDetector())
        confidence_adjustments: Section → boost mapping (default: CONFIDENCE_ADJUSTMENT_BY_SECTION)
        display_names: Section → human name mapping (default: SECTION_DISPLAY_NAMES)
        dedup_threshold: Fuzzy dedup threshold (default 0.8)
        min_confidence: Minimum final confidence (default 0.50)
        max_requirements: Maximum requirements to return (default 20)

    Returns:
        SectionedResult with requirements, sections_detected, and metadata
    """
    # Validate and detect
    validation_result = _validate_and_detect(text, detector)
    if validation_result is None:
        return SectionedResult(
            requirements=(),
            sections_detected=(),
            requirements_by_section={},
            metadata={"input_empty": True},
        )

    text, detector = validation_result

    # Set defaults
    if confidence_adjustments is None:
        confidence_adjustments = CONFIDENCE_ADJUSTMENT_BY_SECTION
    if display_names is None:
        display_names = SECTION_DISPLAY_NAMES

    # Detect sections
    detected = detector.detect(text)
    if not detected:
        return SectionedResult(
            requirements=(),
            sections_detected=(),
            requirements_by_section={},
            metadata={"sections_detected": 0},
        )

    target = detector.target_sections(detected)
    if not target:
        return SectionedResult(
            requirements=(),
            sections_detected=tuple(s.label.value for s in detected),
            requirements_by_section={},
            metadata={"target_sections": 0},
        )

    # Process sections
    candidate_requirements: list[dict[str, Any]] = []
    sentencizer = _get_sentencizer()

    for section in target:
        content_text = section.content_text
        if not content_text.strip():
            continue

        items = split_bullets(content_text)
        for item in items:
            section_candidates = _process_item_sentences(
                item,
                section.label,
                confidence_adjustments,
                display_names,
                sentencizer,
                min_confidence,
            )
            candidate_requirements.extend(section_candidates)

    # Deduplicate and finalize
    unique_reqs = _dedup_candidates(candidate_requirements, dedup_threshold)
    unique_reqs = sorted(
        unique_reqs,
        key=lambda r: r["final_confidence"],
        reverse=True,
    )

    return _build_result(target, unique_reqs, min_confidence, max_requirements, dedup_threshold)
