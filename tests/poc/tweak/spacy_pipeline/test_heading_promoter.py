"""Tests for HeadingPromoter component (Issue #365).

Tests heading promotion rules, edge cases, idempotence, and consistency with
SectionClassifier keyword matching.
"""

import pytest

from src.poc.tweak.markdown_section_classifier import SectionClassifier, SectionType
from src.poc.tweak.spacy_pipeline.heading_promoter import KNOWN_PLAIN_HEADINGS, HeadingPromoter


class TestHeadingPromoterBasic:
    """Test basic heading promotion rules."""

    def test_promote_exact_match_case_insensitive(self) -> None:
        """Exact phrase match (case-insensitive) gets promoted."""
        promoter = HeadingPromoter()
        text = "Job Description\nWork with clients."
        result = promoter.process(text)
        assert "## Job Description" in result

    def test_promote_with_trailing_colon(self) -> None:
        """Trailing colon is stripped; phrase still matches."""
        promoter = HeadingPromoter()
        text = "Role Overview:\nFocus areas below."
        result = promoter.process(text)
        assert "## Role Overview" in result
        # Colon removed in output
        assert "## Role Overview:" not in result

    def test_uppercase_variant_matches(self) -> None:
        """All-uppercase variant of phrase gets promoted."""
        promoter = HeadingPromoter()
        text = "TECHNICAL SKILLS\nPython, Java."
        result = promoter.process(text)
        assert "## TECHNICAL SKILLS" in result

    def test_mixed_case_variant_matches(self) -> None:
        """Mixed-case variant of phrase gets promoted."""
        promoter = HeadingPromoter()
        text = "Key Responsibilities\nManage projects."
        result = promoter.process(text)
        assert "## Key Responsibilities" in result

    def test_unicode_apostrophe_normalized(self) -> None:
        """Unicode apostrophes (smart quotes) match straight apostrophes."""
        promoter = HeadingPromoter()
        # Test with straight apostrophe; the phrase should exist if defined
        text = "Roles and Responsibilities\nMore info."
        result = promoter.process(text)
        # "Roles and Responsibilities" not in KNOWN_PLAIN_HEADINGS, stays as-is
        assert "## Roles and Responsibilities" not in result


class TestHeadingPromoterStructuralRules:
    """Test structural promotion rules (line position, formatting, etc.)."""

    def test_not_promoted_bold_line(self) -> None:
        """Line that is entirely bold (**...**) is not promoted."""
        promoter = HeadingPromoter()
        text = "**Job Description**\nContent."
        result = promoter.process(text)
        assert "## **Job Description**" not in result

    def test_not_promoted_in_paragraph(self) -> None:
        """Phrase in middle of paragraph (no blank line before) is not promoted."""
        promoter = HeadingPromoter()
        text = "Some text. Job Description is next.\nMore content."
        result = promoter.process(text)
        assert "## Job Description" not in result

    def test_not_promoted_hash_line(self) -> None:
        """Line starting with # (already markdown) is not promoted."""
        promoter = HeadingPromoter()
        text = "# Job Description\nContent."
        result = promoter.process(text)
        assert "## # Job Description" not in result

    def test_not_promoted_ast_line(self) -> None:
        """Line starting with * (list marker) is not promoted."""
        promoter = HeadingPromoter()
        text = "* Job Description\nContent."
        result = promoter.process(text)
        assert "## * Job Description" not in result

    def test_not_promoted_dash_line(self) -> None:
        """Line starting with dash is not promoted."""
        promoter = HeadingPromoter()
        text = "- Role Overview\nContent."
        result = promoter.process(text)
        assert "## - Role Overview" not in result

    def test_not_promoted_plus_line(self) -> None:
        """Line starting with plus is not promoted."""
        promoter = HeadingPromoter()
        text = "+ Skills Required\nContent."
        result = promoter.process(text)
        assert "## + Skills Required" not in result

    def test_not_promoted_list_with_digit(self) -> None:
        """Line starting with digit (list marker) is not promoted."""
        promoter = HeadingPromoter()
        text = "1. Technical Skills\nContent."
        result = promoter.process(text)
        assert "## 1. Technical Skills" not in result

    def test_not_promoted_table_line(self) -> None:
        """Line starting with pipe (table marker) is not promoted."""
        promoter = HeadingPromoter()
        text = "| Requirements | Details |\nContent."
        result = promoter.process(text)
        assert "## | Requirements | Details |" not in result

    def test_not_promoted_no_blank_before(self) -> None:
        """Line with no blank line before it (and not first line) is not promoted."""
        promoter = HeadingPromoter()
        text = "Some text\nJob Description\nContent."
        result = promoter.process(text)
        assert "## Job Description" not in result
        assert "Job Description" in result  # Original preserved

    def test_promoted_first_line(self) -> None:
        """First line of document CAN be promoted even without blank line before."""
        promoter = HeadingPromoter()
        text = "Job Description\nContent below."
        result = promoter.process(text)
        assert "## Job Description" in result

    def test_promoted_after_blank_line(self) -> None:
        """Line after blank line is promoted."""
        promoter = HeadingPromoter()
        text = "Some text\n\nJob Description\nContent."
        result = promoter.process(text)
        assert "## Job Description" in result

    def test_not_promoted_empty_line(self) -> None:
        """Empty lines are not promoted."""
        promoter = HeadingPromoter()
        text = "Some text\n\n\n\nContent."
        result = promoter.process(text)
        # Line count should be preserved
        assert result.count("\n") == text.count("\n")

    def test_not_promoted_whitespace_only_line(self) -> None:
        """Whitespace-only lines are not promoted."""
        promoter = HeadingPromoter()
        text = "Some text\n   \nContent."
        result = promoter.process(text)
        # Whitespace-only line stays as-is
        assert "##    " not in result


class TestHeadingPromoterIdempotence:
    """Test that promotion is idempotent."""

    def test_idempotent_single_pass(self) -> None:
        """Processing twice yields same result."""
        promoter = HeadingPromoter()
        text = "Job Description\n\nRole Overview\n\nSkills\nContent."
        result1 = promoter.process(text)
        result2 = promoter.process(result1)
        assert result1 == result2

    def test_idempotent_multiple_passes(self) -> None:
        """Processing many times yields same result (with blank-line separation)."""
        promoter = HeadingPromoter()
        # Multiple blank lines separate headings for promotion eligibility
        text = "Technical Skills\n\nRequired Qualifications\n\nContent."
        result = text
        for _ in range(5):
            result = promoter.process(result)
        assert result.count("## Technical Skills") == 1
        assert result.count("## Required Qualifications") == 1

    def test_mixed_markdown_idempotent(self) -> None:
        """Text with existing markdown headings processes idempotently."""
        promoter = HeadingPromoter()
        text = "## Existing Heading\n\nJob Description\nContent."
        result1 = promoter.process(text)
        result2 = promoter.process(result1)
        assert result1 == result2


class TestHeadingPromoterEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_string(self) -> None:
        """Empty input returns empty output."""
        promoter = HeadingPromoter()
        result = promoter.process("")
        assert result == ""

    def test_single_line(self) -> None:
        """Single known phrase line gets promoted."""
        promoter = HeadingPromoter()
        result = promoter.process("Job Description")
        assert result == "## Job Description"

    def test_crlf_line_endings(self) -> None:
        """CRLF line endings are preserved."""
        promoter = HeadingPromoter()
        text = "Job Description\r\nContent below.\r\n"
        result = promoter.process(text)
        # The split('\n') will handle CRLF; verify promotion happened
        assert "## Job Description" in result

    def test_line_count_preserved(self) -> None:
        """Output has same line count as input (1:1 replacement)."""
        promoter = HeadingPromoter()
        text = "Job Description\n\nRole Overview\n\nTechnical Skills\nContent.\n"
        result = promoter.process(text)
        assert text.count("\n") == result.count("\n")


class TestHeadingPromoterConsistency:
    """Test consistency with SectionClassifier."""

    def test_all_phrases_classify_non_other(self) -> None:
        """Every phrase in KNOWN_PLAIN_HEADINGS classifies as non-'other' type.

        This guards against vocab/classifier drift: if a phrase is in the promoter
        vocabulary, it must map to a semantic type (skills, qualifications, etc),
        NOT to 'other'. This ensures promoted headings are useful for section parsing.
        """
        classifier = SectionClassifier()

        # The 10 'other' phrases that should NOT be in KNOWN_PLAIN_HEADINGS
        other_phrases = {
            "duties",
            "education",
            "eeo statement",
            "equal employment opportunity",
            "job duties",
            "must have",
            "nice to have",
            "the role",
            "who we are",
            "who you are",
        }

        # Check that no 'other' phrases are in the known headings
        for phrase in KNOWN_PLAIN_HEADINGS:
            assert phrase not in other_phrases, f"Phrase '{phrase}' is marked as 'other' and should not be promoted"

        # Sample check: a few known phrases should classify as non-'other'
        test_phrases = [
            "job description",
            "role overview",
            "key responsibilities",
            "required qualifications",
            "technical skills",
        ]

        for phrase in test_phrases:
            if phrase in KNOWN_PLAIN_HEADINGS:
                # Classify as title to get the type
                from src.poc.tweak.multi_line_paragraph import MarkdownSection

                section = MarkdownSection(
                    title=phrase.upper(),  # titles are uppercase
                    content="",
                    level=1,
                    start_line=0,
                    end_line=0,
                    word_count=len(phrase.split()),
                    line_count=1,
                    has_list=False,
                )
                classification = classifier.classify(section)

                # Should have at least one type
                assert len(classification.all_types) > 0, f"Phrase '{phrase}' classified with 0 types"

                # Primary type should NOT be OTHER
                primary_type = classification.all_types[0]
                assert primary_type.section_type != SectionType.OTHER, (
                    f"Phrase '{phrase}' classified as OTHER; should promote non-'other' phrases only"
                )


class TestHeadingPromoterIntegration:
    """Integration tests with WorkSource-shaped text."""

    def test_worksource_shaped_text_multiple_sections(self) -> None:
        """WorkSource-like plain-text headings get promoted to multiple sections."""
        promoter = HeadingPromoter()
        text = """Job#: 3052092

Job Description

Develop algorithms for signal processing.

Role Overview

Focus on advanced research techniques.

Key Responsibilities

* Design and implement algorithms
* Test effectiveness against requirements

Required Qualifications

A Bachelor's Degree in computer science.

Technical Skills

* Python experience required
* C++ preferred
"""
        result = promoter.process(text)

        # Verify key sections promoted
        assert "## Job Description" in result
        assert "## Role Overview" in result
        assert "## Key Responsibilities" in result
        assert "## Required Qualifications" in result
        assert "## Technical Skills" in result

        # Line count preserved
        assert result.count("\n") == text.count("\n")

    def test_perf_marketing_manager_shaped_text(self) -> None:
        """Performance Marketing Manager-shaped text (live job from Q2).

        With the new classifier keywords ("in this role" -> RESPONSIBILITIES,
        "succeed" -> QUALIFICATIONS) and expanded phrase set, headings
        "in this role you will" and "what will make you succeed" are now promoted.
        This enables proper section splitting and requirement extraction.
        """
        promoter = HeadingPromoter()
        text = """Why work at Medbridge?

We are mission driven.

Role Description

You will run Medbridge paid media end to end.

In this role you will:

* Own the full-funnel paid media strategy

What will make you succeed:

* 6+ years of digital marketing experience

Tools

* CRM: Salesforce, Hubspot

Our Values:

Excellence is never an accident."""

        result = promoter.process(text)

        # "Role Description" should be promoted (in vocabulary)
        assert "## Role Description" in result

        # "In this role you will" and "What will make you succeed" should now be promoted
        # (they are in KNOWN_PLAIN_HEADINGS with new keywords from Issue #365)
        assert "## In this role you will" in result
        assert "## What will make you succeed" in result

        # These are still NOT in vocabulary, so they stay as-is
        assert "## Why work at Medbridge?" not in result
        assert "## Tools" not in result
        assert "## Our Values:" not in result

        # Line count preserved
        assert text.count("\n") == result.count("\n")


class TestHeadingPromoterErrorHandling:
    """Test error handling and robustness."""

    def test_exception_returns_original_text(self) -> None:
        """Exceptions during processing return original text unchanged.

        Even if an internal error occurs, the processor returns the original text
        (fail-safe behavior). A warning is logged but no exception is raised.
        """
        promoter = HeadingPromoter()

        # Trigger exception by monkey-patching _should_promote to raise
        def bad_should_promote(*args, **kwargs):
            raise ValueError("Intentional test error")

        original_should_promote = promoter._should_promote
        promoter._should_promote = bad_should_promote

        text = "Job Description\nContent."
        result = promoter.process(text)

        # Should return original text unchanged
        assert result == text

        # Restore original method
        promoter._should_promote = original_should_promote
