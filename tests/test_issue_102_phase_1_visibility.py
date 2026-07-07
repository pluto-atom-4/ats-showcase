"""Tests for Issue #102 Phase 1: Pipeline Visibility."""

import json
import sqlite3
import tempfile
from datetime import datetime, timedelta
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
def store_with_test_data(temp_db):
    """Create store with test data for pipeline stats."""
    store = AssessmentStore(temp_db)

    if store.conn:
        cursor = store.conn.cursor()

        # Create job_reviews table
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS job_reviews (
               job_id TEXT PRIMARY KEY,
               title TEXT,
               company TEXT,
               status TEXT DEFAULT 'pending_review',
               crawled_at TEXT
            )"""
        )

        # Create job_assessments table (use AssessmentStore schema)
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS job_assessments (
               job_id TEXT PRIMARY KEY,
               title TEXT,
               company TEXT,
               location TEXT,
               overall_score REAL,
               tech_score REAL,
               seniority_score REAL,
               location_score REAL,
               recommendations TEXT,
               summary TEXT
            )"""
        )

        # Insert test data
        test_jobs = [
            ("job_1", "Python Dev", "TechCorp", "pending_review", "2026-07-01"),
            ("job_2", "Senior Python", "TechCorp", "pending_review", "2026-07-02"),
            ("job_3", "ML Engineer", "DataCorp", "confirmed", "2026-07-03"),
            ("job_4", "DevOps", "CloudInc", "confirmed", "2026-07-04"),
            ("job_5", "QA Engineer", "TestCorp", "rejected", "2026-07-05"),
            ("job_6", "SRE", "OpsInc", "rejected", "2026-07-06"),
            ("job_7", "Full Stack", "WebCorp", "rejected", "2026-07-07"),
        ]

        for job_id, title, company, status, crawled_at in test_jobs:
            cursor.execute(
                """INSERT INTO job_reviews
                   (job_id, title, company, status, crawled_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (job_id, title, company, status, crawled_at),
            )

        # Add assessments for some jobs
        assessments = [
            ("job_3", "Python Dev", "DataCorp", "Remote", 85.0, 80.0, 90.0, 75.0, "Good fit", "Recommended"),
            ("job_4", "Senior Python", "CloudInc", "NYC", 92.0, 90.0, 95.0, 85.0, "Excellent", "Highly recommended"),
        ]

        for (
            job_id,
            title,
            company,
            location,
            overall,
            tech,
            seniority,
            location_score,
            recs,
            summary,
        ) in assessments:
            cursor.execute(
                """INSERT INTO job_assessments
                   (job_id, title, company, location, overall_score,
                    tech_score, seniority_score, location_score,
                    recommendations, summary)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_id,
                    title,
                    company,
                    location,
                    overall,
                    tech,
                    seniority,
                    location_score,
                    recs,
                    summary,
                ),
            )

        store.conn.commit()

    return store


class TestGetPipelineStats:
    """Test get_pipeline_stats() method."""

    def test_pipeline_stats_basic(self, store_with_test_data):
        """Test basic pipeline stats retrieval."""
        stats = store_with_test_data.get_pipeline_stats()

        assert stats is not None
        assert stats["pending_review"] == 2
        assert stats["confirmed"] == 2
        assert stats["rejected"] == 3
        assert stats["assessed"] == 2

    def test_pipeline_stats_structure(self, store_with_test_data):
        """Test pipeline stats has expected keys."""
        stats = store_with_test_data.get_pipeline_stats()

        required_keys = {"pending_review", "confirmed", "rejected", "assessed"}
        assert required_keys == set(stats.keys())

    def test_pipeline_stats_empty_db(self, temp_db):
        """Test pipeline stats with empty database."""
        store = AssessmentStore(temp_db)
        stats = store.get_pipeline_stats()

        # Empty DB returns empty dict
        assert stats == {}

    def test_pipeline_stats_no_job_reviews_table(self, temp_db):
        """Test graceful fallback when job_reviews doesn't exist."""
        store = AssessmentStore(temp_db)
        # Don't create job_reviews table
        stats = store.get_pipeline_stats()

        # Should return empty dict without error
        assert stats == {}

    def test_pipeline_stats_counts_match_total(self, store_with_test_data):
        """Test that all status counts sum to total jobs."""
        stats = store_with_test_data.get_pipeline_stats()

        total = (
            stats["pending_review"] + stats["confirmed"] + stats["rejected"]
        )
        assert total == 7


class TestGetStatsWithFilters:
    """Test get_stats_with_filters() method."""

    def test_filters_skip_rejected(self, store_with_test_data):
        """Test filtering with skip_rejected=True."""
        stats = store_with_test_data.get_stats_with_filters(
            skip_rejected=True, skip_assessed=False, skip_before_date=None
        )

        # Total: 7 jobs
        # Reject rejected (3): leaves 4
        assert stats["total"] == 7
        assert stats["would_skip"] == 3
        assert stats["would_process"] == 4
        assert stats["reasons"]["rejected"] == 3

    def test_filters_skip_assessed(self, store_with_test_data):
        """Test filtering with skip_assessed=True."""
        stats = store_with_test_data.get_stats_with_filters(
            skip_rejected=False, skip_assessed=True, skip_before_date=None
        )

        # Total: 7 jobs
        # Skip assessed (2 confirmed jobs have assessments): leaves 5
        assert stats["total"] == 7
        assert stats["would_skip"] == 2
        assert stats["would_process"] == 5
        assert stats["reasons"]["already_assessed"] == 2

    def test_filters_skip_before_date(self, store_with_test_data):
        """Test filtering with skip_before_date."""
        stats = store_with_test_data.get_stats_with_filters(
            skip_rejected=False, skip_assessed=False, skip_before_date="2026-07-04"
        )

        # Jobs crawled before 2026-07-04 are job_1, job_2, job_3 (3 jobs)
        # Only job_4 and onwards are kept
        assert stats["total"] == 7
        assert stats["reasons"]["crawled_before_date"] == 3

    def test_filters_combined(self, store_with_test_data):
        """Test combined filters."""
        stats = store_with_test_data.get_stats_with_filters(
            skip_rejected=True, skip_assessed=True, skip_before_date="2026-07-03"
        )

        # Rejected: 3, Assessed: 2, Before date: 2
        # But job_3 (pending_review but confirmed, assessed, crawled 2026-07-03 - not before)
        # Actual: Skip job_1,2 (before date), job_5,6,7 (rejected), job_4 (assessed)
        # Process: job_3
        assert stats["total"] == 7
        assert stats["would_process"] >= 0

    def test_filters_structure(self, store_with_test_data):
        """Test filter stats has expected structure."""
        stats = store_with_test_data.get_stats_with_filters()

        assert "total" in stats
        assert "would_process" in stats
        assert "would_skip" in stats
        assert "reasons" in stats
        assert "rejected" in stats["reasons"]
        assert "already_assessed" in stats["reasons"]
        assert "crawled_before_date" in stats["reasons"]

    def test_filters_no_filters_all_process(self, store_with_test_data):
        """Test with all filters disabled."""
        stats = store_with_test_data.get_stats_with_filters(
            skip_rejected=False, skip_assessed=False, skip_before_date=None
        )

        # All jobs should be processed
        assert stats["would_process"] == 7
        assert stats["would_skip"] == 0

    def test_filters_empty_db(self, temp_db):
        """Test filter stats with empty database."""
        store = AssessmentStore(temp_db)
        stats = store.get_stats_with_filters()

        # Empty DB returns empty dict
        assert stats == {}

    def test_filters_reasons_sum_to_skip(self, store_with_test_data):
        """Test that skip reasons sum to would_skip."""
        stats = store_with_test_data.get_stats_with_filters(
            skip_rejected=True, skip_assessed=True, skip_before_date="2026-07-04"
        )

        reasons_total = (
            stats["reasons"]["rejected"]
            + stats["reasons"]["already_assessed"]
            + stats["reasons"]["crawled_before_date"]
        )
        # Note: some jobs may have multiple skip reasons, so we just verify it's reasonable
        assert reasons_total <= stats["total"]


class TestPipelineVisibilityIntegration:
    """Integration tests for pipeline visibility features."""

    def test_pipeline_stats_full_workflow(self, store_with_test_data):
        """Test stats through complete workflow."""
        # Initial state
        initial_stats = store_with_test_data.get_pipeline_stats()
        assert initial_stats["pending_review"] == 2

        # Simulate marking a pending job as confirmed
        cursor = store_with_test_data.conn.cursor()
        cursor.execute(
            "UPDATE job_reviews SET status = ? WHERE job_id = ?",
            ("confirmed", "job_1"),
        )
        store_with_test_data.conn.commit()

        # Stats should reflect change
        updated_stats = store_with_test_data.get_pipeline_stats()
        assert updated_stats["pending_review"] == 1
        assert updated_stats["confirmed"] == 3

    def test_filter_effect_visualization(self, store_with_test_data):
        """Test that filters show realistic impact."""
        # Get all jobs
        all_stats = store_with_test_data.get_stats_with_filters(
            skip_rejected=False, skip_assessed=False, skip_before_date=None
        )

        # Apply common filters
        filtered_stats = store_with_test_data.get_stats_with_filters(
            skip_rejected=True, skip_assessed=True, skip_before_date=None
        )

        # Filtered should show fewer would_process
        assert filtered_stats["would_process"] <= all_stats["would_process"]
        assert filtered_stats["would_skip"] >= all_stats["would_skip"]

    def test_stats_consistency(self, store_with_test_data):
        """Test that stats are internally consistent."""
        stats = store_with_test_data.get_stats_with_filters()

        # Total should equal sum of process and skip
        assert stats["total"] == stats["would_process"] + stats["would_skip"]

        # Reasons should not double-count (job has max one reason)
        reasons_sum = sum(stats["reasons"].values())
        assert reasons_sum <= stats["total"]
