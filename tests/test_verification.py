"""Tests for user verification CLI."""

import pytest

from src.verification.reviewer import JobReviewer


@pytest.mark.unit
@pytest.mark.asyncio
async def test_job_reviewer_initialization():
    """Test job reviewer initialization."""
    reviewer = JobReviewer()
    assert reviewer is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_review_job(sample_job_data):
    """Test single job review."""
    reviewer = JobReviewer()
    result = await reviewer.review_job(sample_job_data)
    assert result is not None
    assert "title" in result
