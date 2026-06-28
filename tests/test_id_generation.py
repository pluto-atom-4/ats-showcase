"""Tests for job ID generation module."""

import pytest

from src.id_generation import generate_job_id
from src.id_generation.url_utils import clean_canonical_url, detect_portal, extract_portal_id


class TestUrlUtils:
    """Test URL utility functions."""

    def test_detect_portal_greenhouse(self):
        """Detect Greenhouse from URL."""
        url = "https://job-boards.greenhouse.io/embed/job_board?for=carbonrobotics"
        assert detect_portal(url) == "greenhouse"

        url2 = "https://carbonrobotics.greenhouse.io/jobs"
        assert detect_portal(url2) == "greenhouse"

    def test_detect_portal_workday(self):
        """Detect Workday from URL."""
        url = "https://boeing.wd1.myworkdayjobs.com/en-US/EXTERNAL_CAREERS"
        assert detect_portal(url) == "workday"

        url2 = "https://company.myworkdayjobs.com/careers"
        assert detect_portal(url2) == "workday"

    def test_detect_portal_lever(self):
        """Detect Lever from URL."""
        url = "https://company.lever.co/jobs"
        assert detect_portal(url) == "lever"

    def test_detect_portal_custom(self):
        """Detect custom portal (non-standard)."""
        url = "https://example.com/careers"
        assert detect_portal(url) == "custom"

    def test_extract_portal_id_greenhouse(self):
        """Extract Greenhouse job ID from URL."""
        url = "https://carbonrobotics.com/job-openings?gh_jid=4673637006"
        job_id = extract_portal_id(url)
        assert job_id == "4673637006"

    def test_extract_portal_id_path(self):
        """Extract job ID from URL path."""
        url = "https://company.com/jobs/view/12345678"
        job_id = extract_portal_id(url)
        assert job_id == "12345678"

    def test_extract_portal_id_none(self):
        """Return None if no portal ID found."""
        url = "https://company.com/careers"
        assert extract_portal_id(url) is None

    def test_clean_canonical_url(self):
        """Strip query params and fragments from URL."""
        url = "https://example.com/jobs?gh_jid=123&utm_source=indeed#top"
        clean = clean_canonical_url(url)
        assert clean == "https://example.com/jobs"
        assert "?" not in clean
        assert "#" not in clean

    def test_clean_canonical_url_preserves_path(self):
        """Preserve URL path when cleaning."""
        url = "https://example.com/en-US/careers/jobs?id=123"
        clean = clean_canonical_url(url)
        assert "/en-US/careers/jobs" in clean


class TestIdGeneration:
    """Test deterministic job ID generation."""

    def test_deterministic_same_inputs_same_id(self):
        """Same inputs always produce same ID."""
        id1 = generate_job_id(
            company="Stripe",
            title="Senior Engineer",
            location="San Francisco, CA",
            url="https://stripe.com/jobs/123",
        )
        id2 = generate_job_id(
            company="Stripe",
            title="Senior Engineer",
            location="San Francisco, CA",
            url="https://stripe.com/jobs/123",
        )
        assert id1 == id2

    def test_id_format_correct(self):
        """Generated ID has correct format: {portal}:{hash[:16]}."""
        job_id = generate_job_id(
            company="TestCorp",
            title="Engineer",
            location="Remote",
            url="https://testcorp.com/jobs",
        )
        parts = job_id.split(":")
        assert len(parts) == 2
        portal, hash_part = parts
        assert portal == "custom"
        assert len(hash_part) == 16
        assert hash_part.isalnum()

    def test_id_changes_with_title_change(self):
        """ID changes when title changes (not stable across edits)."""
        id1 = generate_job_id(
            company="Stripe",
            title="Backend Engineer",
            location="San Francisco, CA",
            url="https://stripe.com/jobs/123",
        )
        id2 = generate_job_id(
            company="Stripe",
            title="Senior Backend Engineer",
            location="San Francisco, CA",
            url="https://stripe.com/jobs/123",
        )
        assert id1 != id2

    def test_id_changes_with_location_change(self):
        """ID changes when location changes."""
        id1 = generate_job_id(
            company="Stripe",
            title="Engineer",
            location="San Francisco, CA",
            url="https://stripe.com/jobs/123",
        )
        id2 = generate_job_id(
            company="Stripe",
            title="Engineer",
            location="New York, NY",
            url="https://stripe.com/jobs/123",
        )
        assert id1 != id2

    def test_id_same_with_whitespace_variations(self):
        """ID ignores whitespace variations (normalized)."""
        id1 = generate_job_id(
            company="Stripe Inc.",
            title="Senior   Engineer",
            location="San Francisco, CA",
            url="https://stripe.com/jobs/123",
        )
        id2 = generate_job_id(
            company="Stripe Inc.",
            title="Senior Engineer",
            location="San Francisco, CA",
            url="https://stripe.com/jobs/123",
        )
        assert id1 == id2

    def test_greenhouse_portal_detection(self):
        """Detect Greenhouse portal and use in ID."""
        job_id = generate_job_id(
            company="CarbonRobotics",
            title="ML Engineer",
            location="Seattle, WA",
            url="https://carbonrobotics.com/jobs?gh_jid=4673637006",
        )
        assert job_id.startswith("greenhouse:")

    def test_workday_portal_detection(self):
        """Detect Workday portal and use in ID."""
        job_id = generate_job_id(
            company="Boeing",
            title="Systems Engineer",
            location="Seattle, WA",
            url="https://boeing.wd1.myworkdayjobs.com/en-US/jobs/123456",
        )
        assert job_id.startswith("workday:")

    def test_id_with_special_characters_in_company(self):
        """Handle special characters in company name (normalized)."""
        id1 = generate_job_id(
            company="3M Company",
            title="Engineer",
            location="Minnesota",
            url="https://3m.com/jobs",
        )
        id2 = generate_job_id(
            company="3M-Company",
            title="Engineer",
            location="Minnesota",
            url="https://3m.com/jobs",
        )
        assert id1 == id2

    def test_id_without_url(self):
        """Generate ID without URL (uses company as fallback)."""
        job_id = generate_job_id(
            company="Stripe",
            title="Engineer",
            location="Remote",
            url=None,
        )
        assert ":" in job_id
        assert len(job_id.split(":")[1]) == 16

    def test_id_with_empty_location(self):
        """Handle empty location string."""
        id1 = generate_job_id(
            company="Stripe",
            title="Engineer",
            location="",
            url="https://stripe.com/jobs",
        )
        id2 = generate_job_id(
            company="Stripe",
            title="Engineer",
            location="Remote",
            url="https://stripe.com/jobs",
        )
        assert id1 != id2

    def test_portal_parameter_override(self):
        """Explicit portal parameter overrides detection."""
        job_id = generate_job_id(
            company="TestCorp",
            title="Engineer",
            location="Remote",
            url="https://testcorp.com/jobs",
            portal="custom_ats",
        )
        assert job_id.startswith("custom_ats:")

    def test_id_stability_across_runs(self):
        """ID remains stable for same job across multiple generations."""
        company = "TechCorp"
        title = "Software Engineer"
        location = "Mountain View, CA"
        url = "https://techcorp.com/careers/jobs/sf-engineer-001"

        ids = [
            generate_job_id(company, title, location, url)
            for _ in range(5)
        ]

        assert len(set(ids)) == 1, "ID should be identical across runs"

    def test_greenhouse_portal_id_in_hash(self):
        """Greenhouse portal ID is extracted and used in hash."""
        # Two different URLs with same gh_jid should have same ID
        id1 = generate_job_id(
            company="Company",
            title="Engineer",
            location="Remote",
            url="https://company.com/jobs?gh_jid=12345678",
        )
        id2 = generate_job_id(
            company="Company",
            title="Engineer",
            location="Remote",
            url="https://greenhouse.io/jobs?gh_jid=12345678",
        )
        # Should be same because portal ID is the anchor
        assert id1 == id2
