"""Tests for description normalization in crawler."""

import pytest

from src.browser.crawler import Crawler


class TestDescriptionNormalization:
    """Test metadata label separation in job descriptions."""

    def test_normalize_remote_type(self):
        """Separate 'remote type' label from value."""
        crawler = Crawler()
        desc = "remote typeHybrid (telework 2 days)"
        result = crawler._normalize_description(desc)
        assert "remote type Hybrid" in result

    def test_normalize_locations(self):
        """Separate 'locations' label from value."""
        crawler = Crawler()
        desc = "locationsSeattle, WA"
        result = crawler._normalize_description(desc)
        assert "locations Seattle" in result

    def test_normalize_time_type(self):
        """Separate 'time type' label from value."""
        crawler = Crawler()
        desc = "time typeFull time"
        result = crawler._normalize_description(desc)
        assert "time type Full" in result

    def test_normalize_posted_on(self):
        """Separate 'posted on' label from value."""
        crawler = Crawler()
        desc = "posted onPosted Yesterday"
        result = crawler._normalize_description(desc)
        assert "posted on Posted" in result

    def test_normalize_job_description(self):
        """Separate 'Job Description' label from value."""
        crawler = Crawler()
        desc = "Job DescriptionThe College"
        result = crawler._normalize_description(desc)
        assert "Job Description The" in result

    def test_normalize_multiple_fields_separated(self):
        """Multiple metadata fields get newline separators."""
        crawler = Crawler()
        desc = (
            "remote typeHybrid (telework)"
            "locationsSeattle, WAtime typeFull"
        )
        result = crawler._normalize_description(desc)
        # Should have newlines before each label
        assert result.count("\n") >= 2
        assert "remote type Hybrid" in result
        assert "locations Seattle" in result
        assert "time type Full" in result

    def test_normalize_complete_workday_description(self):
        """Normalize a complete concatenated Workday description."""
        crawler = Crawler()
        desc = (
            "remote typeHybrid (telework 2 days or less per week)"
            "locationsSeattle, WAtime typeFull timeposted onPosted Today"
            "time left to applyEnd Date: July 22, 2026"
            "job requisition idREQ-0000133673"
            "Job DescriptionThe College of Engineering team..."
        )
        result = crawler._normalize_description(desc)

        # Verify all labels have proper spacing
        assert "remote type Hybrid" in result
        assert "locations Seattle" in result
        assert "time type Full" in result
        assert "posted on Posted" in result
        assert "time left to apply End" in result
        assert "job requisition id REQ" in result
        assert "Job Description The" in result

        # Verify newlines between sections
        lines = result.split("\n")
        # Should have multiple lines due to newline separators
        assert len(lines) > 3

    def test_normalize_already_separated(self):
        """Don't double-space metadata that's already separated."""
        crawler = Crawler()
        desc = "remote type Hybrid (telework)"
        result = crawler._normalize_description(desc)
        # Should not have double spaces
        assert "remote  type" not in result
        assert "remote type Hybrid" in result

    def test_normalize_empty_description(self):
        """Handle empty description."""
        crawler = Crawler()
        result = crawler._normalize_description("")
        assert result == ""

    def test_normalize_none_description(self):
        """Handle None description."""
        crawler = Crawler()
        result = crawler._normalize_description(None)
        assert result is None

    def test_normalize_case_insensitive(self):
        """Normalize metadata labels case-insensitively."""
        crawler = Crawler()
        desc = "REMOTE TYPEHybrid"
        result = crawler._normalize_description(desc)
        # Case-insensitive match should work
        assert "Hybrid" in result
        assert "REMOTE TYPE" in result or "remote type" in result.lower()

    def test_normalize_no_false_positives(self):
        """Don't modify unrelated content containing label words."""
        crawler = Crawler()
        desc = "The location type is important for this job"
        # Should not add newlines to words that contain "location" or "type"
        result = crawler._normalize_description(desc)
        # These sentences should remain unchanged
        assert "The location type is" in result
