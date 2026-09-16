"""Tests for RequirementProcessor confidence threshold gating (Issue #346).

Verifies min_confidence gating on classification.all_types[0] for QUALIFICATIONS
sections, with backward-compatible fallback to labels-only filtering when
all_types is empty/absent.

Coverage:
- High-confidence QUALIFICATIONS section (all_types[0].confidence >= threshold)
  -> requirements extracted
- Low-confidence QUALIFICATIONS section (all_types[0].confidence < threshold)
  -> extraction skipped
- min_confidence=0 -> extracts everything (regression guard)
- all_types empty/absent -> falls back to labels-only behavior (no regression)

Run with:
    uv run pytest tests/poc/tweak/spacy_pipeline/test_requirement_processor.py -v
"""

import logging
from typing import Any

import pytest

from src.poc.tweak.markdown_section_classifier import SectionClassification, SectionType, TypeClassification
from src.poc.tweak.multi_line_paragraph import MarkdownSection

# Import to trigger factory registration
from src.poc.tweak.spacy_pipeline import RequirementProcessor, registry  # noqa: F401

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def spacy_module():
    """Import spacy (skip test if not available)."""
    try:
        import spacy

        return spacy
    except ImportError:
        pytest.skip("spaCy not installed")


@pytest.fixture
def nlp(spacy_module: Any) -> Any:
    """Load spaCy model (skip if not available)."""
    try:
        nlp = spacy_module.load("en_core_web_md")
        # Ensure classified_sections extension exists (normally registered by
        # SectionClassifierComponent.__init__, not instantiated in these tests).
        from spacy.tokens import Doc

        if not Doc.has_extension("classified_sections"):
            Doc.set_extension("classified_sections", default=[])
        return nlp
    except OSError:
        pytest.skip("en_core_web_md model not installed")


@pytest.fixture
def qualifications_section() -> MarkdownSection:
    """Section title/content that trigger requirement pattern matching."""
    return MarkdownSection(
        title="Requirements",
        content="Must have Python experience.",
        level=2,
        start_line=0,
        end_line=0,
        word_count=4,
        line_count=1,
        has_list=False,
    )


def _make_classification(confidence: float) -> SectionClassification:
    """Build SectionClassification with QUALIFICATIONS as top-ranked all_types entry."""
    return SectionClassification.from_type_classifications(
        [TypeClassification(SectionType.QUALIFICATIONS, confidence, ("required",))],
    )


# ============================================================================
# Confidence Threshold Tests (Issue #346)
# ============================================================================


class TestRequirementProcessorConfidenceThreshold:
    """Test min_confidence gating against classification.all_types[0]."""

    def test_high_confidence_qualifications_extracts_requirements(self, nlp, qualifications_section) -> None:
        """High-confidence QUALIFICATIONS (all_types[0] >= 0.70) extracts requirements."""
        processor = RequirementProcessor(nlp, "requirement_processor")

        doc = nlp("Test")
        classification = _make_classification(confidence=0.85)
        doc._.classified_sections = [(qualifications_section, classification)]

        doc = processor(doc)

        assert len(doc._.requirements) >= 1

    def test_low_confidence_qualifications_skips_extraction(self, nlp, qualifications_section, caplog) -> None:
        """Low-confidence QUALIFICATIONS (all_types[0] < 0.70) skips extraction and logs reason."""
        processor = RequirementProcessor(nlp, "requirement_processor")

        doc = nlp("Test")
        classification = _make_classification(confidence=0.42)
        doc._.classified_sections = [(qualifications_section, classification)]

        with caplog.at_level(logging.INFO):
            doc = processor(doc)

        assert doc._.requirements == []
        assert "Skipping QUALIFICATIONS extraction: confidence 0.42 < threshold 0.70" in caplog.text

    def test_min_confidence_zero_extracts_everything(self, nlp, qualifications_section) -> None:
        """min_confidence=0 extracts even very low-confidence QUALIFICATIONS sections (regression guard)."""
        processor = RequirementProcessor(nlp, "requirement_processor", min_confidence=0.0)

        doc = nlp("Test")
        classification = _make_classification(confidence=0.01)
        doc._.classified_sections = [(qualifications_section, classification)]

        doc = processor(doc)

        assert len(doc._.requirements) >= 1

    def test_missing_all_types_falls_back_to_labels_only(self, nlp, qualifications_section) -> None:
        """Empty/absent all_types falls back to labels-only filtering (no regression)."""
        processor = RequirementProcessor(nlp, "requirement_processor")

        doc = nlp("Test")
        # all_types intentionally empty/absent (default); labels-only behavior applies.
        classification = SectionClassification(all_types=(), labels=frozenset({SectionType.QUALIFICATIONS}))
        doc._.classified_sections = [(qualifications_section, classification)]

        doc = processor(doc)

        assert len(doc._.requirements) >= 1


# ============================================================================
# Run with: uv run pytest tests/poc/tweak/spacy_pipeline/test_requirement_processor.py -v
# ============================================================================
