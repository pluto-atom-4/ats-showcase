"""Tests for AssessmentStore purge functionality."""

import json
import tempfile
from pathlib import Path

import pytest

from storage.assessment_store import AssessmentStore


@pytest.fixture
def temp_db():
    """Create temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def store_with_assessments(temp_db):
    """Create store with sample assessments."""
    store = AssessmentStore(temp_db)

    # Create sample assessments
    assessments = [
        {
            "job_id": "job1",
            "title": "Senior Python Engineer",
            "company": "TechCorp",
            "location": "San Francisco, CA",
            "overall_score": 92,
            "tech_score": 95,
            "seniority_score": 88,
            "location_score": 80,
            "recommendations": ["Learn Kubernetes"],
            "summary": "Excellent fit",
            "tokens_used": 650,
            "actual_cost": 0.002,
            "input_tokens": 600,
            "output_tokens": 50,
        },
        {
            "job_id": "job2",
            "title": "ML Engineer",
            "company": "DataInc",
            "location": "New York, NY",
            "overall_score": 78,
            "tech_score": 85,
            "seniority_score": 75,
            "location_score": 60,
            "recommendations": ["Study PyTorch"],
            "summary": "Good fit",
            "tokens_used": 670,
            "actual_cost": 0.002,
            "input_tokens": 620,
            "output_tokens": 50,
        },
        {
            "job_id": "job3",
            "title": "Frontend Developer",
            "company": "WebDev Inc",
            "location": "Austin, TX",
            "overall_score": 65,
            "tech_score": 70,
            "seniority_score": 60,
            "location_score": 50,
            "recommendations": [],
            "summary": "Moderate fit",
            "tokens_used": 640,
            "actual_cost": 0.002,
            "input_tokens": 590,
            "output_tokens": 50,
        },
    ]

    for assessment in assessments:
        store.save_assessment(
            job_id=assessment["job_id"],
            title=assessment["title"],
            company=assessment["company"],
            location=assessment["location"],
            overall_score=assessment["overall_score"],
            tech_score=assessment["tech_score"],
            seniority_score=assessment["seniority_score"],
            location_score=assessment["location_score"],
            recommendations=assessment["recommendations"],
            summary=assessment["summary"],
            tokens_used=assessment["tokens_used"],
            actual_cost=assessment["actual_cost"],
            input_tokens=assessment["input_tokens"],
            output_tokens=assessment["output_tokens"],
        )

    return store


class TestPurgeByDate:
    """Test purge_by_date method."""

    def test_purge_no_filters(self, store_with_assessments):
        """Test purge with no date filters."""
        result = store_with_assessments.purge_by_date(dry_run=True)
        assert result["count"] == 0
        assert result["dry_run"] is True

    def test_purge_dry_run_no_delete(self, store_with_assessments):
        """Test that dry_run doesn't actually delete."""
        initial_count = store_with_assessments.count_assessments()
        assert initial_count == 3

        # Dry run with future date (should match all assessments)
        result = store_with_assessments.purge_by_date(
            before_date="2099-12-31",
            dry_run=True,
        )

        assert result["count"] == 3
        assert result["dry_run"] is True

        # Verify nothing was deleted
        final_count = store_with_assessments.count_assessments()
        assert final_count == 3

    def test_purge_before_date_actual_delete(self, store_with_assessments):
        """Test actual deletion before date."""
        initial_count = store_with_assessments.count_assessments()
        assert initial_count == 3

        # Delete with future date (all should match)
        result = store_with_assessments.purge_by_date(
            before_date="2099-12-31",
            dry_run=False,
        )

        assert result["count"] == 3
        assert result["dry_run"] is False

        # Verify all were deleted
        final_count = store_with_assessments.count_assessments()
        assert final_count == 0

    def test_purge_before_date_partial(self, store_with_assessments):
        """Test partial deletion before date."""
        # This test uses a past date that won't match anything
        result = store_with_assessments.purge_by_date(
            before_date="2020-01-01",
            dry_run=False,
        )

        # Should not delete anything (all assessments created after 2020-01-01)
        assert result["count"] == 0
        assert store_with_assessments.count_assessments() == 3

    def test_purge_after_date(self, store_with_assessments):
        """Test purge with after_date."""
        # With past date, should match all assessments
        result = store_with_assessments.purge_by_date(
            after_date="2020-01-01",
            dry_run=True,
        )

        assert result["count"] == 3

    def test_purge_result_structure(self, store_with_assessments):
        """Test result dictionary structure."""
        result = store_with_assessments.purge_by_date(
            before_date="2099-12-31",
            dry_run=True,
        )

        assert "count" in result
        assert "dry_run" in result
        assert "before_date" in result
        assert "after_date" in result
        assert isinstance(result["count"], int)
        assert isinstance(result["dry_run"], bool)

    def test_purge_fts_cleanup(self, store_with_assessments):
        """Test that FTS index is cleaned up on purge."""
        # Verify initial assessment can be searched
        results = store_with_assessments.search_by_keyword("Python")
        assert len(results) > 0

        # Purge all
        store_with_assessments.purge_by_date(
            before_date="2099-12-31",
            dry_run=False,
        )

        # Verify assessment is gone from database
        assert store_with_assessments.count_assessments() == 0

        # Try to search - should return empty
        results = store_with_assessments.search_by_keyword("Python")
        assert len(results) == 0

    def test_purge_before_after_validation(self, store_with_assessments):
        """Test that both before and after dates can be used together."""
        # Get initial count
        initial_count = store_with_assessments.count_assessments()

        # Try to delete with both dates (past range - nothing should match)
        result = store_with_assessments.purge_by_date(
            before_date="2019-12-31",
            after_date="2018-01-01",
            dry_run=True,
        )

        # Nothing should match
        assert result["count"] == 0

        # Verify count unchanged
        assert store_with_assessments.count_assessments() == initial_count
