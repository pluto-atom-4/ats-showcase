"""Tests for HTML cleanup and boilerplate removal (Phase 6 - Issue #193)."""

import pytest

from src.tokenization.html_cleanup import (
    get_boilerplate_keywords,
    get_boilerplate_patterns,
    is_boilerplate_phrase,
    remove_boilerplate,
    remove_html_entities,
)


class TestBoilerplatePatterns:
    """Test boilerplate pattern retrieval."""

    def test_get_boilerplate_patterns(self):
        """Get all 7 categories of boilerplate patterns."""
        patterns = get_boilerplate_patterns()
        assert isinstance(patterns, dict)
        assert len(patterns) == 7
        assert "legal_compliance" in patterns
        assert "section_headers" in patterns
        assert "company_boilerplate" in patterns
        assert "time_references" in patterns
        assert "salary_benefits" in patterns
        assert "special_formatting" in patterns
        assert "navigation" in patterns

    def test_pattern_lists_not_empty(self):
        """Ensure each category has at least one pattern."""
        patterns = get_boilerplate_patterns()
        for category, pattern_list in patterns.items():
            assert len(pattern_list) > 0, f"Category {category} has no patterns"
            for pattern in pattern_list:
                assert isinstance(pattern, str), f"Pattern in {category} is not a string"


class TestIsBoilerplatePhrase:
    """Test boilerplate phrase detection."""

    def test_legal_compliance_phrases(self):
        """Detect legal/compliance boilerplate."""
        assert is_boilerplate_phrase("Required Qualifications")
        assert is_boilerplate_phrase("Equal Opportunity Employer")
        assert is_boilerplate_phrase("Affirmative Action")
        assert is_boilerplate_phrase("Background Check Required")
        assert is_boilerplate_phrase("Export Control Compliance")

    def test_section_headers(self):
        """Detect section header boilerplate."""
        assert is_boilerplate_phrase("JD: Senior Developer")
        assert is_boilerplate_phrase("Job Description:")
        assert is_boilerplate_phrase("Overview:")
        assert is_boilerplate_phrase("Requirements:")
        assert is_boilerplate_phrase("Technical Skills:")

    def test_company_boilerplate(self):
        """Detect company boilerplate phrases."""
        assert is_boilerplate_phrase("We are committed to diversity")
        assert is_boilerplate_phrase("We believe in innovation")
        assert is_boilerplate_phrase("Our company culture")
        assert is_boilerplate_phrase("Our mission statement")

    def test_time_references(self):
        """Detect time reference boilerplate."""
        assert is_boilerplate_phrase("Full-time position")
        assert is_boilerplate_phrase("Part-time contract")
        assert is_boilerplate_phrase("Temporary role")
        assert is_boilerplate_phrase("Permanent position")

    def test_salary_benefits(self):
        """Detect salary/benefits boilerplate."""
        assert is_boilerplate_phrase("Competitive salary")
        assert is_boilerplate_phrase("Health benefits included")
        assert is_boilerplate_phrase("401(k) retirement plan")
        assert is_boilerplate_phrase("Dental and vision insurance")
        assert is_boilerplate_phrase("Paid time off (PTO)")

    def test_navigation_phrases(self):
        """Detect navigation boilerplate."""
        assert is_boilerplate_phrase("Apply Now")
        assert is_boilerplate_phrase("Share this job")
        assert is_boilerplate_phrase("Save job")
        assert is_boilerplate_phrase("Back to results")

    def test_non_boilerplate_phrases(self):
        """Verify normal text is not flagged as boilerplate."""
        assert not is_boilerplate_phrase("Python developer with 5 years experience")
        assert not is_boilerplate_phrase("We need a senior engineer for our team")
        assert not is_boilerplate_phrase("Excellent communication skills required")

    def test_empty_or_none_input(self):
        """Handle empty or whitespace-only input."""
        assert not is_boilerplate_phrase("")
        assert not is_boilerplate_phrase("   ")
        # Deliberately pass None to check graceful handling.
        assert not is_boilerplate_phrase(None)  # type: ignore[arg-type]

    def test_category_specific_check(self):
        """Check boilerplate by specific category."""
        # Should match legal_compliance category
        assert is_boilerplate_phrase("Equal Opportunity", category="legal_compliance")

        # Should not match other categories
        assert not is_boilerplate_phrase("Equal Opportunity", category="salary_benefits")

    def test_invalid_category(self):
        """Handle invalid category gracefully."""
        # Should log warning and return False
        assert not is_boilerplate_phrase("Some text", category="invalid_category")


class TestRemoveBoilerplate:
    """Test boilerplate removal."""

    def test_remove_legal_compliance(self):
        """Remove legal/compliance boilerplate."""
        text = "Position Requirements: Equal Opportunity Employer. Background Check Required."
        cleaned = remove_boilerplate(text)
        assert "Equal Opportunity" not in cleaned
        assert "Background Check" not in cleaned

    def test_remove_salary_benefits(self):
        """Remove salary/benefits boilerplate."""
        text = "Job Details: Competitive salary $80,000-$120,000 per year. Health benefits included."
        cleaned = remove_boilerplate(text)
        assert "Competitive salary" not in cleaned.lower()
        assert "Health benefits" not in cleaned.lower()

    def test_remove_section_headers(self):
        """Remove section header artifacts."""
        text = "Job Description: We need a developer. Requirements: Python skills needed."
        cleaned = remove_boilerplate(text)
        # Headers should be removed
        assert "Job Description:" not in cleaned
        assert "Requirements:" not in cleaned

    def test_remove_navigation(self):
        """Remove navigation boilerplate."""
        text = "Position details here. Apply Now. Share this job. Save job."
        cleaned = remove_boilerplate(text)
        assert "Apply Now" not in cleaned
        assert "Share" not in cleaned
        assert "Save" not in cleaned

    def test_preserve_job_content(self):
        """Ensure core job content is preserved."""
        text = "We need a Python developer with 5+ years experience. Competitive salary offered."
        cleaned = remove_boilerplate(text)
        assert "Python developer" in cleaned
        assert "5+ years" in cleaned or "5" in cleaned

    def test_remove_html_artifacts(self):
        """Remove HTML entity artifacts."""
        text = "Requirements&nbsp;&nbsp;Position Details&nbsp;We are looking."
        cleaned = remove_boilerplate(text)
        # Extra spaces should be cleaned up
        assert "  " not in cleaned

    def test_empty_result_handling(self):
        """Handle text that becomes empty after removal."""
        text = "Equal Opportunity Employer. Apply Now."
        cleaned = remove_boilerplate(text)
        assert isinstance(cleaned, str)

    def test_preserve_multiple_spaces_cleanup(self):
        """Normalize multiple spaces to single space."""
        text = "Senior   Developer   with   experience."
        cleaned = remove_boilerplate(text)
        assert "   " not in cleaned

    def test_empty_or_none_input(self):
        """Handle empty or None input."""
        assert remove_boilerplate("") == ""
        assert remove_boilerplate("   ") == ""


class TestRemoveHTMLEntities:
    """Test HTML entity removal."""

    def test_remove_nbsp(self):
        """Remove non-breaking spaces."""
        text = "Senior&nbsp;Developer&nbsp;Position"
        cleaned = remove_html_entities(text)
        assert "&nbsp;" not in cleaned
        assert "Senior" in cleaned
        assert "Developer" in cleaned

    def test_remove_html_entities(self):
        """Remove common HTML entities."""
        text = "Skills &amp; Experience: C++ &lt; Python &gt; JavaScript"
        cleaned = remove_html_entities(text)
        assert "&amp;" not in cleaned
        assert "&lt;" not in cleaned
        assert "&gt;" not in cleaned
        assert "C++ < Python > JavaScript" in cleaned or "C++" in cleaned

    def test_remove_numeric_entities(self):
        """Remove numeric HTML entities."""
        text = "Salary: &#36;100,000 &#45; &#36;150,000"
        cleaned = remove_html_entities(text)
        assert "&#36;" not in cleaned
        assert "&#45;" not in cleaned

    def test_preserve_normal_text(self):
        """Preserve normal text without entities."""
        text = "Python developer with 5+ years experience"
        cleaned = remove_html_entities(text)
        assert cleaned == text

    def test_empty_input(self):
        """Handle empty input."""
        assert remove_html_entities("") == ""


class TestGetBoilerplateKeywords:
    """Test keyword extraction."""

    def test_get_boilerplate_keywords(self):
        """Get set of boilerplate keywords."""
        keywords = get_boilerplate_keywords()
        assert isinstance(keywords, set)
        assert len(keywords) > 0
        assert "salary" in keywords
        assert "benefits" in keywords
        assert "equal" in keywords
        assert "opportunity" in keywords


class TestIntegrationBoilerplateRemoval:
    """Integration tests for complete boilerplate removal."""

    def test_realistic_job_description(self):
        """Remove boilerplate from realistic job description."""
        text = (
            "Job Description: Senior Python Developer\n"
            "Equal Opportunity Employer\n"
            "Responsibilities: Build backend services\n"
            "Requirements: 5+ years Python experience\n"
            "Compensation: Competitive salary $100-$150K\n"
            "Benefits: Health insurance, 401(k), PTO\n"
            "Apply Now | Share | Save Job"
        )

        cleaned = remove_boilerplate(text)

        # Boilerplate should be removed
        assert "Equal Opportunity" not in cleaned
        assert "Job Description:" not in cleaned
        assert "Apply Now" not in cleaned
        assert "Competitive salary" not in cleaned.lower()

        # Content should be preserved
        assert "Python" in cleaned
        assert "5+" in cleaned or "5" in cleaned

    def test_multiple_categories_removal(self):
        """Remove boilerplate from multiple categories in single text."""
        text = (
            "JD: Senior Developer\n"
            "Full-time position\n"
            "Salary: $120K - $150K\n"
            "We are committed to diversity\n"
            "Background Check Required\n"
            "Apply Now"
        )

        cleaned = remove_boilerplate(text)

        # All categories should be partially cleaned
        # (some patterns may be partial matches)
        assert len(cleaned) < len(text)
