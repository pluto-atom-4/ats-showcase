"""Tests for job crawling functionality."""

import pytest

from browser.crawler import Crawler
from browser.selectors import SelectorManager


@pytest.mark.asyncio
async def test_crawler_initialization():
    """Test crawler initialization."""
    crawler = Crawler(headless=True, timeout_ms=30000)
    assert crawler.headless is True
    assert crawler.timeout_ms == 30000


def test_crawler_no_longer_owns_markdown_transform():
    """Regression guard for Issue #228: HTML->Markdown transform (and its
    helpers) moved to src.parsers.html_to_markdown; Crawler must no longer
    reference or import any of it, so descriptions stay raw at crawl time.
    """
    import inspect

    import browser.crawler as crawler_module

    assert not hasattr(Crawler, "_normalize_description")
    assert not hasattr(Crawler, "_add_markdown_section_headers")
    assert not hasattr(Crawler, "_insert_section_dividers")
    assert "html_to_markdown" not in inspect.getsource(crawler_module)


@pytest.mark.asyncio
async def test_selector_manager():
    """Test selector manager."""
    manager = SelectorManager()

    selectors = {
        "job_container": ".job-item",
        "title": ".job-title",
        "description": ".job-description",
    }

    manager.add_company("TechCorp", selectors)
    retrieved = manager.get_selectors("TechCorp")
    assert retrieved == selectors


def test_selector_validation():
    """Test selector validation."""
    manager = SelectorManager()

    valid = {
        "job_container": ".jobs",
        "title": ".title",
        "description": ".desc",
    }

    invalid = {"title": ".title"}

    assert manager.validate_selectors(valid) is True
    assert manager.validate_selectors(invalid) is False
