"""Tests for SkillProcessor confidence threshold gating (Issue #347).

Coverage:
- High-confidence SKILLS section (top-ranked, >= min_confidence) -> extracted
- Low-confidence SKILLS section (top-ranked, < min_confidence) -> skipped
- Multi-type overlap: SKILLS present but not top-ranked, own confidence clears
  threshold -> still extracted
- all_types empty/absent -> falls back to labels-only behavior (no regression)

Run with:
    uv run pytest tests/poc/tweak/spacy_pipeline/test_skill_processor.py -v
"""

from typing import Any

import pytest

from src.poc.tweak.markdown_section_classifier import SectionClassification, TypeClassification
from src.poc.tweak.multi_line_paragraph import MarkdownSection
from src.poc.tweak.patterns import SectionType
from src.poc.tweak.spacy_pipeline import SkillProcessor


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
        loaded = spacy_module.load("en_core_web_md")
        from spacy.tokens import Doc

        from src.poc.tweak.multi_line_paragraph import MarkdownSpanRuler

        MarkdownSpanRuler(loaded)  # Initializes Doc extensions

        if not Doc.has_extension("classified_sections"):
            Doc.set_extension("classified_sections", default=[])

        return loaded
    except OSError:
        pytest.skip("en_core_web_md model not installed")


def _make_section(
    title: str = "Skills", content: str = "We are building scalable architectures with Python."
) -> MarkdownSection:
    return MarkdownSection(
        title=title,
        content=content,
        level=2,
        start_line=0,
        end_line=0,
        word_count=len(content.split()),
        line_count=1,
        has_list=False,
    )


class TestSkillProcessorConfidenceThreshold:
    """Test confidence-gated SKILLS extraction (Issue #347)."""

    def test_high_confidence_top_ranked_skills_extracted(self, nlp) -> None:
        """Top-ranked SKILLS at/above min_confidence -> skills extracted."""
        processor = SkillProcessor(nlp, "skill_processor", min_confidence=0.70)

        section = _make_section()
        tc = TypeClassification(SectionType.SKILLS, 0.85, ("skill",))
        classification = SectionClassification.from_type_classifications([tc])

        doc = nlp("Test document")
        doc._.classified_sections = [(section, classification)]

        doc = processor(doc)

        assert len(doc._.skills) > 0

    def test_low_confidence_top_ranked_skills_skipped(self, nlp) -> None:
        """Top-ranked SKILLS below min_confidence -> extraction skipped."""
        processor = SkillProcessor(nlp, "skill_processor", min_confidence=0.70)

        section = _make_section()
        tc = TypeClassification(SectionType.SKILLS, 0.42, ("skill",))
        classification = SectionClassification.from_type_classifications([tc])

        doc = nlp("Test document")
        doc._.classified_sections = [(section, classification)]

        doc = processor(doc)

        assert doc._.skills == []

    def test_skills_not_top_ranked_but_own_confidence_clears_threshold(self, nlp) -> None:
        """SKILLS present but not #1-ranked; its own confidence clears threshold -> extracted.

        Multi-type overlap case (e.g. "Technical Stack" section classified
        KNOWLEDGE 0.85 / SKILLS 0.72): SkillProcessor scans all_types for the
        SKILLS entry itself rather than requiring top-rank, unlike
        RequirementProcessor's top-ranked-only rule.
        """
        processor = SkillProcessor(nlp, "skill_processor", min_confidence=0.70)

        section = _make_section(title="Technical Stack")
        tc_top = TypeClassification(SectionType.KNOWLEDGE, 0.85, ("technical",))
        tc_skills = TypeClassification(SectionType.SKILLS, 0.72, ("skill",))
        classification = SectionClassification.from_type_classifications([tc_top, tc_skills])

        assert classification.all_types[0].section_type == SectionType.KNOWLEDGE

        doc = nlp("Test document")
        doc._.classified_sections = [(section, classification)]

        doc = processor(doc)

        assert len(doc._.skills) > 0

    def test_skills_not_top_ranked_own_confidence_below_threshold_skipped(self, nlp) -> None:
        """SKILLS present but not top-ranked, and its own confidence is below threshold -> skipped."""
        processor = SkillProcessor(nlp, "skill_processor", min_confidence=0.70)

        section = _make_section(title="Technical Stack")
        tc_top = TypeClassification(SectionType.KNOWLEDGE, 0.85, ("technical",))
        tc_skills = TypeClassification(SectionType.SKILLS, 0.50, ("skill",))
        classification = SectionClassification.from_type_classifications([tc_top, tc_skills])

        doc = nlp("Test document")
        doc._.classified_sections = [(section, classification)]

        doc = processor(doc)

        assert doc._.skills == []

    def test_all_types_empty_falls_back_to_labels_only(self, nlp) -> None:
        """all_types empty/absent -> labels-only behavior unchanged (no regression)."""
        processor = SkillProcessor(nlp, "skill_processor", min_confidence=0.70)

        section = _make_section()
        classification = SectionClassification(
            all_types=(),
            labels=frozenset({SectionType.SKILLS}),
        )

        doc = nlp("Test document")
        doc._.classified_sections = [(section, classification)]

        doc = processor(doc)

        # No confidence data available: extraction proceeds purely on labels membership.
        assert len(doc._.skills) > 0


class TestSkillProcessorLineSegmentation:
    """Test line-by-line segmentation before spaCy Matcher (Issue #354)."""

    def test_multiline_skill_list_extracts_separate_skills(self, nlp) -> None:
        """Multi-line skill list (3 lines) -> 3 separate skills, not merged."""
        processor = SkillProcessor(nlp, "skill_processor", min_confidence=0.70)

        # Three skills on separate lines
        multiline_content = "Building scalable systems\nLeading distributed teams\nDesigning scalable architectures"
        section = _make_section(content=multiline_content)
        tc = TypeClassification(SectionType.SKILLS, 0.85, ("skill",))
        classification = SectionClassification.from_type_classifications([tc])

        doc = nlp("Test document")
        doc._.classified_sections = [(section, classification)]

        doc = processor(doc)

        # Should extract at least 3 distinct skills (one per line)
        assert len(doc._.skills) >= 3
        # Verify skills are distinct (not merged into one)
        skill_texts = [s["skill"] for s in doc._.skills]
        assert "building scalable systems" in skill_texts or "building scalable" in skill_texts
        assert any("leading" in s for s in skill_texts)
        assert any("designing" in s for s in skill_texts)

    def test_mixed_line_endings_correct_segmentation(self, nlp) -> None:
        """Mixed line endings (\\r\\n + \\n) -> correct per-line segmentation."""
        processor = SkillProcessor(nlp, "skill_processor", min_confidence=0.70)

        # Mix Windows (\\r\\n) and Unix (\\n) line endings
        multiline_content = "Building scalable systems\r\nLeading distributed teams\nDesigning architectures"
        section = _make_section(content=multiline_content)
        tc = TypeClassification(SectionType.SKILLS, 0.85, ("skill",))
        classification = SectionClassification.from_type_classifications([tc])

        doc = nlp("Test document")
        doc._.classified_sections = [(section, classification)]

        doc = processor(doc)

        # Should extract multiple skills despite mixed line endings
        assert len(doc._.skills) >= 2
        skill_texts = [s["skill"] for s in doc._.skills]
        # Verify no skills contain raw line ending markers
        for skill in skill_texts:
            assert "\r" not in skill
            assert "\n" not in skill

    def test_single_line_skill_no_regression(self, nlp) -> None:
        """Single-line skills -> no regression from line segmentation."""
        processor = SkillProcessor(nlp, "skill_processor", min_confidence=0.70)

        section = _make_section(content="Building scalable architectures with Python and distributed systems")
        tc = TypeClassification(SectionType.SKILLS, 0.85, ("skill",))
        classification = SectionClassification.from_type_classifications([tc])

        doc = nlp("Test document")
        doc._.classified_sections = [(section, classification)]

        doc = processor(doc)

        # Should extract skills normally
        assert len(doc._.skills) > 0

    def test_seen_skills_deduplication_across_lines(self, nlp) -> None:
        """Deduplication (seen_skills) still works across multiple lines."""
        processor = SkillProcessor(nlp, "skill_processor", min_confidence=0.70)

        # Repeated skill on different lines
        multiline_content = (
            "Building scalable systems\n"
            "Building scalable systems\n"  # Duplicate
            "Leading distributed teams"
        )
        section = _make_section(content=multiline_content)
        tc = TypeClassification(SectionType.SKILLS, 0.85, ("skill",))
        classification = SectionClassification.from_type_classifications([tc])

        doc = nlp("Test document")
        doc._.classified_sections = [(section, classification)]

        doc = processor(doc)

        # Duplicates should be deduplicated
        skill_texts = [s["skill"] for s in doc._.skills]
        # "building scalable systems" or similar should appear exactly once
        building_count = sum(1 for s in skill_texts if "building" in s and "scalable" in s)
        assert building_count == 1


class TestSkillProcessorNounLedBullets:
    """Test noun-led fallback for bullet-point skills (Issue #372)."""

    def test_comma_separated_skills_extracted(self, nlp) -> None:
        """Comma-separated skills without action verb -> noun-led extraction.

        Test case: "Python, C++, SQL" under "Technical Skills" title.
        Expected: exactly {"python","c++","sql"}
        """
        processor = SkillProcessor(nlp, "skill_processor", min_confidence=0.70)

        section = _make_section(title="Technical Skills", content="Python, C++, SQL")
        tc = TypeClassification(SectionType.SKILLS, 0.85, ("skill",))
        classification = SectionClassification.from_type_classifications([tc])

        doc = nlp("Test document")
        doc._.classified_sections = [(section, classification)]

        doc = processor(doc)

        skill_texts = {s["skill"] for s in doc._.skills}
        assert skill_texts == {"python", "c++", "sql"}

    def test_bullet_points_with_qualifiers_stripped(self, nlp) -> None:
        """Bullet points with trailing qualifiers -> qualifiers removed.

        Test case: "* Python experience required" + "* C++ preferred"
        Expected: {"python","c++"}
        """
        processor = SkillProcessor(nlp, "skill_processor", min_confidence=0.70)

        content = "* Python experience required\n* C++ preferred"
        section = _make_section(title="Technical Skills", content=content)
        tc = TypeClassification(SectionType.SKILLS, 0.85, ("skill",))
        classification = SectionClassification.from_type_classifications([tc])

        doc = nlp("Test document")
        doc._.classified_sections = [(section, classification)]

        doc = processor(doc)

        skill_texts = {s["skill"] for s in doc._.skills}
        assert skill_texts == {"python", "c++"}

    def test_mixed_verb_led_and_noun_led(self, nlp) -> None:
        """Mixed section with verb-led and noun-led lines -> both extracted.

        Verb-led line should use Matcher, noun-led line should use fallback.
        Both should be present in results.
        """
        processor = SkillProcessor(nlp, "skill_processor", min_confidence=0.70)

        content = "Building scalable systems\n* Python required"
        section = _make_section(title="Technical Skills", content=content)
        tc = TypeClassification(SectionType.SKILLS, 0.85, ("skill",))
        classification = SectionClassification.from_type_classifications([tc])

        doc = nlp("Test document")
        doc._.classified_sections = [(section, classification)]

        doc = processor(doc)

        skill_texts = {s["skill"] for s in doc._.skills}
        # Should contain both verb-led skills (like "building scalable systems")
        # and noun-led skills (like "python")
        assert "python" in skill_texts
        assert any("building" in s for s in skill_texts)

    def test_non_skills_section_yields_nothing(self, nlp) -> None:
        """Non-SKILLS section with noun-led lines -> no extraction.

        Section classified as QUALIFICATIONS, not SKILLS, should not extract.
        """
        processor = SkillProcessor(nlp, "skill_processor", min_confidence=0.70)

        content = "* Python required\n* C++ preferred"
        section = _make_section(title="Qualifications", content=content)
        tc = TypeClassification(SectionType.QUALIFICATIONS, 0.85, ("qualification",))
        classification = SectionClassification.from_type_classifications([tc])

        doc = nlp("Test document")
        doc._.classified_sections = [(section, classification)]

        doc = processor(doc)

        assert doc._.skills == []

    def test_low_confidence_skills_section_skipped(self, nlp) -> None:
        """Low-confidence SKILLS section (below gate) -> extraction skipped.

        SKILLS confidence < min_confidence (0.70) should be skipped.
        """
        processor = SkillProcessor(nlp, "skill_processor", min_confidence=0.70)

        content = "* Python required\n* C++ preferred"
        section = _make_section(title="Technical Skills", content=content)
        tc = TypeClassification(SectionType.SKILLS, 0.50, ("skill",))
        classification = SectionClassification.from_type_classifications([tc])

        doc = nlp("Test document")
        doc._.classified_sections = [(section, classification)]

        doc = processor(doc)

        assert doc._.skills == []

    def test_dedup_across_lines_title_echo_skipped(self, nlp) -> None:
        """Dedup across lines, title echoes skipped, blank lines ignored.

        Test:
        - Duplicate skills across lines should be deduplicated
        - Title line echoing section title should not emit a skill
        - Blank or marker-only lines should yield nothing
        """
        processor = SkillProcessor(nlp, "skill_processor", min_confidence=0.70)

        content = (
            "Technical Skills\n"  # Title echo - should be skipped
            "* Python required\n"
            "* Python preferred\n"  # Duplicate of above
            "* C++ required\n"
            "\n"  # Blank line
            "- \n"  # Marker-only line
            "*\n"  # Another marker-only
        )
        section = _make_section(title="Technical Skills", content=content)
        tc = TypeClassification(SectionType.SKILLS, 0.85, ("skill",))
        classification = SectionClassification.from_type_classifications([tc])

        doc = nlp("Test document")
        doc._.classified_sections = [(section, classification)]

        doc = processor(doc)

        skill_texts = {s["skill"] for s in doc._.skills}
        # Should have exactly python and c++, no duplicates, no title echo
        assert skill_texts == {"python", "c++"}
        # Verify "technical skills" was not extracted
        assert "technical skills" not in skill_texts

    def test_worksource_shaped_e2e(self, nlp) -> None:
        """End-to-end test with WorkSource-shaped text.

        Uses text from test_heading_promoter.py:288-317:
        - Section: Technical Skills
        - Content: "* Python experience required" + "* C++ preferred"

        Expected result: ["python","c++"] (order-insensitive)
        """
        processor = SkillProcessor(nlp, "skill_processor", min_confidence=0.70)

        # WorkSource-shaped text for Technical Skills section
        content = "* Python experience required\n* C++ preferred"
        section = _make_section(title="Technical Skills", content=content)
        tc = TypeClassification(SectionType.SKILLS, 0.85, ("skill",))
        classification = SectionClassification.from_type_classifications([tc])

        doc = nlp("Test document")
        doc._.classified_sections = [(section, classification)]

        # Run skill processor
        doc = processor(doc)

        # Extract skills
        skill_texts = {s["skill"] for s in doc._.skills}

        # Should contain python and c++ (order-insensitive)
        assert "python" in skill_texts
        assert "c++" in skill_texts
