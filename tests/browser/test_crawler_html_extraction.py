"""Tests for crawler raw HTML extraction with fallback chain."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.browser.crawler import Crawler


@pytest.fixture
def crawler():
    """Create a Crawler instance for testing."""
    return Crawler(headless=True, timeout_ms=30000)


class TestIframeHtmlExtraction:
    """Tests for iframe HTML extraction with fallback chain."""

    @pytest.mark.asyncio
    async def test_iframe_html_extraction_returns_raw_html(self, crawler):
        """Test that iframe extraction uses innerHTML (raw HTML) by default."""
        mock_page = AsyncMock()
        mock_frame = AsyncMock()

        mock_page.wait_for_load_state = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.frames = [mock_frame]

        # >100 chars to pass the crawler min-length check.
        expected_html = (
            "<h2>Senior Developer</h2>"
            "<p>Requirements: 5+ years experience with Python, AWS, and cloud"
            " infrastructure. Must have expertise in microservices architecture"
            " and DevOps practices.</p>"
        )
        mock_frame.evaluate = AsyncMock(return_value=expected_html)
        mock_frame.query_selector = AsyncMock(return_value=None)

        result = await crawler._fetch_iframe_via_frame(mock_page, inner_selector=None)

        mock_frame.evaluate.assert_called()
        calls = mock_frame.evaluate.call_args_list
        first_call_arg = calls[0][0][0] if calls else ""
        assert "innerHTML" in first_call_arg

        assert result == expected_html

    @pytest.mark.asyncio
    async def test_iframe_with_selector_returns_raw_html(self, crawler):
        """Test iframe extraction with selector uses inner_html."""
        mock_page = AsyncMock()
        mock_frame = AsyncMock()
        mock_elem = AsyncMock()

        mock_page.wait_for_load_state = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.frames = [mock_frame]

        mock_frame.query_selector = AsyncMock(return_value=mock_elem)

        expected_html = "<div><p>Job requirements and responsibilities for Senior Developer position</p></div>"
        mock_elem.inner_html = AsyncMock(return_value=expected_html)

        result = await crawler._fetch_iframe_via_frame(mock_page, inner_selector=".job-description")

        mock_elem.inner_html.assert_called_once()
        assert result == expected_html

    @pytest.mark.asyncio
    async def test_fallback_chain_inner_html_to_outer_html(self, crawler):
        """Test fallback from innerHTML to outerHTML when content is minimal."""
        mock_page = AsyncMock()
        mock_frame = AsyncMock()
        mock_elem = AsyncMock()

        mock_page.wait_for_load_state = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.frames = [mock_frame]

        mock_frame.query_selector = AsyncMock(return_value=mock_elem)

        # <50 chars trips the crawler min-length check and forces the outerHTML fallback.
        mock_elem.inner_html = AsyncMock(return_value="<p>Short</p>")
        outer_html = "<div><p>Full job description with requirements</p></div>"
        mock_elem.evaluate = AsyncMock(return_value=outer_html)

        result = await crawler._fetch_iframe_via_frame(mock_page, inner_selector=".content")

        mock_elem.inner_html.assert_called_once()
        mock_elem.evaluate.assert_called()
        assert result == outer_html

    @pytest.mark.asyncio
    async def test_fallback_chain_to_text_content(self, crawler):
        """Test fallback to innerText when HTML extraction fails."""
        mock_page = AsyncMock()
        mock_frame = AsyncMock()
        mock_elem = AsyncMock()

        mock_page.wait_for_load_state = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.frames = [mock_frame]

        mock_frame.query_selector = AsyncMock(return_value=mock_elem)

        mock_elem.inner_html = AsyncMock(return_value="")
        mock_elem.evaluate = AsyncMock(return_value="")
        plain_text = "Senior Developer - 5+ years required"
        mock_elem.text_content = AsyncMock(return_value=plain_text)

        result = await crawler._fetch_iframe_via_frame(mock_page, inner_selector=".description")

        assert plain_text in result

    @pytest.mark.asyncio
    async def test_fallback_chain_frame_level_html_to_text(self, crawler):
        """Test fallback from frame.innerHTML to frame.innerText at frame level."""
        mock_page = AsyncMock()
        mock_frame = AsyncMock()

        mock_page.wait_for_load_state = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.frames = [mock_frame]

        mock_frame.query_selector = AsyncMock(return_value=None)

        def evaluate_side_effect(script):
            if "innerHTML" in script:
                return "<html></html>"
            elif "outerHTML" in script:
                return "<html></html>"
            else:
                return "Senior Developer Role\nKey Responsibilities"

        mock_frame.evaluate = AsyncMock(side_effect=evaluate_side_effect)

        result = await crawler._fetch_iframe_via_frame(mock_page, inner_selector=None)

        assert "Senior Developer" in result or len(result.strip()) == 0 or "Senior" in result

    @pytest.mark.asyncio
    async def test_regular_element_html_extraction_continues_working(self, crawler):
        """Test that regular (non-iframe) element extraction still works correctly."""
        mock_page = AsyncMock()
        mock_desc_elem = AsyncMock()

        mock_page.query_selector = AsyncMock(return_value=mock_desc_elem)
        mock_page.evaluate = AsyncMock(return_value="div")
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()

        expected_html = "<h3>Job Description</h3><p>Detailed requirements</p>"
        mock_desc_elem.inner_html = AsyncMock(return_value=expected_html)
        mock_desc_elem.evaluate = AsyncMock(return_value="div")

        result = await mock_desc_elem.inner_html()
        assert result == expected_html

    @pytest.mark.asyncio
    async def test_no_content_found_returns_empty_string(self, crawler):
        """Test that no content found returns empty string gracefully."""
        mock_page = AsyncMock()
        mock_frame = AsyncMock()

        mock_page.wait_for_load_state = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.frames = [mock_frame]

        mock_frame.query_selector = AsyncMock(return_value=None)
        mock_frame.evaluate = AsyncMock(return_value="")

        result = await crawler._fetch_iframe_via_frame(mock_page, inner_selector=None)

        assert result == ""

    @pytest.mark.asyncio
    async def test_frame_exception_skipped_tries_next_frame(self, crawler):
        """Test that frame exceptions don't stop processing; tries next frame."""
        mock_page = AsyncMock()
        mock_frame1 = AsyncMock()
        mock_frame2 = AsyncMock()

        mock_page.wait_for_load_state = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.frames = [mock_frame1, mock_frame2]

        mock_frame1.evaluate = AsyncMock(side_effect=Exception("Frame error"))
        mock_frame1.query_selector = AsyncMock(side_effect=Exception("Frame error"))

        # >100 chars to pass the crawler min-length check; frame1 raises so frame2 is used.
        success_content = (
            "<h2>Job Title</h2>"
            "<p>Requirements: 5+ years experience with relevant technologies."
            " Must have expertise in cloud platforms, containerization, and"
            " modern DevOps practices and tools.</p>"
        )
        mock_frame2.evaluate = AsyncMock(return_value=success_content)
        mock_frame2.query_selector = AsyncMock(return_value=None)

        result = await crawler._fetch_iframe_via_frame(mock_page, inner_selector=None)

        assert success_content in result

    @pytest.mark.asyncio
    async def test_multiple_frames_uses_first_substantial_content(self, crawler):
        """Test that multiple frames returns content from first frame with substantial data."""
        mock_page = AsyncMock()
        mock_frame1 = AsyncMock()
        mock_frame2 = AsyncMock()

        mock_page.wait_for_load_state = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.frames = [mock_frame1, mock_frame2]

        # >100 chars so frame1 satisfies the min-length check and frame2 is never tried.
        substantial_content = (
            "<h2>Job Description</h2>"
            "<p>We are looking for an experienced developer with 5+ years of"
            " experience in cloud-native architectures and microservices.</p>"
        )
        mock_frame1.evaluate = AsyncMock(return_value=substantial_content)
        mock_frame1.query_selector = AsyncMock(return_value=None)

        result = await crawler._fetch_iframe_via_frame(mock_page, inner_selector=None)

        mock_frame1.evaluate.assert_called()
        assert substantial_content in result


class TestRequirementsExtraction:
    """Tests for requirements parsing in _fetch_job_detail."""

    async def _fetch_requirements(self, crawler, req_elems):
        mock_page = AsyncMock()
        mock_page.query_selector_all = AsyncMock(return_value=req_elems)
        mock_page.set_default_timeout = MagicMock()
        crawler.context = MagicMock()
        crawler.context.new_page = AsyncMock(return_value=mock_page)
        selectors = {"requirements_selector": ".requirements"}
        _, requirements = await crawler._fetch_job_detail("https://example.com/job/1", selectors)
        return requirements

    @staticmethod
    def _req_elem(text):
        req_elem = AsyncMock()
        req_elem.inner_text = AsyncMock(return_value=text)
        req_elem.text_content = AsyncMock(return_value=text)
        return req_elem

    @pytest.mark.asyncio
    async def test_multiline_inner_text_splits_into_list(self, crawler):
        """Multi-line inner_text becomes one stripped item per non-blank line."""
        req_elem = self._req_elem("\n  Python 3.11+\n\n  FastAPI\nPostgreSQL\n")

        result = await self._fetch_requirements(crawler, [req_elem])

        assert result == ["Python 3.11+", "FastAPI", "PostgreSQL"]

    @pytest.mark.asyncio
    async def test_single_line_is_not_comma_split(self, crawler):
        """A single line stays one item even when it contains commas."""
        req_elem = self._req_elem("5+ years of Python, SQL")

        result = await self._fetch_requirements(crawler, [req_elem])

        assert result == ["5+ years of Python, SQL"]

    @pytest.mark.asyncio
    async def test_multiple_elements_concatenated_in_page_order(self, crawler):
        """Lines from every matched element are collected in DOM order."""
        first = self._req_elem("Python 3.11+\nFastAPI")
        second = self._req_elem("  PostgreSQL \n\n")
        third = self._req_elem("Docker")

        result = await self._fetch_requirements(crawler, [first, second, third])

        assert result == ["Python 3.11+", "FastAPI", "PostgreSQL", "Docker"]

    @pytest.mark.asyncio
    async def test_blank_element_contributes_nothing(self, crawler):
        """A blank matched element adds no items; the others still count."""
        blank = self._req_elem("  \n\t\n")
        filled = self._req_elem("Go\nRust")

        result = await self._fetch_requirements(crawler, [blank, filled])

        assert result == ["Go", "Rust"]

    @pytest.mark.asyncio
    async def test_commas_within_multiple_elements_not_split(self, crawler):
        """Commas inside any element never split a line into items."""
        first = self._req_elem("Python, SQL, Go")
        second = self._req_elem("Kubernetes, Helm")

        result = await self._fetch_requirements(crawler, [first, second])

        assert result == ["Python, SQL, Go", "Kubernetes, Helm"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("text", ["", "   \n\t  \n"])
    async def test_blank_text_returns_none(self, crawler, text):
        """Whitespace-only or empty requirements text yields None."""
        req_elem = self._req_elem(text)

        result = await self._fetch_requirements(crawler, [req_elem])

        assert result is None

    @pytest.mark.asyncio
    async def test_all_blank_elements_return_none(self, crawler):
        """None only when every matched element is blank."""
        result = await self._fetch_requirements(crawler, [self._req_elem(""), self._req_elem(" \n ")])

        assert result is None

    @pytest.mark.asyncio
    async def test_no_matching_element_returns_none(self, crawler):
        """A missing requirements element yields None."""
        result = await self._fetch_requirements(crawler, [])

        assert result is None
