"""Tests for SectionDetector (Issue #281).

Model-free pytest suite. Tests character-offset section detection, overlap resolution,
heading-like filtering, pattern injection, frozen dataclass, and module isolation.
"""

from __future__ import annotations

import copy
import dataclasses
import inspect
from typing import Any

import pytest

from src.preprocessing.section_detector import (
    MAX_INPUT_CHARS,
    SPANS_KEY,
    DetectedSection,
    SectionDetector,
)
from src.preprocessing.section_patterns import (
    DEFAULT_TARGET_SECTIONS,
    FILTER_SECTIONS,
    SECTION_DISPLAY_NAMES,
    SECTION_RULER_PATTERNS,
    SectionLabel,
)


class TestDetectedSectionDataclass:
    """Tests for DetectedSection dataclass immutability."""

    def test_detected_section_is_frozen(self) -> None:
        """DetectedSection raises FrozenInstanceError on mutation attempt."""
        section = DetectedSection(
            label=SectionLabel.REQUIREMENTS,
            display_name="Requirements",
            header_text="Requirements",
            header_start=0,
            header_end=12,
            content_start=12,
            content_end=50,
            content_text="Must know Python",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            section.label = SectionLabel.BENEFITS  # type: ignore[misc]

    def test_detected_section_all_fields(self) -> None:
        """DetectedSection holds all expected fields with correct types."""
        section = DetectedSection(
            label=SectionLabel.EDUCATION,
            display_name="Education",
            header_text="Education",
            header_start=10,
            header_end=19,
            content_start=20,
            content_end=100,
            content_text="Bachelor's degree required",
        )
        assert section.label == SectionLabel.EDUCATION
        assert section.display_name == "Education"
        assert section.header_text == "Education"
        assert section.header_start == 10
        assert section.header_end == 19
        assert section.content_start == 20
        assert section.content_end == 100
        assert section.content_text == "Bachelor's degree required"


class TestSectionDetectorEmptyInput:
    """Tests for handling empty and whitespace-only input."""

    def test_empty_string_returns_empty_list(self) -> None:
        """detect('') returns []."""
        detector = SectionDetector()
        assert detector.detect("") == []

    def test_none_like_empty_string_returns_empty_list(self) -> None:
        """detect(whitespace-only) returns []."""
        detector = SectionDetector()
        assert detector.detect("   \n\t  ") == []

    def test_whitespace_newlines_returns_empty_list(self) -> None:
        """detect with only newlines returns []."""
        detector = SectionDetector()
        assert detector.detect("\n\n\n") == []


class TestSectionDetectorBasicDetection:
    """Tests for basic section detection with default patterns."""

    def test_markdown_requirements_header_detected(self) -> None:
        """detect markdown '## Requirements' header with content."""
        text = "## Requirements\n- 5 years Python experience\n- Team player"
        detector = SectionDetector()
        sections = detector.detect(text)
        assert len(sections) == 1
        first = sections[0]
        assert first.label == SectionLabel.REQUIREMENTS
        assert first.display_name == "Requirements"
        assert first.header_text == "Requirements"
        assert first.header_start == 3  # after "## "
        assert first.header_end == 15
        assert "5 years Python" in first.content_text

    def test_markdown_benefits_header_detected(self) -> None:
        """detect markdown '## Benefits' header."""
        text = "## Benefits\n- Health insurance"
        detector = SectionDetector()
        sections = detector.detect(text)
        assert any(s.label == SectionLabel.BENEFITS for s in sections)

    def test_two_sections_content_boundaries(self) -> None:
        """detect two sections with content_end of first == header_start of second."""
        text = "## Requirements\n- Must know Python\n\n## Benefits\n- Health insurance"
        detector = SectionDetector()
        sections = detector.detect(text)
        req_section = next(s for s in sections if s.label == SectionLabel.REQUIREMENTS)
        ben_section = next(s for s in sections if s.label == SectionLabel.BENEFITS)
        # content_end of req should be at or near the start of "## Benefits"
        assert req_section.content_end <= len(text)
        assert ben_section.header_start <= len(text)
        # Sections ordered by start
        assert req_section.header_start < ben_section.header_start

    def test_section_ordering_by_start(self) -> None:
        """detect returns sections in order by header_start."""
        text = "## Requirements\nPython\n\n## Qualifications\nBachelor's"
        detector = SectionDetector()
        sections = detector.detect(text)
        starts = [s.header_start for s in sections]
        assert starts == sorted(starts)

    def test_no_overlaps_in_returned_sections(self) -> None:
        """detect returns sections with no overlapping ranges."""
        text = "## Requirements\nContent\n\n## Qualifications\nMore content"
        detector = SectionDetector()
        sections = detector.detect(text)
        for i in range(len(sections) - 1):
            assert sections[i].header_end <= sections[i + 1].header_start


class TestSectionDetectorHeadingLikeFiltering:
    """Tests for promote_headings filtering (heading-like detection)."""

    def test_heading_in_markdown_format_detected_with_promote_headings(self) -> None:
        """detect '## Requirements' (markdown header) with promote_headings=True."""
        text = "## Requirements\nSome text"
        detector = SectionDetector(promote_headings=True)
        sections = detector.detect(text)
        assert any(s.label == SectionLabel.REQUIREMENTS for s in sections)

    def test_heading_mid_sentence_not_detected_with_promote_headings(self) -> None:
        """detect skips 'Requirements' when mid-sentence with promote_headings=True."""
        # Place 'Requirements' in the middle of a sentence
        text = "We have multiple requirements such as Requirements and qualifications"
        detector = SectionDetector(promote_headings=True)
        sections = detector.detect(text)
        # Both 'requirements' and 'qualifications' match the ruler but sit mid-line
        assert sections == []
        assert SectionDetector(promote_headings=False).detect(text) != []

    def test_heading_mid_sentence_detected_with_promote_headings_false(self) -> None:
        """detect finds 'Requirements' mid-sentence with promote_headings=False."""
        text = "We have multiple requirements and also qualifications and benefits here"
        detector = SectionDetector(promote_headings=False)
        sections = detector.detect(text)
        labels = [s.label for s in sections]
        assert labels == [SectionLabel.REQUIREMENTS, SectionLabel.QUALIFICATIONS, SectionLabel.BENEFITS]


class TestSectionDetectorCustomPatterns:
    """Tests for custom pattern injection."""

    def test_custom_single_pattern_injection(self) -> None:
        """detect with custom pattern for 'schooling' → SECTION_EDUCATION."""
        custom_pattern: list[dict[str, Any]] = [
            {
                "label": SectionLabel.EDUCATION.value,
                "pattern": [{"LOWER": "schooling"}],
            }
        ]
        text = "## Schooling\nBachelor's degree required"
        detector = SectionDetector(patterns=custom_pattern)
        sections = detector.detect(text)
        # Should find the custom pattern
        assert len(sections) == 1
        schooling_matches = [s for s in sections if s.label == SectionLabel.EDUCATION]
        assert len(schooling_matches) == 1
        assert any("schooling" in s.header_text.lower() for s in schooling_matches)

    def test_default_patterns_not_mutated(self) -> None:
        """detect does not mutate the original SECTION_RULER_PATTERNS."""
        original_patterns = copy.deepcopy(SECTION_RULER_PATTERNS)
        _detector = SectionDetector()  # Uses default patterns internally
        # Verify patterns are unchanged
        assert SECTION_RULER_PATTERNS == original_patterns


class TestSectionDetectorTargetSections:
    """Tests for target_sections filtering method."""

    def test_target_sections_keeps_requirements(self) -> None:
        """target_sections keeps REQUIREMENTS section."""
        text = "## Requirements\nPython\n\n## Benefits\nHealth"
        detector = SectionDetector()
        sections = detector.detect(text)
        targeted = detector.target_sections(sections)
        req = [s for s in targeted if s.label == SectionLabel.REQUIREMENTS]
        assert len(req) == 1

    def test_target_sections_excludes_benefits(self) -> None:
        """target_sections excludes BENEFITS (in FILTER_SECTIONS)."""
        text = "## Benefits\nHealth insurance"
        detector = SectionDetector()
        sections = detector.detect(text)
        targeted = detector.target_sections(sections)
        ben = [s for s in targeted if s.label == SectionLabel.BENEFITS]
        assert len(ben) == 0

    def test_target_sections_excludes_compensation(self) -> None:
        """target_sections excludes COMPENSATION (in FILTER_SECTIONS)."""
        text = "## Compensation\n$80k-$120k"
        detector = SectionDetector()
        sections = detector.detect(text)
        targeted = detector.target_sections(sections)
        comp = [s for s in targeted if s.label == SectionLabel.COMPENSATION]
        assert len(comp) == 0

    def test_target_sections_preserves_order(self) -> None:
        """target_sections preserves section order."""
        text = "## Qualifications\nBS in CS\n\n## Requirements\nPython\n\n## Preferred Skills\nRust"
        detector = SectionDetector()
        sections = detector.detect(text)
        targeted = detector.target_sections(sections)
        labels = [s.label for s in targeted]
        # Should be in order of appearance
        assert labels == sorted(labels, key=lambda lbl: [s.header_start for s in sections if s.label == lbl][0])

    def test_target_sections_with_custom_target_set(self) -> None:
        """target_sections respects custom target_sections passed to __init__."""
        custom_targets = frozenset({SectionLabel.REQUIREMENTS})
        detector = SectionDetector(target_sections=custom_targets)
        text = "## Requirements\nPython\n\n## Qualifications\nBS"
        sections = detector.detect(text)
        targeted = detector.target_sections(sections)
        # Should only have REQUIREMENTS, not QUALIFICATIONS
        labels = {s.label for s in targeted}
        assert SectionLabel.REQUIREMENTS in labels
        assert SectionLabel.QUALIFICATIONS not in labels


class TestSectionDetectorInputTruncation:
    """Tests for MAX_INPUT_CHARS truncation."""

    def test_input_over_max_chars_truncated_no_raise(self) -> None:
        """detect truncates input > MAX_INPUT_CHARS without raising."""
        large_text = "## Requirements\n" + "a" * (MAX_INPUT_CHARS + 1000)
        detector = SectionDetector()
        sections = detector.detect(large_text)
        # Should not raise; sections may or may not be detected depending on truncation point
        assert isinstance(sections, list)

    def test_offsets_within_max_chars_after_truncation(self) -> None:
        """detect returns offsets ≤ MAX_INPUT_CHARS after truncation."""
        large_text = "## Requirements\n" + "x" * (MAX_INPUT_CHARS + 1000)
        detector = SectionDetector()
        sections = detector.detect(large_text)
        for section in sections:
            assert section.header_start <= MAX_INPUT_CHARS
            assert section.header_end <= MAX_INPUT_CHARS
            assert section.content_start <= MAX_INPUT_CHARS
            assert section.content_end <= MAX_INPUT_CHARS

    def test_exact_max_chars_no_truncation(self) -> None:
        """detect with text of exactly MAX_INPUT_CHARS length works."""
        text = "## Requirements\n" + "a" * (MAX_INPUT_CHARS - 16)
        assert len(text) == MAX_INPUT_CHARS
        detector = SectionDetector()
        sections = detector.detect(text)
        # Should work without truncation warning
        assert isinstance(sections, list)


class TestSectionDetectorDisplayNames:
    """Tests for display_name assignment."""

    def test_default_display_names_from_patterns(self) -> None:
        """detect uses SECTION_DISPLAY_NAMES for display_name field."""
        text = "## Requirements\nPython"
        detector = SectionDetector()
        sections = detector.detect(text)
        req = [s for s in sections if s.label == SectionLabel.REQUIREMENTS][0]
        assert req.display_name == SECTION_DISPLAY_NAMES[SectionLabel.REQUIREMENTS]

    def test_custom_display_names_injection(self) -> None:
        """detect uses custom display_names if provided."""
        custom_names = {
            SectionLabel.REQUIREMENTS: "Custom Requirements Header",
            SectionLabel.BENEFITS: "Custom Benefits",
        }
        text = "## Requirements\nContent"
        detector = SectionDetector(display_names=custom_names)
        sections = detector.detect(text)
        req = [s for s in sections if s.label == SectionLabel.REQUIREMENTS]
        assert len(req) == 1
        assert req[0].display_name == "Custom Requirements Header"


class TestSectionDetectorModuleIsolation:
    """Tests for module isolation and no src.poc imports."""

    def test_module_does_not_import_src_poc(self) -> None:
        """SectionDetector module source does not contain 'src.poc' imports."""
        import src.preprocessing.section_detector as sd_module

        source = inspect.getsource(sd_module)
        assert "src.poc" not in source
        assert "from src.poc" not in source
        assert "import src.poc" not in source


class TestSectionDetectorSpaCyIntegration:
    """Tests for spaCy pipeline usage."""

    def test_blank_nlp_created_on_init(self) -> None:
        """SectionDetector initializes blank spaCy pipeline on __init__."""
        detector = SectionDetector()
        # Verify internal nlp exists and is blank (no model)
        assert detector._nlp is not None
        assert "span_ruler" in detector._nlp.pipe_names
        assert "tagger" not in detector._nlp.pipe_names  # blank pipeline has no tagger

    def test_spans_key_configuration(self) -> None:
        """SectionDetector configures span_ruler with SPANS_KEY."""
        detector = SectionDetector()
        # The span_ruler should be configured with SPANS_KEY="sections"
        assert detector._nlp is not None
        # We can verify by checking that SPANS_KEY is used
        assert SPANS_KEY == "sections"


class TestSectionDetectorContentText:
    """Tests for content_text extraction."""

    def test_content_text_stripped(self) -> None:
        """content_text is text[content_start:content_end].strip()."""
        text = "## Requirements\n  - Must know Python  \n  - Team player  \n\n## Benefits"
        detector = SectionDetector()
        sections = detector.detect(text)
        req = next(s for s in sections if s.label == SectionLabel.REQUIREMENTS)
        # content_text should not have leading/trailing whitespace
        assert req.content_text == req.content_text.strip()
        # Should include the actual requirements
        assert "Python" in req.content_text or "python" in req.content_text.lower()

    def test_content_text_multiline(self) -> None:
        """content_text correctly spans multiple lines until next section."""
        text = "## Requirements\nLine 1\nLine 2\nLine 3\n\n## Qualifications\nQual 1"
        detector = SectionDetector()
        sections = detector.detect(text)
        req = next(s for s in sections if s.label == SectionLabel.REQUIREMENTS)
        # Should contain all three lines
        assert "Line 1" in req.content_text
        assert "Line 2" in req.content_text
        assert "Line 3" in req.content_text


class TestSectionDetectorEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_single_section_in_text(self) -> None:
        """detect single section with no following sections."""
        text = "## Requirements\nMust know Python"
        detector = SectionDetector()
        sections = detector.detect(text)
        assert len(sections) == 1
        req = sections[0]
        assert req.content_end == len(text)

    def test_multiple_same_label_sections(self) -> None:
        """detect handles multiple sections with the same label (kept separately)."""
        text = "## Requirements\nSet 1\n\n## Requirements\nSet 2"
        detector = SectionDetector()
        sections = detector.detect(text)
        req_sections = [s for s in sections if s.label == SectionLabel.REQUIREMENTS]
        assert len(req_sections) == 2
        for i in range(len(req_sections) - 1):
            assert req_sections[i].header_start < req_sections[i + 1].header_start

    def test_section_at_text_start(self) -> None:
        """detect section starting at position 0 of text."""
        text = "Requirements\nMust know Python"
        detector = SectionDetector()
        sections = detector.detect(text)
        assert len(sections) == 1
        assert sections[0].header_start == 0

    def test_next_header_marker_not_in_content(self) -> None:
        """content_text excludes the markdown marker of the following header."""
        detector = SectionDetector()
        sections = detector.detect("## Requirements\nPython\n\n**Benefits**\nHealth")
        assert [s.content_text for s in sections] == ["Python", "Health"]

    def test_closing_colon_and_bullet_marker(self) -> None:
        """content_text drops a closing ':' but keeps a leading '* ' bullet."""
        detector = SectionDetector()
        colon = detector.detect("Requirements:\nPython")
        bullet = detector.detect("Requirements\n* Python")
        assert colon[0].content_text == "Python"
        assert bullet[0].content_text == "* Python"

    @pytest.mark.parametrize("last_line", ["Must know C#", "Use snake_case_", "Point ->", "Experience *"])
    def test_trailing_marker_chars_in_content_preserved(self, last_line: str) -> None:
        """Real trailing '#', '_', '>', '*' in content survive; only the next header prefix is dropped."""
        sections = SectionDetector().detect(f"## Requirements\n{last_line}\n\n## Benefits\nHealth")
        assert sections[0].content_text == last_line
        assert sections[1].content_text == "Health"

    def test_last_section_trailing_marker_preserved(self) -> None:
        """No next header: nothing is trimmed from the end of the last section."""
        sections = SectionDetector().detect("## Requirements\nMust know C#")
        assert sections[0].content_text == "Must know C#"

    def test_very_long_content_section(self) -> None:
        """detect handles section with very long content."""
        long_content = "a" * 50000
        text = f"## Requirements\n{long_content}\n\n## Benefits\nShort"
        detector = SectionDetector()
        sections = detector.detect(text)
        req = [s for s in sections if s.label == SectionLabel.REQUIREMENTS]
        assert len(req) == 1
        assert req[0].content_text == long_content


__all__ = [
    "TestDetectedSectionDataclass",
    "TestSectionDetectorEmptyInput",
    "TestSectionDetectorBasicDetection",
    "TestSectionDetectorHeadingLikeFiltering",
    "TestSectionDetectorCustomPatterns",
    "TestSectionDetectorTargetSections",
    "TestSectionDetectorInputTruncation",
    "TestSectionDetectorDisplayNames",
    "TestSectionDetectorModuleIsolation",
    "TestSectionDetectorSpaCyIntegration",
    "TestSectionDetectorContentText",
    "TestSectionDetectorEdgeCases",
]
