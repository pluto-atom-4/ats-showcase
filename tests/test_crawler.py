"""Tests for job crawling functionality."""

import pytest

from src.browser.crawler import Crawler
from src.browser.selectors import SelectorManager


@pytest.mark.asyncio
async def test_crawler_initialization():
    """Test crawler initialization."""
    crawler = Crawler(headless=True, timeout_ms=30000)
    assert crawler.headless is True
    assert crawler.timeout_ms == 30000


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

    invalid = {"title": ".title"}  # Missing required fields

    assert manager.validate_selectors(valid) is True
    assert manager.validate_selectors(invalid) is False
