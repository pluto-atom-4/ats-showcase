"""Tests for job description extraction from detail pages (Issue #309).

Tests adaptive retry logic, selector waiting, iframe extraction, and graceful
fallback patterns.
"""

import asyncio
import json
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.poc.tweak.crawl_details import (
    extract_description_from_detail_page,
    fetch_job_details,
    fetch_worksource_job_via_api,
    is_shell_content,
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
        mock_page.set_default_timeout = MagicMock()
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
        mock_page.set_default_timeout = MagicMock()
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
        mock_page.set_default_timeout = MagicMock()
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
        mock_page.set_default_timeout = MagicMock()
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
        mock_page.set_default_timeout = MagicMock()
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
        mock_page.set_default_timeout = MagicMock()
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
        mock_page.set_default_timeout = MagicMock()
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


# ============================================================================
# WORKSOURCE API INTERCEPT + SHELL DETECTION (Issue #765)
# ============================================================================

WS_JOB_URL = "https://worksource.my.site.com/worksourcewa/job-search?keyword=engineer&jobId=J988117"
WS_DETAIL_URL = "https://worksource.my.site.com/worksourcewa/job-search/job-details?jobId=J988117"
WS_API_URL = (
    "https://worksource.my.site.com/webruntime/api/apex/execute"
    "?language=en-US&asGuest=true&htmlEncode=false&classname=9f8e7d6c5b4a&method=ApexActionController.execute"
)

# Trimmed excerpts of the real captures (.playwright-mcp/worksource_shell_search.json = shell,
# worksource_real_detail.json = real detail). Only the discriminating markers are kept.
WS_SHELL_EXCERPT = (
    '<div class="refine-your-job-container"><h2 class="refine-your-search-heading">Refine your search</h2>'
    '<button class="refine-your-job-clear-button">Clear filters</button></div>'
    '<h2 class="search-result">Viewing 1 - 20 of 476 jobs</h2>'
)
WS_REAL_EXCERPT = (
    '<div class="common-jobdetails"><p class="wswa-h5"><span>Job ID:</span><span>J988117</span></p>'
    "<p><strong>Pay:</strong>$198,000 - $246,000/year</p><button>Apply</button></div>"
    "<div><h3>Job details</h3><p>Lead the platform team across three sites.</p></div>"
)
WS_API_DESCRIPTION = "<p>Lead the platform team across three sites.</p>"
WS_DOM_DESCRIPTION = "<p>DOM read description text.</p>"


def make_api_response(
    *,
    url: str = WS_API_URL,
    method: str = "POST",
    post_data: Optional[str] = None,
    ok: bool = True,
    status: int = 200,
    payload: Any = None,
    json_error: Optional[Exception] = None,
) -> SimpleNamespace:
    """Fake Playwright Response for an Apex getJobDetails call."""
    if post_data is None:
        post_data = json.dumps({"method": "getJobDetails", "params": {"jobId": "J988117"}})
    if payload is None:
        payload = {"returnValue": {"jobDescription": WS_API_DESCRIPTION}}
    json_mock = AsyncMock(side_effect=json_error) if json_error else AsyncMock(return_value=payload)
    return SimpleNamespace(
        url=url,
        ok=ok,
        status=status,
        request=SimpleNamespace(method=method, post_data=post_data),
        json=json_mock,
    )


async def _return(value: Any) -> Any:
    return value


class _FakeExpectResponse:
    """Stand-in for page.expect_response(): matches canned responses when the block exits."""

    def __init__(self, predicate: Any, responses: List[Any], timeout: int) -> None:
        self._predicate = predicate
        self._responses = responses
        self._timeout = timeout
        self.value: Any = None

    async def __aenter__(self) -> "_FakeExpectResponse":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if exc_type is not None:
            return False
        matched = next((r for r in self._responses if self._predicate(r)), None)
        if matched is None:
            raise asyncio.TimeoutError(f"no matching response within {self._timeout}ms")
        self.value = _return(matched)
        return False


def make_worksource_page(
    api_responses: Optional[List[Any]] = None,
    dom_description: Optional[str] = None,
) -> AsyncMock:
    """AsyncMock page wired for WorkSource: expect_response, goto, and an optional DOM description."""
    page = AsyncMock()
    responses = list(api_responses or [])
    page.expect_response = MagicMock(
        side_effect=lambda predicate, timeout: _FakeExpectResponse(predicate, responses, timeout)
    )
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    if dom_description is None:
        page.query_selector = AsyncMock(return_value=None)
    else:
        elem = AsyncMock()
        elem.evaluate = AsyncMock(return_value="div")
        elem.inner_html = AsyncMock(return_value=dom_description)
        page.query_selector = AsyncMock(return_value=elem)
    return page


WS_SELECTORS = {"description_selector": "div.job-description"}


class TestIsShellContent:
    """Shell detection: WorkSource search-list shell vs real detail page."""

    def test_shell_excerpt_is_shell(self):
        assert is_shell_content(WS_SHELL_EXCERPT) is True

    def test_real_excerpt_is_not_shell(self):
        assert is_shell_content(WS_REAL_EXCERPT) is False

    def test_empty_string_is_shell(self):
        assert is_shell_content("") is True

    def test_whitespace_only_is_shell(self):
        assert is_shell_content("   \n\t ") is True

    def test_single_marker_is_not_enough(self):
        """One marker alone (e.g. 'Clear filters' in prose) does not classify as shell."""
        assert is_shell_content("<p>Use Clear filters to reset the form.</p>") is False

    def test_plain_description_is_not_shell(self):
        assert is_shell_content("<p>We are hiring a Python engineer.</p>") is False


class TestFetchWorksourceJobViaApi:
    """fetch_worksource_job_via_api(): intercept getJobDetails response."""

    @pytest.mark.asyncio
    async def test_success_returns_return_value(self):
        response = make_api_response()
        page = make_worksource_page(api_responses=[response])

        result = await fetch_worksource_job_via_api(page, WS_JOB_URL, api_timeout_ms=10000)

        assert result == {"jobDescription": WS_API_DESCRIPTION}
        page.goto.assert_awaited_once_with(WS_JOB_URL, wait_until="commit")
        assert page.expect_response.call_args.kwargs == {"timeout": 10000}

    @pytest.mark.asyncio
    async def test_predicate_ignores_classname_hash(self):
        """Predicate matches on path/method/body only; any build-specific classname hash matches."""
        page = make_worksource_page(api_responses=[])
        await fetch_worksource_job_via_api(page, WS_JOB_URL)
        predicate = page.expect_response.call_args.args[0]

        other_build = make_api_response(
            url=WS_API_URL.replace("9f8e7d6c5b4a", "0000deadbeef"),
        )
        assert predicate(other_build) is True
        assert predicate(make_api_response()) is True

    @pytest.mark.asyncio
    async def test_predicate_rejects_wrong_method_path_or_body(self):
        page = make_worksource_page(api_responses=[])
        await fetch_worksource_job_via_api(page, WS_JOB_URL)
        predicate = page.expect_response.call_args.args[0]

        assert predicate(make_api_response(method="GET")) is False
        assert predicate(make_api_response(url="https://worksource.my.site.com/other/path")) is False
        assert predicate(make_api_response(post_data=json.dumps({"method": "getOther"}))) is False
        assert predicate(make_api_response(post_data="message=%7B%7D&aura.context=x")) is False

    @pytest.mark.asyncio
    async def test_timeout_returns_none(self):
        page = make_worksource_page(api_responses=[])

        result = await fetch_worksource_job_via_api(page, WS_JOB_URL, api_timeout_ms=50)

        assert result is None

    @pytest.mark.asyncio
    async def test_non_ok_response_returns_none(self):
        page = make_worksource_page(api_responses=[make_api_response(ok=False, status=500)])

        assert await fetch_worksource_job_via_api(page, WS_JOB_URL) is None

    @pytest.mark.asyncio
    async def test_bad_json_returns_none(self):
        page = make_worksource_page(api_responses=[make_api_response(json_error=ValueError("bad json"))])

        assert await fetch_worksource_job_via_api(page, WS_JOB_URL) is None

    @pytest.mark.asyncio
    async def test_missing_return_value_returns_none(self):
        page = make_worksource_page(api_responses=[make_api_response(payload={"unexpected": True})])

        assert await fetch_worksource_job_via_api(page, WS_JOB_URL) is None

    @pytest.mark.asyncio
    async def test_navigation_error_returns_none(self):
        page = make_worksource_page(api_responses=[])
        page.goto = AsyncMock(side_effect=RuntimeError("net::ERR_ABORTED"))

        assert await fetch_worksource_job_via_api(page, WS_JOB_URL) is None


class TestWorksourceDescriptionFlow:
    """extract_description_from_detail_page() for company_key == 'WorkSource'."""

    @pytest.mark.asyncio
    async def test_api_success_skips_dom(self):
        page = make_worksource_page(
            api_responses=[make_api_response()],
            dom_description=WS_DOM_DESCRIPTION,
        )

        result = await extract_description_from_detail_page(page, WS_JOB_URL, WS_SELECTORS, company_key="WorkSource")

        assert result == WS_API_DESCRIPTION
        page.query_selector.assert_not_called()
        page.wait_for_selector.assert_not_called()
        assert page.goto.await_count == 1

    @pytest.mark.asyncio
    async def test_api_timeout_falls_back_to_dom(self):
        page = make_worksource_page(api_responses=[], dom_description=WS_DOM_DESCRIPTION)

        result = await extract_description_from_detail_page(
            page, WS_JOB_URL, WS_SELECTORS, api_timeout_ms=50, company_key="WorkSource"
        )

        assert result == WS_DOM_DESCRIPTION
        assert page.goto.await_count == 2
        assert page.goto.await_args_list[1].args[0] == WS_DETAIL_URL

    @pytest.mark.asyncio
    async def test_api_shell_description_falls_back_to_dom(self):
        page = make_worksource_page(
            api_responses=[make_api_response(payload={"returnValue": {"jobDescription": WS_SHELL_EXCERPT}})],
            dom_description=WS_DOM_DESCRIPTION,
        )

        result = await extract_description_from_detail_page(page, WS_JOB_URL, WS_SELECTORS, company_key="WorkSource")

        assert result == WS_DOM_DESCRIPTION
        assert page.goto.await_args_list[1].args[0] == WS_DETAIL_URL

    @pytest.mark.asyncio
    async def test_api_empty_description_falls_back_to_dom(self):
        page = make_worksource_page(
            api_responses=[make_api_response(payload={"returnValue": {"jobDescription": ""}})],
            dom_description=WS_DOM_DESCRIPTION,
        )

        result = await extract_description_from_detail_page(page, WS_JOB_URL, WS_SELECTORS, company_key="WorkSource")

        assert result == WS_DOM_DESCRIPTION

    @pytest.mark.asyncio
    async def test_fallback_without_job_id_uses_job_url_as_is(self):
        url = "https://worksource.my.site.com/worksourcewa/job-search?keyword=engineer"
        page = make_worksource_page(api_responses=[], dom_description=WS_DOM_DESCRIPTION)

        result = await extract_description_from_detail_page(
            page, url, WS_SELECTORS, api_timeout_ms=50, company_key="WorkSource"
        )

        assert result == WS_DOM_DESCRIPTION
        assert page.goto.await_args_list[1].args[0] == url

    @pytest.mark.asyncio
    async def test_dom_fallback_shell_content_returns_none(self):
        page = make_worksource_page(api_responses=[], dom_description=WS_SHELL_EXCERPT)

        result = await extract_description_from_detail_page(
            page, WS_JOB_URL, WS_SELECTORS, api_timeout_ms=50, company_key="WorkSource"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_dom_fallback_navigation_error_returns_none(self):
        page = make_worksource_page(api_responses=[], dom_description=WS_DOM_DESCRIPTION)
        page.goto = AsyncMock(side_effect=[None, RuntimeError("net::ERR_ABORTED")])

        result = await extract_description_from_detail_page(
            page, WS_JOB_URL, WS_SELECTORS, api_timeout_ms=50, company_key="WorkSource"
        )

        assert result is None


class TestNonWorksourceUnchanged:
    """Regression: non-WorkSource extraction never touches the API path and keeps DOM behaviour."""

    @pytest.mark.asyncio
    async def test_real_content_returned_without_api_or_goto(self):
        page = make_worksource_page(api_responses=[make_api_response()], dom_description=WS_REAL_EXCERPT)
        page.expect_response = MagicMock()

        for key in ("", "CarbonRobotics"):
            result = await extract_description_from_detail_page(
                page, "https://example.com/job", WS_SELECTORS, company_key=key
            )
            assert result == WS_REAL_EXCERPT

        page.expect_response.assert_not_called()
        page.goto.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_default_company_key_is_backward_compatible(self):
        page = make_worksource_page(dom_description="<p>Direct DOM content</p>")

        result = await extract_description_from_detail_page(page, "https://example.com/job", WS_SELECTORS)

        assert result == "<p>Direct DOM content</p>"

    @pytest.mark.asyncio
    async def test_generic_shell_guard_returns_none_for_other_companies(self):
        page = make_worksource_page(dom_description=WS_SHELL_EXCERPT)

        result = await extract_description_from_detail_page(
            page, "https://example.com/job", WS_SELECTORS, company_key="CarbonRobotics"
        )

        assert result is None


class TestFetchJobDetailsWorksourceWiring:
    """fetch_job_details() reads source_config and passes company_key through."""

    @pytest.mark.asyncio
    async def test_source_config_passed_as_company_key_and_selector_gate_bypassed(self):
        job = {"url": WS_JOB_URL, "company": "WorkSource for Jobs", "title": "Eng", "source_config": "WorkSource"}
        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=AsyncMock())

        with patch("src.poc.tweak.crawl_details.retry_goto", new_callable=AsyncMock, return_value=True):
            with patch("src.poc.tweak.crawl_details.selector_present", new_callable=AsyncMock, return_value=False):
                with patch("src.poc.tweak.crawl_details.resolve_company_selectors", return_value=WS_SELECTORS):
                    with patch(
                        "src.poc.tweak.crawl_details.extract_description_from_detail_page",
                        new_callable=AsyncMock,
                        return_value=WS_API_DESCRIPTION,
                    ) as mock_extract:
                        result = await fetch_job_details(mock_browser, job, {})

        assert result["description"] == WS_API_DESCRIPTION
        assert mock_extract.await_count == 1
        assert mock_extract.await_args.kwargs["company_key"] == "WorkSource"

    @pytest.mark.asyncio
    async def test_non_worksource_selector_gate_unchanged(self):
        job = {"url": "https://example.com/job", "company": "Acme", "title": "Eng", "source_config": "Acme"}
        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=AsyncMock())

        with patch("src.poc.tweak.crawl_details.retry_goto", new_callable=AsyncMock, return_value=True):
            with patch("src.poc.tweak.crawl_details.selector_present", new_callable=AsyncMock, return_value=False):
                with patch("src.poc.tweak.crawl_details.resolve_company_selectors", return_value=WS_SELECTORS):
                    with patch(
                        "src.poc.tweak.crawl_details.extract_description_from_detail_page",
                        new_callable=AsyncMock,
                    ) as mock_extract:
                        await fetch_job_details(mock_browser, job, {})

        mock_extract.assert_not_awaited()
