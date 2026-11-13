"""Standalone POC: Requirement extraction from job descriptions.

No dependencies on Phase 8a/8b components. Implements simplified pipeline:
1. Sentence splitting (spaCy sentencizer)
2. Sentence classification (hardcoded patterns + confidence scoring)
3. Span refinement (optional multi-line expansion)
4. JSON output (company + requirements list)

Uses en_core_web_sm for lightweight inference.
"""

import logging
from typing import Any, Dict, List, Optional

import spacy
from pydantic import BaseModel, Field
from spacy.language import Language

from .bullet_point_preprocessor import normalize_bullet_points
from .company_extractor import extract_company_name, extract_company_name_enhanced
from .requirement_classifier import classify_sentence_as_requirement
from .requirement_patterns import REQUIREMENT_PATTERNS

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
__all__ = [
    "extract_company_name",
    "extract_company_name_enhanced",
    "classify_sentence_as_requirement",
    "extract_requirements_b",
    "extract_requirements_standalone",
    "SimpleRequirementExtractionOutput",
]


class SimpleRequirementExtractionOutput(BaseModel):
    """Minimal output schema (company + requirements list only)."""

    company: Optional[str] = Field(None, description="Company name")
    requirements: List[str] = Field(default_factory=list, description="Extracted requirements")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Pipeline metadata (sentences analyzed, patterns matched, etc.)",
    )


def load_spacy_model(model_name: str = "en_core_web_sm") -> Language:
    """Load spaCy model, raise error if missing.

    Args:
        model_name: spaCy model to load (default: en_core_web_sm)

    Returns:
        Loaded spaCy Language object

    Raises:
        RuntimeError: If model not found
    """
    try:
        return spacy.load(model_name)
    except OSError as e:
        raise RuntimeError(
            f"spaCy model '{model_name}' not found. Install with: python -m spacy download {model_name}"
        ) from e


def split_sentences(text: str, nlp: Language) -> List[str]:
    """Split text into sentences using spaCy sentencizer.

    Args:
        text: Input text
        nlp: Loaded spaCy Language object

    Returns:
        List of sentence texts (stripped)
    """
    doc = nlp(text)
    return [sent.text.strip() for sent in doc.sents if sent.text.strip()]


def extract_requirements_standalone(
    markdown: str,
    min_confidence: float = 0.50,
    max_requirements: int = 20,
) -> SimpleRequirementExtractionOutput:
    """Full extraction pipeline (standalone, no Phase 8a/8b).

    Pipeline:
    1. Load spaCy model
    2. Split into sentences
    3. Classify each sentence as requirement
    4. Filter by confidence
    5. Deduplicate
    6. Extract company
    7. Return JSON

    Args:
        markdown: Raw markdown job description
        min_confidence: Minimum confidence threshold (default 0.50)
        max_requirements: Maximum requirements to return (default 20)

    Returns:
        SimpleRequirementExtractionOutput with company + requirements
    """
    logger.info("Starting standalone requirement extraction pipeline")

    nlp = load_spacy_model("en_core_web_md")

    normalized_markdown = normalize_bullet_points(markdown)
    logger.info("Normalized bullet points")

    sentences = split_sentences(normalized_markdown, nlp)
    logger.info(f"Split into {len(sentences)} sentences")

    candidate_requirements = []
    for sentence in sentences:
        req_info = classify_sentence_as_requirement(sentence, nlp)
        if req_info and req_info["confidence"] >= min_confidence:
            candidate_requirements.append(req_info)

    logger.info(f"Classified {len(candidate_requirements)} requirements (confidence >= {min_confidence})")

    seen_normalized: Dict[str, Dict[str, Any]] = {}
    for req in candidate_requirements:
        norm_key = req["text"].lower().strip()
        if norm_key not in seen_normalized:
            seen_normalized[norm_key] = req
        elif req["confidence"] > seen_normalized[norm_key]["confidence"]:
            seen_normalized[norm_key] = req

    unique_reqs = sorted(
        seen_normalized.values(),
        key=lambda r: r["confidence"],
        reverse=True,
    )[:max_requirements]

    logger.info(f"Deduplicated to {len(unique_reqs)} unique requirements")

    company = extract_company_name(markdown)
    logger.info(f"Extracted company: {company}")

    metadata = {
        "sentences_analyzed": len(sentences),
        "requirements_extracted": len(unique_reqs),
        "spacy_model": "en_core_web_md",
        "pipeline_components": ["sentencizer", "pattern_matching", "deduplication"],
        "min_confidence_threshold": min_confidence,
        "max_requirements_limit": max_requirements,
        "patterns_count": len(REQUIREMENT_PATTERNS),
    }

    return SimpleRequirementExtractionOutput(
        company=company,
        requirements=[r["text"] for r in unique_reqs],
        metadata=metadata,
    )


def extract_requirements_b(
    markdown_text: str,
    min_confidence: float = 0.50,
    max_requirements: int = 20,
) -> SimpleRequirementExtractionOutput:
    """Convenience function for single-pass extraction.

    Args:
        markdown_text: Markdown job description
        min_confidence: Minimum confidence threshold
        max_requirements: Maximum requirements to return

    Returns:
        SimpleRequirementExtractionOutput with structured results
    """
    return extract_requirements_standalone(markdown_text, min_confidence, max_requirements)


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m src.poc.extract_requirements_b <markdown_file>")
        sys.exit(1)

    markdown_file = sys.argv[1]
    with open(markdown_file) as f:
        markdown_text = f.read()

    result = extract_requirements_b(markdown_text)
    print(json.dumps(result.model_dump(), indent=2))
