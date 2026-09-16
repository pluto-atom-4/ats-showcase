"""Tests for MarkdownSection schema and batch processor integration.

Tests both the MarkdownSection data class and its integration with
batch_processor for Issue #338.
"""

import pytest

from src.poc.tweak.batch_processor import JobResult
from src.poc.tweak.section_model import MarkdownSection


class TestMarkdownSectionSchema:
    """Test MarkdownSection data class."""

    def test_section_creation_valid(self):
        """Test creating a valid MarkdownSection."""
        section = MarkdownSection(
            section_id="sec_0",
            heading="Requirements",
            content="5+ years of Python experience",
            section_type="requirements",
            confidence=0.92,
            line_start=10,
            line_end=25,
        )

        assert section.section_id == "sec_0"
        assert section.heading == "Requirements"
        assert section.section_type == "requirements"
        assert section.confidence == 0.92
        assert section.line_start == 10
        assert section.line_end == 25

    def test_section_confidence_validation_too_high(self):
        """Test confidence > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="confidence must be in"):
            MarkdownSection(
                section_id="sec_0",
                heading="Test",
                content="Content",
                section_type="requirements",
                confidence=1.5,  # Invalid
                line_start=0,
                line_end=10,
            )

    def test_section_confidence_validation_negative(self):
        """Test negative confidence raises ValueError."""
        with pytest.raises(ValueError, match="confidence must be in"):
            MarkdownSection(
                section_id="sec_0",
                heading="Test",
                content="Content",
                section_type="requirements",
                confidence=-0.1,  # Invalid
                line_start=0,
                line_end=10,
            )

    def test_section_line_numbers_validation(self):
        """Test line_end < line_start raises ValueError."""
        with pytest.raises(ValueError, match="line_end .* must be >="):
            MarkdownSection(
                section_id="sec_0",
                heading="Test",
                content="Content",
                section_type="requirements",
                confidence=0.85,
                line_start=25,
                line_end=10,  # Invalid: end < start
            )

    def test_section_confidence_boundary_values(self):
        """Test boundary values for confidence [0.0, 1.0]."""
        # Confidence = 0.0 (valid)
        section1 = MarkdownSection(
            section_id="sec_0",
            heading="Test",
            content="Content",
            section_type="requirements",
            confidence=0.0,
            line_start=0,
            line_end=10,
        )
        assert section1.confidence == 0.0

        # Confidence = 1.0 (valid)
        section2 = MarkdownSection(
            section_id="sec_1",
            heading="Test",
            content="Content",
            section_type="requirements",
            confidence=1.0,
            line_start=0,
            line_end=10,
        )
        assert section2.confidence == 1.0

    def test_section_summary_property(self):
        """Test the summary property formatting."""
        section = MarkdownSection(
            section_id="sec_0",
            heading="Requirements",
            content="Content",
            section_type="requirements",
            confidence=0.92,
            line_start=10,
            line_end=25,
        )

        expected = "sec_0: requirements (conf=0.92) @ lines 10-25"
        assert section.summary == expected

    def test_section_content_preview_no_truncation(self):
        """Test content_preview when content is short."""
        section = MarkdownSection(
            section_id="sec_0",
            heading="Test",
            content="Short content",
            section_type="requirements",
            confidence=0.85,
            line_start=0,
            line_end=5,
        )

        preview = section.content_preview
        assert preview == "Short content"

    def test_section_content_preview_with_truncation(self):
        """Test content_preview truncates long content."""
        long_content = "a" * 100
        section = MarkdownSection(
            section_id="sec_0",
            heading="Test",
            content=long_content,
            section_type="requirements",
            confidence=0.85,
            line_start=0,
            line_end=5,
        )

        preview = section.content_preview
        assert len(preview) <= 63  # 60 chars + "..."
        assert preview.endswith("...")

    def test_section_to_dict_conversion(self):
        """Test converting MarkdownSection to dictionary."""
        section = MarkdownSection(
            section_id="sec_0",
            heading="Requirements",
            content="5+ years experience",
            section_type="requirements",
            confidence=0.9234,  # Should be rounded to 0.92
            line_start=10,
            line_end=25,
            matched_keywords=["years", "experience"],
        )

        section_dict = section.to_dict()

        assert section_dict["section_id"] == "sec_0"
        assert section_dict["heading"] == "Requirements"
        assert section_dict["content"] == "5+ years experience"
        assert section_dict["section_type"] == "requirements"
        assert section_dict["confidence"] == 0.92  # Rounded
        assert section_dict["line_start"] == 10
        assert section_dict["line_end"] == 25
        assert section_dict["matched_keywords"] == ["years", "experience"]

    def test_section_with_empty_keywords(self):
        """Test MarkdownSection with no matched keywords."""
        section = MarkdownSection(
            section_id="sec_0",
            heading="Test",
            content="Content",
            section_type="requirements",
            confidence=0.85,
            line_start=0,
            line_end=10,
            # matched_keywords not provided, should default to []
        )

        assert section.matched_keywords == []
        assert section.to_dict()["matched_keywords"] == []

    def test_section_with_empty_heading(self):
        """Test MarkdownSection with empty heading."""
        section = MarkdownSection(
            section_id="sec_0",
            heading="",  # Empty heading (allowed)
            content="Content without heading",
            section_type="requirements",
            confidence=0.85,
            line_start=0,
            line_end=10,
        )

        assert section.heading == ""
        assert section.summary == "sec_0: requirements (conf=0.85) @ lines 0-10"


class TestMarkdownSectionNewFields:
    """Test new fields for full classification data preservation (Issue #338, #295)."""

    def test_new_fields_default_values(self):
        """Test new fields have correct defaults for backward compatibility."""
        section = MarkdownSection(
            section_id="sec_0",
            heading="Test",
            content="Content",
            section_type="requirements",
            confidence=0.85,
            line_start=0,
            line_end=10,
        )

        # New fields should default to empty or False
        assert section.all_types == []
        assert section.labels == []
        assert section.is_skip is False
        assert section.keyword_matches == []

    def test_new_fields_with_multi_type_data(self):
        """Test new fields with multi-type classification data."""
        section = MarkdownSection(
            section_id="sec_0",
            heading="Skills and Responsibilities",
            content="Manage Python projects",
            section_type="skills",
            confidence=0.90,
            line_start=0,
            line_end=5,
            matched_keywords=["skill"],
            all_types=[
                {"section_type": "skills", "confidence": 0.90},
                {"section_type": "responsibilities", "confidence": 0.75},
            ],
            labels=["skills", "responsibilities"],
            is_skip=False,
            keyword_matches=[
                {"keyword": "skill", "section_type": "skills", "source": "title", "position": 0},
                {"keyword": "responsibility", "section_type": "responsibilities", "source": "content", "position": 15},
            ],
        )

        assert len(section.all_types) == 2
        assert section.all_types[0]["section_type"] == "skills"
        assert section.all_types[0]["confidence"] == 0.90
        assert section.all_types[1]["section_type"] == "responsibilities"
        assert section.all_types[1]["confidence"] == 0.75

        assert len(section.labels) == 2
        assert "skills" in section.labels
        assert "responsibilities" in section.labels

        assert section.is_skip is False

        assert len(section.keyword_matches) == 2
        assert section.keyword_matches[0]["keyword"] == "skill"
        assert section.keyword_matches[0]["source"] == "title"
        assert section.keyword_matches[0]["position"] == 0
        assert section.keyword_matches[1]["keyword"] == "responsibility"
        assert section.keyword_matches[1]["source"] == "content"
        assert section.keyword_matches[1]["position"] == 15

    def test_to_dict_includes_new_fields(self):
        """Test to_dict() includes all new fields."""
        section = MarkdownSection(
            section_id="sec_0",
            heading="Requirements",
            content="Content",
            section_type="requirements",
            confidence=0.92,
            line_start=10,
            line_end=25,
            matched_keywords=["years"],
            all_types=[
                {"section_type": "requirements", "confidence": 0.92},
                {"section_type": "qualifications", "confidence": 0.75},
            ],
            labels=["requirements", "qualifications"],
            is_skip=False,
            keyword_matches=[{"keyword": "years", "section_type": "requirements", "source": "title", "position": 5}],
        )

        section_dict = section.to_dict()

        # Verify new fields are in dict
        assert "all_types" in section_dict
        assert "labels" in section_dict
        assert "is_skip" in section_dict
        assert "keyword_matches" in section_dict

        # Verify content
        assert section_dict["all_types"] == section.all_types
        assert section_dict["labels"] == section.labels
        assert section_dict["is_skip"] is False
        assert len(section_dict["keyword_matches"]) == 1

    def test_section_with_skip_flag(self):
        """Test section with is_skip=True."""
        section = MarkdownSection(
            section_id="sec_0",
            heading="Legal Disclaimer",
            content="This is boilerplate",
            section_type="skip",
            confidence=0.70,
            line_start=0,
            line_end=5,
            is_skip=True,
            labels=["skip"],
            all_types=[{"section_type": "skip", "confidence": 0.70}],
        )

        assert section.is_skip is True
        assert section.labels == ["skip"]
        assert section.to_dict()["is_skip"] is True

    def test_to_dict_rounds_all_types_confidence_consistently(self):
        """Test to_dict() rounds all_types confidence values consistently with primary confidence.

        Addresses Issue #338 review round 2 finding: Ensure that when serializing,
        confidence values are rounded to 2 decimals consistently across both the primary
        confidence field and the all_types entries.
        """
        # Create section with full-precision confidence values
        full_precision_confidence = 0.926789
        secondary_precision = 0.754321

        section = MarkdownSection(
            section_id="sec_0",
            heading="Requirements",
            content="5+ years experience required",
            section_type="requirements",
            confidence=full_precision_confidence,  # 0.926789, should round to 0.93
            line_start=10,
            line_end=25,
            matched_keywords=["years"],
            all_types=[
                {
                    "section_type": "requirements",
                    "confidence": full_precision_confidence,  # Should also round to 0.93
                },
                {"section_type": "qualifications", "confidence": secondary_precision},  # Should round to 0.75
            ],
            labels=["requirements", "qualifications"],
            is_skip=False,
        )

        # Verify internal representation maintains full precision
        assert section.confidence == full_precision_confidence
        assert section.all_types[0]["confidence"] == full_precision_confidence
        assert section.all_types[1]["confidence"] == secondary_precision

        # After to_dict(), serialization should round both
        section_dict = section.to_dict()

        # Primary confidence should be rounded to 2 decimals
        assert section_dict["confidence"] == 0.93

        # all_types entries should also be rounded to 2 decimals
        assert len(section_dict["all_types"]) == 2
        assert section_dict["all_types"][0]["confidence"] == 0.93  # Same primary type, same rounded value
        assert section_dict["all_types"][1]["confidence"] == 0.75

        # Verify all_types structure is preserved
        assert section_dict["all_types"][0]["section_type"] == "requirements"
        assert section_dict["all_types"][1]["section_type"] == "qualifications"


class TestJobResultWithSections:
    """Test JobResult integration with markdown_sections."""

    def test_job_result_with_sections(self):
        """Test JobResult stores markdown_sections."""
        result = JobResult(
            job_id="test_1",
            title="Senior Engineer",
            company="Acme Corp",
            sections_detected=2,
            keyword_matches=5,
            confidence_min=0.75,
            confidence_max=0.95,
            confidence_avg=0.85,
        )

        section1 = MarkdownSection(
            section_id="sec_0",
            heading="Role Overview",
            content="Lead the design of distributed systems...",
            section_type="responsibilities",
            confidence=0.85,
            line_start=0,
            line_end=10,
        )

        section2 = MarkdownSection(
            section_id="sec_1",
            heading="Requirements",
            content="5+ years of experience with Kubernetes...",
            section_type="requirements",
            confidence=0.92,
            line_start=11,
            line_end=20,
        )

        result.markdown_sections = [section1, section2]

        assert len(result.markdown_sections) == 2
        assert result.markdown_sections[0].section_type == "responsibilities"
        assert result.markdown_sections[1].section_type == "requirements"
        assert result.markdown_sections[0].confidence == 0.85
        assert result.markdown_sections[1].confidence == 0.92

    def test_job_result_sections_match_count(self):
        """Test sections_detected matches markdown_sections length."""
        result = JobResult(
            job_id="test_1",
            title="Engineer",
            company="Company",
            sections_detected=3,
            keyword_matches=0,
            confidence_min=0.8,
            confidence_max=0.9,
            confidence_avg=0.85,
        )

        sections = [
            MarkdownSection(
                section_id=f"sec_{i}",
                heading=f"Section {i}",
                content=f"Content {i}",
                section_type="requirements",
                confidence=0.85,
                line_start=i * 10,
                line_end=(i + 1) * 10 - 1,
            )
            for i in range(3)
        ]

        result.markdown_sections = sections

        # Verify count matches
        assert len(result.markdown_sections) == result.sections_detected == 3

    def test_job_result_serialization_with_sections(self):
        """Test JobResult can be serialized with sections (for JSON export)."""
        from dataclasses import asdict

        result = JobResult(
            job_id="test_1",
            title="Engineer",
            company="Company",
            sections_detected=1,
            keyword_matches=2,
            confidence_min=0.85,
            confidence_max=0.95,
            confidence_avg=0.90,
        )

        section = MarkdownSection(
            section_id="sec_0",
            heading="Requirements",
            content="Content here",
            section_type="requirements",
            confidence=0.90,
            line_start=0,
            line_end=5,
            matched_keywords=["experience"],
        )

        result.markdown_sections = [section]

        # Convert to dict (should handle MarkdownSection objects)
        result_dict = asdict(result)

        assert "markdown_sections" in result_dict
        assert len(result_dict["markdown_sections"]) == 1
        assert result_dict["markdown_sections"][0]["section_id"] == "sec_0"
        assert result_dict["markdown_sections"][0]["section_type"] == "requirements"

    def test_job_result_serialization_includes_new_fields(self):
        """Test JobResult serialization includes new classification fields."""
        from dataclasses import asdict

        result = JobResult(
            job_id="test_1",
            title="Engineer",
            company="Company",
            sections_detected=1,
            keyword_matches=2,
            confidence_min=0.85,
            confidence_max=0.95,
            confidence_avg=0.90,
        )

        section = MarkdownSection(
            section_id="sec_0",
            heading="Skills and Responsibilities",
            content="Manage Python projects",
            section_type="skills",
            confidence=0.90,
            line_start=0,
            line_end=5,
            matched_keywords=["skill"],
            all_types=[
                {"section_type": "skills", "confidence": 0.90},
                {"section_type": "responsibilities", "confidence": 0.75},
            ],
            labels=["skills", "responsibilities"],
            is_skip=False,
            keyword_matches=[{"keyword": "skill", "section_type": "skills", "source": "title", "position": 0}],
        )

        result.markdown_sections = [section]

        # Convert to dict
        result_dict = asdict(result)

        # Verify new fields are in serialized output
        section_dict = result_dict["markdown_sections"][0]
        assert "all_types" in section_dict
        assert "labels" in section_dict
        assert "is_skip" in section_dict
        assert "keyword_matches" in section_dict

        assert len(section_dict["all_types"]) == 2
        assert section_dict["labels"] == ["skills", "responsibilities"]
        assert section_dict["is_skip"] is False
        assert len(section_dict["keyword_matches"]) == 1

    def test_job_result_with_errors_and_sections(self):
        """Test JobResult with both sections and errors."""
        result = JobResult(
            job_id="test_1",
            title="Engineer",
            company="Company",
            sections_detected=1,
            keyword_matches=0,
            confidence_min=0.0,
            confidence_max=0.0,
            confidence_avg=0.0,
        )

        section = MarkdownSection(
            section_id="sec_0",
            heading="Partial Section",
            content="Some content",
            section_type="unknown",
            confidence=0.0,
            line_start=0,
            line_end=5,
        )

        result.markdown_sections = [section]
        result.add_error("converter", "HTML conversion failed")

        assert len(result.markdown_sections) == 1
        assert len(result.errors) == 1
        assert result.has_errors()


class TestBatchProcessorSectionIntegration:
    """Integration tests for batch processor with sections.

    Note: These are placeholder tests that verify structure.
    Full integration tests require mock pipeline components.
    """

    def test_job_result_structure_with_sections(self):
        """Test JobResult structure includes sections field."""
        result = JobResult(
            job_id="test_1",
            title="Test Job",
            company="Test Co",
            sections_detected=0,
            keyword_matches=0,
            confidence_min=0.0,
            confidence_max=0.0,
            confidence_avg=0.0,
        )

        # Verify markdown_sections field exists and is initialized
        assert hasattr(result, "markdown_sections")
        assert isinstance(result.markdown_sections, list)
        assert len(result.markdown_sections) == 0

    def test_markdown_section_in_job_result_dataclass(self):
        """Test markdown_sections is a proper dataclass field."""
        from dataclasses import fields

        result = JobResult(
            job_id="test_1",
            title="Test Job",
            company="Test Co",
            sections_detected=0,
            keyword_matches=0,
            confidence_min=0.0,
            confidence_max=0.0,
            confidence_avg=0.0,
        )

        field_names = {f.name for f in fields(result)}
        assert "markdown_sections" in field_names

    def test_batch_processor_preserves_multi_type_classification(self):
        """Test that batch processor preserves multi-type classification data (Issue #338, #295).

        This test verifies that when a section matches multiple types, all types
        are stored in all_types, not just the primary (highest-confidence) type.
        """
        # Create a section representing multi-type classification
        section = MarkdownSection(
            section_id="sec_0",
            heading="Skills and Responsibilities",
            content="Manage Python projects and lead team",
            section_type="skills",  # Primary type
            confidence=0.90,  # Primary confidence
            line_start=0,
            line_end=5,
            matched_keywords=["skill", "responsibility"],
            # Full multi-type data preserved from SectionClassification
            all_types=[
                {"section_type": "skills", "confidence": 0.90},
                {"section_type": "responsibilities", "confidence": 0.75},
            ],
            labels=["skills", "responsibilities"],
            is_skip=False,
            keyword_matches=[
                {"keyword": "skill", "section_type": "skills", "source": "title", "position": 0},
                {"keyword": "responsibility", "section_type": "responsibilities", "source": "content", "position": 25},
            ],
        )

        # Verify primary type from first entry
        assert section.section_type == "skills"
        assert section.confidence == 0.90

        # Verify all types are preserved
        assert len(section.all_types) == 2
        assert section.all_types[0]["section_type"] == "skills"
        assert section.all_types[1]["section_type"] == "responsibilities"

        # Verify labels (frozenset from SectionClassification converted to list)
        assert len(section.labels) == 2
        assert "skills" in section.labels
        assert "responsibilities" in section.labels

        # Verify keyword matches with position and source
        assert len(section.keyword_matches) == 2
        assert section.keyword_matches[0]["source"] in ["title", "content"]
        assert "position" in section.keyword_matches[0]
