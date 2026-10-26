"""Tests for job ID generation module."""

import pytest

from src.id_generation import generate_job_id
from src.id_generation.url_utils import (
    canonical_url_with_query_keys,
    clean_canonical_url,
    detect_portal,
    extract_portal_id,
)


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

    def test_clean_canonical_url_unchanged_drops_all_query_keys(self):
        """clean_canonical_url still drops every query param, including jobId."""
        url = "https://example.com/careers?jobId=42&gh_jid=7#apply"
        assert clean_canonical_url(url) == "https://example.com/careers"


class TestCanonicalUrlWithQueryKeys:
    """Test query-key-preserving canonicalization (custom portal anchor)."""

    def test_keeps_jobid_drops_other_params(self):
        """Only the listed key survives; other params are dropped."""
        url = "https://example.com/careers?utm_source=indeed&jobId=12345&ref=abc"
        assert canonical_url_with_query_keys(url, ["jobId"]) == ("https://example.com/careers?jobId=12345")

    def test_drops_fragment(self):
        """Fragment is always dropped."""
        url = "https://example.com/careers?jobId=9#apply-now"
        assert canonical_url_with_query_keys(url, ["jobId"]) == ("https://example.com/careers?jobId=9")

    def test_missing_key_yields_no_query(self):
        """If the listed key is absent, result has path only."""
        url = "https://example.com/careers?utm_source=indeed"
        assert canonical_url_with_query_keys(url, ["jobId"]) == "https://example.com/careers"

    def test_empty_keys_matches_clean_canonical_url(self):
        """No keys means behaviour matches clean_canonical_url."""
        url = "https://example.com/jobs?jobId=1#top"
        assert canonical_url_with_query_keys(url, []) == clean_canonical_url(url)

    def test_empty_url(self):
        """Empty URL returns empty string."""
        assert canonical_url_with_query_keys("", ["jobId"]) == ""

    def test_different_job_ids_stay_distinct(self):
        """Two jobs on the same path with different jobId get different anchors."""
        a = canonical_url_with_query_keys("https://example.com/careers?jobId=1", ["jobId"])
        b = canonical_url_with_query_keys("https://example.com/careers?jobId=2", ["jobId"])
        assert a != b


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

        ids = [generate_job_id(company, title, location, url) for _ in range(5)]

        assert len(set(ids)) == 1, "ID should be identical across runs"

    def test_greenhouse_portal_id_in_hash(self):
        """Greenhouse portal ID is extracted and used in hash."""
        # Same gh_jid on different hosts -> same ID (portal ID is the anchor).
        same_1 = generate_job_id(
            company="Company",
            title="Engineer",
            location="Remote",
            url="https://company.com/jobs?gh_jid=12345678",
        )
        same_2 = generate_job_id(
            company="Company",
            title="Engineer",
            location="Remote",
            url="https://greenhouse.io/jobs?gh_jid=12345678",
        )
        assert same_1 == same_2
        # Different gh_jid on the same company/title/location -> different IDs.
        diff_1 = generate_job_id(
            company="Company",
            title="Engineer",
            location="Remote",
            url="https://company.com/jobs?gh_jid=11111111",
        )
        diff_2 = generate_job_id(
            company="Company",
            title="Engineer",
            location="Remote",
            url="https://company.com/jobs?gh_jid=22222222",
        )
        assert diff_1 != diff_2

    def test_generate_job_id_distinct_for_worksource_search_urls(self):
        """WorkSource search URLs differing only by jobId get distinct ids (#736/#763)."""
        id1 = generate_job_id(
            company="WorkSource",
            title="Warehouse Associate",
            location="Spokane, WA",
            url="https://my.site.com/search?jobId=MuW5N",
        )
        id2 = generate_job_id(
            company="WorkSource",
            title="Warehouse Associate",
            location="Spokane, WA",
            url="https://my.site.com/search?jobId=MuTqf",
        )
        assert id1 != id2


class TestCustomPortalJobIdAnchor:
    """Custom-portal jobId is the id discriminator (#763); other portals unchanged."""

    @staticmethod
    def _gen(url, title="Warehouse Associate", location="Spokane, WA", portal=None):
        return generate_job_id(
            company="WorkSource",
            title=title,
            location=location,
            url=url,
            portal=portal,
        )

    def test_custom_portal_distinct_jobid_distinct_ids(self):
        """Custom portal: different jobId -> different ids."""
        id1 = self._gen("https://my.site.com/search?jobId=AAA111")
        id2 = self._gen("https://my.site.com/search?jobId=BBB222")
        assert id1 != id2
        assert id1.startswith("custom:")
        assert id2.startswith("custom:")

    def test_custom_portal_same_jobid_other_params_same_id(self):
        """Custom portal: same jobId, different other params/fragment -> same id."""
        id1 = self._gen("https://my.site.com/search?jobId=AAA111&utm_source=indeed")
        id2 = self._gen("https://my.site.com/search?ref=zzz&jobId=AAA111#apply")
        id3 = self._gen("https://my.site.com/search?jobId=AAA111")
        assert id1 == id2 == id3

    def test_custom_portal_without_jobid_falls_back(self):
        """Custom portal without jobId keeps existing query-stripping behavior."""
        url_a = "https://example.com/careers?utm_source=indeed"
        url_b = "https://example.com/careers?utm_source=linkedin"
        # Existing behavior: query stripped, so the two URLs share an anchor.
        assert self._gen(url_a) == self._gen(url_b)
        # Matches the pre-#763 result: anchor == clean_canonical_url(url).
        expected = generate_job_id(
            company="WorkSource",
            title="Warehouse Associate",
            location="Spokane, WA",
            url="https://example.com/careers",
        )
        assert self._gen(url_a) == expected

    def test_custom_portal_empty_jobid_falls_back(self):
        """Empty jobId value is treated as absent -> existing behavior."""
        assert self._gen("https://example.com/careers?jobId=") == self._gen("https://example.com/careers?jobId=&x=1")
        assert self._gen("https://example.com/careers?jobId=") == generate_job_id(
            company="WorkSource",
            title="Warehouse Associate",
            location="Spokane, WA",
            url="https://example.com/careers",
        )

    def test_custom_portal_jobid_wins_over_numeric_path(self):
        """Custom portal jobId anchor applies even when path carries an 8-15 digit id."""
        id1 = self._gen("https://example.com/jobs/12345678/apply?jobId=A1")
        id2 = self._gen("https://example.com/jobs/12345678/apply?jobId=B2")
        assert id1 != id2

    def test_non_custom_portal_ignores_jobid_discriminator(self):
        """Non-custom portals keep query-stripping: jobId does not split ids."""
        # Greenhouse: anchor is gh_jid, unchanged by jobId.
        g1 = generate_job_id(
            company="Co",
            title="Engineer",
            location="Remote",
            url="https://job-boards.greenhouse.io/co/jobs?gh_jid=12345678&jobId=1",
        )
        g2 = generate_job_id(
            company="Co",
            title="Engineer",
            location="Remote",
            url="https://job-boards.greenhouse.io/co/jobs?gh_jid=12345678&jobId=2",
        )
        assert g1 == g2
        # Explicit non-custom portal name with jobId: query stripped, ids collide.
        p1 = generate_job_id(
            company="Co",
            title="Engineer",
            location="Remote",
            url="https://example.com/careers?jobId=1",
            portal="custom_ats",
        )
        p2 = generate_job_id(
            company="Co",
            title="Engineer",
            location="Remote",
            url="https://example.com/careers?jobId=2",
            portal="custom_ats",
        )
        assert p1 == p2
        assert p1.startswith("custom_ats:")


class TestAnchorOverwrite768:
    """Extracted portal id must survive the anchor chain (#768)."""

    @staticmethod
    def _gen(url, company="Acme", title="Engineer", location="Remote"):
        return generate_job_id(company=company, title=title, location=location, url=url)

    def test_digit_path_id_distinct_ids_distinct(self):
        """Same company/title/location, different 8-15 digit path id -> different ids."""
        id1 = self._gen("https://acme.wd1.myworkdayjobs.com/job/12345678")
        id2 = self._gen("https://acme.wd1.myworkdayjobs.com/job/87654321")
        assert id1 != id2

    def test_custom_portal_digit_path_anchors_on_digit_id(self):
        """Custom portal, digit path, no jobId: anchor is the digit id (behavior change)."""
        id1 = self._gen("https://example.com/jobs/12345678")
        id2 = self._gen("https://example.com/jobs/87654321")
        assert id1 != id2
        # Anchor is the extracted digit id, not the normalized company.
        assert id1 != generate_job_id(company="Acme", title="Engineer", location="Remote", url=None)

    def test_url_none_uses_company_anchor(self):
        """url=None keeps norm_company anchor (unchanged)."""
        assert self._gen(None) == generate_job_id(company="Acme", title="Engineer", location="Remote", url=None)
        assert self._gen(None).startswith("custom:")
