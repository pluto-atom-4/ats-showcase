"""Tests for job description extraction from detail pages (Issue #309).

Tests adaptive retry logic, selector waiting, iframe extraction, and graceful
fallback patterns.
"""

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.poc.tweak.crawl_details import (
    extract_description_from_detail_page,
    fetch_job_details,
    selector_present,
)

# ============================================================================
# TESTS: selector_present()
# ============================================================================


class TestSelectorPresent:
    """Tests for selector_present() helper function."""

    @pytest.mark.asyncio
    async def test_selector_present_success(self):
        """selector_present() returns True when selector found."""
        mock_page = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()

        result = await selector_present(mock_page, "div.job-desc", timeout_ms=1000)

        assert result is True
        mock_page.wait_for_selector.assert_called_once_with("div.job-desc", timeout=1000)

    @pytest.mark.asyncio
    async def test_selector_present_timeout(self):
        """selector_present() returns False when selector times out."""
        mock_page = AsyncMock()
        mock_page.wait_for_selector = AsyncMock(side_effect=TimeoutError("timeout"))

        result = await selector_present(mock_page, "div.job-desc", timeout_ms=500)

        assert result is False

    @pytest.mark.asyncio
    async def test_selector_present_none_selector(self):
        """selector_present() returns False when selector is None."""
        mock_page = AsyncMock()

        result = await selector_present(mock_page, None, timeout_ms=1000)

        assert result is False
        mock_page.wait_for_selector.assert_not_called()

    @pytest.mark.asyncio
    async def test_selector_present_generic_exception(self):
        """selector_present() returns False on any exception."""
        mock_page = AsyncMock()
        mock_page.wait_for_selector = AsyncMock(side_effect=RuntimeError("page error"))

        result = await selector_present(mock_page, "div.job-desc", timeout_ms=1000)

        assert result is False


# ============================================================================
# TESTS: fetch_job_details() - Adaptive Retry Loop
# ============================================================================


class TestFetchJobDetailsRetryLogic:
    """Tests for adaptive retry loop (3 attempts with increasing timeouts)."""

    @pytest.mark.asyncio
    async def test_fetch_job_details_success_first_attempt(self):
        """Job details extracted on first attempt."""
        job = {
            "id": "job1",
            "title": "Engineer",
            "company": "Acme",
            "url": "https://example.com/job1",
        }

        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)

        # Mock retry_goto to succeed
        with patch("src.poc.tweak.crawl_details.retry_goto", new_callable=AsyncMock) as mock_retry:
            mock_retry.return_value = True

            # Mock selector_present to find selector
            with patch("src.poc.tweak.crawl_details.selector_present", new_callable=AsyncMock) as mock_sel:
                mock_sel.return_value = True

                # Mock extraction to return description
                with patch(
                    "src.poc.tweak.crawl_details.extract_description_from_detail_page",
                    new_callable=AsyncMock,
                ) as mock_extract:
                    mock_extract.return_value = "<p>Job description</p>"

                    with patch("src.poc.tweak.crawl_details.resolve_company_selectors") as mock_resolve:
                        mock_resolve.return_value = {"description_selector": "div.job-desc"}

                        result = await fetch_job_details(mock_browser, job, {"Acme": {}})

        assert result["description"] == "<p>Job description</p>"
        mock_page.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_job_details_success_third_attempt(self):
        """Job details extracted on third attempt after initial failures."""
        job = {
            "id": "job2",
            "title": "Developer",
            "company": "Acme",
            "url": "https://example.com/job2",
        }

        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)

        with patch("src.poc.tweak.crawl_details.retry_goto", new_callable=AsyncMock) as mock_retry:
            mock_retry.return_value = True

            # First two attempts: selector not found
            # Third attempt: selector found
            with patch("src.poc.tweak.crawl_details.selector_present", new_callable=AsyncMock) as mock_sel:
                mock_sel.side_effect = [False, False, True]

                with patch(
                    "src.poc.tweak.crawl_details.extract_description_from_detail_page",
                    new_callable=AsyncMock,
                ) as mock_extract:
                    mock_extract.return_value = "<p>Description</p>"

                    with patch("src.poc.tweak.crawl_details.resolve_company_selectors") as mock_resolve:
                        mock_resolve.return_value = {"description_selector": "div.job-desc"}

                        result = await fetch_job_details(mock_browser, job, {"Acme": {}})

        assert result["description"] == "<p>Description</p>"
        # selector_present called 3 times for 3 attempts
        assert mock_sel.call_count == 3

    @pytest.mark.asyncio
    async def test_fetch_job_details_all_attempts_fail(self):
        """No description extracted after 3 failed attempts."""
        job = {
            "id": "job3",
            "title": "QA",
            "company": "Acme",
            "url": "https://example.com/job3",
        }

        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)

        with patch("src.poc.tweak.crawl_details.retry_goto", new_callable=AsyncMock) as mock_retry:
            mock_retry.return_value = True

            # All attempts: selector not found
            with patch("src.poc.tweak.crawl_details.selector_present", new_callable=AsyncMock) as mock_sel:
                mock_sel.return_value = False

                with patch("src.poc.tweak.crawl_details.resolve_company_selectors") as mock_resolve:
                    mock_resolve.return_value = {"description_selector": "div.job-desc"}

                    result = await fetch_job_details(mock_browser, job, {"Acme": {}})

        assert result["description"] == ""
        assert mock_sel.call_count == 3

    @pytest.mark.asyncio
    async def test_fetch_job_details_retry_timeouts_escalate(self):
        """Each retry attempt uses escalating timeout (500 → 1000 → 2000 ms)."""
        job = {
            "id": "job4",
            "title": "Manager",
            "company": "Acme",
            "url": "https://example.com/job4",
        }

        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)

        with patch("src.poc.tweak.crawl_details.retry_goto", new_callable=AsyncMock) as mock_retry:
            mock_retry.return_value = True

            with patch("src.poc.tweak.crawl_details.selector_present", new_callable=AsyncMock) as mock_sel:
                mock_sel.return_value = False

                with patch("src.poc.tweak.crawl_details.resolve_company_selectors") as mock_resolve:
                    mock_resolve.return_value = {"description_selector": "div.job-desc"}

                    _ = await fetch_job_details(mock_browser, job, {"Acme": {}})

            # Extract timeout values from calls using positional args
            # selector_present(page, selector, timeout_ms)
            calls = mock_sel.call_args_list
            assert len(calls) == 3
            assert calls[0][0][2] == 500  # args[2]
            assert calls[1][0][2] == 1000  # args[2]
            assert calls[2][0][2] == 2000  # args[2]

    @pytest.mark.asyncio
    async def test_fetch_job_details_navigation_fails(self):
        """Returns original job unchanged if navigation to detail page fails."""
        job = {
            "id": "job5",
            "title": "Intern",
            "company": "Acme",
            "url": "https://example.com/job5",
        }

        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)

        with patch("src.poc.tweak.crawl_details.retry_goto", new_callable=AsyncMock) as mock_retry:
            mock_retry.return_value = False  # Navigation fails

            result = await fetch_job_details(mock_browser, job, {"Acme": {}})

        # Should return job with no description added
        assert "description" not in result or result.get("description") == ""
        mock_page.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_job_details_no_url(self):
        """Returns original job unchanged if URL is missing."""
        job = {
            "id": "job6",
            "title": "Senior",
            "company": "Acme",
        }

        mock_browser = AsyncMock()

        result = await fetch_job_details(mock_browser, job, {"Acme": {}})

        assert result == job
        mock_browser.new_page.assert_not_called()


# ============================================================================
# TESTS: extract_description_from_detail_page()
# ============================================================================


class TestExtractDescriptionFromDetailPage:
    """Tests for description extraction logic."""

    @pytest.mark.asyncio
    async def test_extract_description_direct_dom(self):
        """Extracts description from direct DOM (non-iframe) element."""
        mock_page = AsyncMock()
        mock_elem = AsyncMock()
        mock_elem.evaluate = AsyncMock(return_value="div")  # tag_name
        mock_elem.inner_html = AsyncMock(return_value="<p>Direct DOM content</p>")
        mock_page.query_selector = AsyncMock(return_value=mock_elem)

        selectors = {"description_selector": "div.job-desc"}

        result = await extract_description_from_detail_page(mock_page, "https://example.com/job", selectors)

        assert result == "<p>Direct DOM content</p>"

    @pytest.mark.asyncio
    async def test_extract_description_iframe(self):
        """Extracts description from iframe element."""
        mock_page = AsyncMock()
        mock_elem = AsyncMock()
        mock_elem.evaluate = AsyncMock(return_value="iframe")  # tag_name

        mock_page.query_selector = AsyncMock(return_value=mock_elem)

        selectors = {
            "description_selector": "div.job-desc",
            "inner_description_selector": "div.inner",
        }

        with patch("src.poc.tweak.crawl_details.fetch_iframe_content", new_callable=AsyncMock) as mock_iframe:
            mock_iframe.return_value = "<p>Iframe content</p>"

            result = await extract_description_from_detail_page(mock_page, "https://example.com/job", selectors)

        assert result == "<p>Iframe content</p>"
        mock_iframe.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_description_no_selector_configured(self):
        """Returns None when no description selector configured."""
        mock_page = AsyncMock()
        selectors: dict[str, str] = {}  # No description_selector

        result = await extract_description_from_detail_page(mock_page, "https://example.com/job", selectors)

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_description_selector_not_found(self):
        """Returns None when selector not found on page."""
        mock_page = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=None)

        selectors = {"description_selector": "div.nonexistent"}

        result = await extract_description_from_detail_page(mock_page, "https://example.com/job", selectors)

        assert result is None

    def test_generic_fallback_has_description_selector_key(self):
        """GENERIC_FALLBACK_SELECTORS has 'description_selector' key, not 'description'."""
        from src.poc.tweak.common import GENERIC_FALLBACK_SELECTORS

        # Verify key exists and is not "description"
        assert "description_selector" in GENERIC_FALLBACK_SELECTORS
        assert "description" not in GENERIC_FALLBACK_SELECTORS

        # Verify value is a valid selector string
        value = GENERIC_FALLBACK_SELECTORS["description_selector"]
        assert isinstance(value, str)
        assert len(value) > 0


# ============================================================================
# TESTS: Graceful Degradation
# ============================================================================


class TestGracefulDegradation:
    """Tests that failures don't stop processing; jobs returned with available data."""

    @pytest.mark.asyncio
    async def test_job_returned_even_on_extraction_failure(self):
        """Job returned with empty description if extraction fails."""
        job = {
            "id": "job7",
            "title": "Engineer",
            "company": "Acme",
            "url": "https://example.com/job7",
        }

        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)

        with patch("src.poc.tweak.crawl_details.retry_goto", new_callable=AsyncMock) as mock_retry:
            mock_retry.return_value = True

            with patch("src.poc.tweak.crawl_details.selector_present", new_callable=AsyncMock) as mock_sel:
                mock_sel.return_value = False  # All attempts fail

                with patch("src.poc.tweak.crawl_details.resolve_company_selectors") as mock_resolve:
                    mock_resolve.return_value = {}

                    result = await fetch_job_details(mock_browser, job, {"Acme": {}})

        # Job returned with description set to empty string
        assert "id" in result
        assert "title" in result
        assert "description" in result
        assert result["description"] == ""

    @pytest.mark.asyncio
    async def test_original_fields_preserved_on_failure(self):
        """Original job fields preserved even if new extraction fails."""
        job = {
            "id": "job8",
            "title": "QA Engineer",
            "company": "Acme",
            "url": "https://example.com/job8",
            "location": "Remote",
            "extra_field": "custom_value",
        }

        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)

        with patch("src.poc.tweak.crawl_details.retry_goto", new_callable=AsyncMock) as mock_retry:
            mock_retry.return_value = True

            with patch("src.poc.tweak.crawl_details.selector_present", new_callable=AsyncMock) as mock_sel:
                mock_sel.return_value = False

                with patch("src.poc.tweak.crawl_details.resolve_company_selectors") as mock_resolve:
                    mock_resolve.return_value = {}

                    result = await fetch_job_details(mock_browser, job, {"Acme": {}})

        # All original fields present
        assert result["id"] == "job8"
        assert result["title"] == "QA Engineer"
        assert result["location"] == "Remote"
        assert result["extra_field"] == "custom_value"
