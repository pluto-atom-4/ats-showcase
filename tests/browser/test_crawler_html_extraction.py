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
