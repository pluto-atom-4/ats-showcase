"""Proof-of-concept requirement extraction from job descriptions.

Orchestrates 5-phase pipeline:
1. Markdown parsing: Extract company, sections, remove boilerplate
2. Sentence classification: Sentencizer + Phase 8a patterns, confidence ≥0.50
3. Span extraction: Use Phase 8b span_categorizer for boundaries
4. Normalization: Deduplicate, filter, sort by confidence
5. JSON output: Company + requirements list + metadata

Reuses Phase 8a (requirement_filter) and Phase 8b (span_categorizer) components.
"""

import logging
import re
from typing import Any, Dict, List, Optional

import spacy
from pydantic import BaseModel, Field
from spacy.language import Language

# Side-effect imports: register the requirement_filter and span_categorizer pipes.
import src.preprocessing.requirement_filter  # noqa: F401
import src.preprocessing.span_categorizer  # noqa: F401

logger = logging.getLogger(__name__)


class RequirementModel(BaseModel):
    """Extracted requirement with metadata."""

    text: str = Field(..., description="Requirement text")
    trigger_word: str = Field(..., description="Trigger word (required, must, years of, etc.)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    span_type: str = Field(default="requirement", description="Span type (atomic/compound)")


class RequirementExtractionOutput(BaseModel):
    """JSON output schema for requirement extraction."""

    company: Optional[str] = Field(None, description="Company name (extracted from markdown)")
    requirements_count: int = Field(..., description="Number of extracted requirements")
    requirements: List[RequirementModel] = Field(default_factory=list, description="List of requirements")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Pipeline metadata (sentences analyzed, components, etc.)",
    )


class RequirementExtractor:
    """Main class for requirement extraction pipeline."""

    def __init__(
        self,
        spacy_model: str = "en_core_web_md",
        min_confidence: float = 0.50,
        max_requirements: int = 25,
    ):
        """Initialize extractor with spaCy model and configuration.

        Args:
            spacy_model: spaCy model name to load
            min_confidence: Minimum confidence threshold for requirements
            max_requirements: Maximum number of requirements to extract
        """
        self.min_confidence = min_confidence
        self.max_requirements = max_requirements
        self.spacy_model_name = spacy_model

        try:
            self.nlp: Language = spacy.load(spacy_model)
        except OSError as e:
            raise RuntimeError(f"Failed to load spaCy model '{spacy_model}': {e}") from e

        if "requirement_filter" not in self.nlp.pipe_names:
            self.nlp.add_pipe("requirement_filter", last=True)
        if "span_categorizer" not in self.nlp.pipe_names:
            self.nlp.add_pipe("span_categorizer", last=True)

        logger.info(f"Initialized RequirementExtractor with model={spacy_model}")

    def extract_company(self, markdown_text: str) -> Optional[str]:
        """Extract company name from markdown (Phase 1).

        Simple extraction from markdown h1/h2 headers or company patterns.

        Args:
            markdown_text: Markdown job description

        Returns:
            Company name or None if not found
        """
        # Pattern 1: # Company Name at start
        h1_match = re.search(r"^#\s+([^\n]+)", markdown_text, re.MULTILINE)
        if h1_match:
            return h1_match.group(1).strip()

        # Pattern 2: ## Company Name
        h2_match = re.search(r"^##\s+([^\n]+)", markdown_text, re.MULTILINE)
        if h2_match:
            return h2_match.group(1).strip()

        # Pattern 3: Company: Name pattern
        company_pattern = re.search(r"(?:company|employer):\s*([^\n]+)", markdown_text, re.IGNORECASE)
        if company_pattern:
            return company_pattern.group(1).strip()

        return None

    def classify_sentences(self, markdown_text: str) -> List[str]:
        """Classify sentences and extract requirement sentences (Phase 2).

        Uses spaCy sentencizer to split text, then Phase 8a patterns for classification.

        Args:
            markdown_text: Markdown job description

        Returns:
            List of sentences classified as containing requirements
        """
        doc = self.nlp(markdown_text)

        requirement_sentences: List[str] = []

        if doc._.requirements:  # type: ignore
            high_confidence_reqs = [
                req
                for req in doc._.requirements  # type: ignore
                if req["confidence"] >= self.min_confidence
            ]

            requirement_sentence_chars = set()
            for req in high_confidence_reqs:
                span_start, span_end = req["span"]
                requirement_sentence_chars.add((span_start, span_end))

            for sent in doc.sents:
                sentence_contains_requirement = False
                for req_start, _req_end in requirement_sentence_chars:
                    if sent.start_char <= req_start < sent.end_char:
                        sentence_contains_requirement = True
                        break

                if sentence_contains_requirement:
                    requirement_sentences.append(sent.text)

        logger.info(f"Classified {len(requirement_sentences)} sentences with requirements")
        return requirement_sentences

    def extract_spans(self, markdown_text: str) -> List[Dict[str, Any]]:
        """Extract expanded spans using Phase 8b (Phase 3).

        Uses span_categorizer to get multi-token boundaries and span types.

        Args:
            markdown_text: Markdown job description

        Returns:
            List of requirement spans with boundaries and metadata
        """
        doc = self.nlp(markdown_text)

        requirement_spans: List[Dict[str, Any]] = []

        if doc._.requirement_spans:  # type: ignore
            for span_dict in doc._.requirement_spans:  # type: ignore
                if span_dict["confidence"] >= self.min_confidence:
                    requirement_spans.append(span_dict)

        logger.info(f"Extracted {len(requirement_spans)} requirement spans")
        return requirement_spans

    def normalize(self, requirement_spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize and deduplicate requirements (Phase 4).

        Removes duplicates, filters by confidence, sorts by confidence descending,
        and applies case-insensitive deduplication.

        Args:
            requirement_spans: Raw requirement spans from Phase 8b

        Returns:
            Normalized list of unique requirements
        """
        seen: Dict[str, Dict[str, Any]] = {}

        for req in requirement_spans:
            normalized_key = req["text"].lower().strip()

            if normalized_key not in seen or req["confidence"] > seen[normalized_key]["confidence"]:
                seen[normalized_key] = req

        normalized_reqs = sorted(
            seen.values(),
            key=lambda r: r["confidence"],
            reverse=True,
        )

        normalized_reqs = normalized_reqs[: self.max_requirements]

        logger.info(f"Normalized to {len(normalized_reqs)} unique requirements")
        return normalized_reqs

    def to_json(
        self,
        normalized_reqs: List[Dict[str, Any]],
        markdown_text: str,
        sentence_count: int,
    ) -> RequirementExtractionOutput:
        """Convert to JSON output schema (Phase 5).

        Args:
            normalized_reqs: Normalized requirements
            markdown_text: Original markdown text
            sentence_count: Number of sentences analyzed

        Returns:
            RequirementExtractionOutput with JSON schema
        """
        company = self.extract_company(markdown_text)

        requirement_models = []
        for req in normalized_reqs:
            requirement_models.append(
                RequirementModel(
                    text=req["text"],
                    trigger_word=req["trigger_word"],
                    confidence=req["confidence"],
                    span_type=req.get("span_type", "requirement"),
                )
            )

        metadata = {
            "sentences_analyzed": sentence_count,
            "requirements_extracted": len(requirement_models),
            "spacy_model": self.spacy_model_name,
            "pipeline_components": ["sentencizer", "requirement_filter", "span_categorizer"],
            "min_confidence_threshold": self.min_confidence,
            "max_requirements_limit": self.max_requirements,
        }

        return RequirementExtractionOutput(
            company=company,
            requirements_count=len(requirement_models),
            requirements=requirement_models,
            metadata=metadata,
        )

    def extract(self, markdown_text: str) -> RequirementExtractionOutput:
        """Run full 5-phase extraction pipeline.

        Args:
            markdown_text: Markdown job description

        Returns:
            RequirementExtractionOutput with structured results
        """
        logger.info("Starting requirement extraction pipeline")

        company = self.extract_company(markdown_text)
        logger.info(f"Phase 1: Extracted company = {company}")

        doc = self.nlp(markdown_text)
        sentence_count = len(list(doc.sents))
        requirement_sentences = self.classify_sentences(markdown_text)
        logger.info(f"Phase 2: Classified {sentence_count} sentences, {len(requirement_sentences)} with requirements")

        requirement_spans = self.extract_spans(markdown_text)
        logger.info(f"Phase 3: Extracted {len(requirement_spans)} spans")

        normalized_reqs = self.normalize(requirement_spans)
        logger.info(f"Phase 4: Normalized to {len(normalized_reqs)} unique requirements")

        output = self.to_json(normalized_reqs, markdown_text, sentence_count)
        logger.info(f"Phase 5: Generated JSON output with {output.requirements_count} requirements")

        return output


def extract_requirements_from_markdown(
    markdown_text: str,
    min_confidence: float = 0.50,
    max_requirements: int = 25,
) -> RequirementExtractionOutput:
    """Convenience function for single-pass extraction.

    Args:
        markdown_text: Markdown job description
        min_confidence: Minimum confidence threshold
        max_requirements: Maximum requirements to return

    Returns:
        RequirementExtractionOutput with structured results
    """
    extractor = RequirementExtractor(
        min_confidence=min_confidence,
        max_requirements=max_requirements,
    )
    return extractor.extract(markdown_text)
