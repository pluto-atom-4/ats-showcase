"""Tests for Issue #102 Phase 4: Job Timeline Visibility."""

import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.verification.reviewer import JobReviewer


@pytest.fixture
def temp_db():
    """Create temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def reviewer_with_jobs(temp_db):
    """Create reviewer with test jobs and timeline data."""
    reviewer = JobReviewer(temp_db)

    if reviewer.conn:
        cursor = reviewer.conn.cursor()

        # Insert test jobs with full timeline
        jobs = [
            {
                "job_id": "job_1",
                "title": "Python Dev",
                "company": "TechCorp",
                "location": "Remote",
                "status": "confirmed",
                "crawled_at": "2026-07-01T10:00:00+00:00",
                "preprocessed_at": "2026-07-01T10:05:00+00:00",
                "reviewed_at": "2026-07-01T14:22:00+00:00",
            },
            {
                "job_id": "job_2",
                "title": "ML Engineer",
                "company": "DataCorp",
                "location": "NYC",
                "status": "confirmed",
                "crawled_at": "2026-07-02T09:00:00+00:00",
                "preprocessed_at": "2026-07-02T09:10:00+00:00",
                "reviewed_at": "2026-07-02T15:30:00+00:00",
            },
            {
                "job_id": "job_3",
                "title": "DevOps",
                "company": "CloudInc",
                "location": "SF",
                "status": "pending_review",
                "crawled_at": "2026-07-03T08:00:00+00:00",
                "preprocessed_at": None,  # Not preprocessed yet
                "reviewed_at": None,
            },
        ]

        for job in jobs:
            cursor.execute(
                """INSERT INTO job_reviews
                   (job_id, title, company, location, status, crawled_at, preprocessed_at, reviewed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job["job_id"],
                    job["title"],
                    job["company"],
                    job["location"],
                    job["status"],
                    job["crawled_at"],
                    job["preprocessed_at"],
                    job["reviewed_at"],
                ),
            )

        # Create job_assessments table
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
               summary TEXT,
               tokens_used INTEGER,
               input_tokens INTEGER DEFAULT 0,
               output_tokens INTEGER DEFAULT 0,
               actual_cost REAL,
               assessed_date TIMESTAMP
            )"""
        )

        # Add assessments for jobs 1 and 2
        cursor.execute(
            """INSERT INTO job_assessments
               (job_id, title, company, overall_score, assessed_date)
               VALUES (?, ?, ?, ?, ?)""",
            ("job_1", "Python Dev", "TechCorp", 85.0, "2026-07-01T16:00:00+00:00"),
        )
        cursor.execute(
            """INSERT INTO job_assessments
               (job_id, title, company, overall_score, assessed_date)
               VALUES (?, ?, ?, ?, ?)""",
            ("job_2", "ML Engineer", "DataCorp", 92.0, "2026-07-02T17:15:00+00:00"),
        )

        reviewer.conn.commit()

    return reviewer


class TestJobTimeline:
    """Test job timeline tracking and display."""

    def test_get_job_timeline_full(self, reviewer_with_jobs):
        """Test retrieving full timeline for a job."""
        timeline = reviewer_with_jobs.get_job_timeline("job_1")

        assert timeline is not None
        assert timeline["crawled_at"] == "2026-07-01T10:00:00+00:00"
        assert timeline["preprocessed_at"] == "2026-07-01T10:05:00+00:00"
        assert timeline["reviewed_at"] == "2026-07-01T14:22:00+00:00"
        assert timeline["assessed_at"] == "2026-07-01T16:00:00+00:00"

    def test_get_job_timeline_partial(self, reviewer_with_jobs):
        """Test timeline with missing stages."""
        timeline = reviewer_with_jobs.get_job_timeline("job_3")

        assert timeline is not None
        assert timeline["crawled_at"] == "2026-07-03T08:00:00+00:00"
        assert timeline["preprocessed_at"] is None
        assert timeline["reviewed_at"] is None
        assert timeline["assessed_at"] is None

    def test_get_job_timeline_nonexistent(self, reviewer_with_jobs):
        """Test timeline for nonexistent job."""
        timeline = reviewer_with_jobs.get_job_timeline("nonexistent_job")

        assert timeline is not None
        assert all(v is None for v in timeline.values())

    def test_set_preprocessed_at(self, reviewer_with_jobs):
        """Test setting preprocessed_at timestamp."""
        reviewer_with_jobs.set_preprocessed_at("job_3")

        timeline = reviewer_with_jobs.get_job_timeline("job_3")
        assert timeline["preprocessed_at"] is not None
        # Should be recent timestamp
        assert "2026-07" in timeline["preprocessed_at"]

    def test_set_crawled_at_explicit(self, temp_db):
        """Test setting crawled_at with explicit timestamp."""
        reviewer = JobReviewer(temp_db)
        reviewer.save_review("job_test", "Test Job", "Remote", "confirmed")
        reviewer.set_crawled_at("job_test", "2026-07-04T09:00:00+00:00")

        timeline = reviewer.get_job_timeline("job_test")
        assert timeline["crawled_at"] == "2026-07-04T09:00:00+00:00"
        reviewer._close_db()

    def test_set_crawled_at_auto(self, temp_db):
        """Test setting crawled_at with auto timestamp."""
        reviewer = JobReviewer(temp_db)
        reviewer.save_review("job_test", "Test Job", "Remote", "confirmed")
        reviewer.set_crawled_at("job_test")

        timeline = reviewer.get_job_timeline("job_test")
        assert timeline["crawled_at"] is not None
        assert "2026-07" in timeline["crawled_at"]
        reviewer._close_db()

    def test_format_timestamp_iso(self, reviewer_with_jobs):
        """Test timestamp formatting for ISO format."""
        formatted = reviewer_with_jobs._format_timestamp("2026-07-01T10:00:00+00:00")
        assert formatted == "2026-07-01 10:00"

    def test_format_timestamp_none(self, reviewer_with_jobs):
        """Test timestamp formatting for None."""
        formatted = reviewer_with_jobs._format_timestamp(None)
        assert formatted == "not processed"

    def test_format_timestamp_invalid(self, reviewer_with_jobs):
        """Test timestamp formatting for invalid input."""
        formatted = reviewer_with_jobs._format_timestamp("invalid_timestamp")
        assert "invalid" in formatted.lower() or len(formatted) > 0

    def test_timeline_sequence(self, reviewer_with_jobs):
        """Test that timeline events occur in correct sequence."""
        timeline = reviewer_with_jobs.get_job_timeline("job_1")

        # Parse timestamps
        crawled = datetime.fromisoformat(timeline["crawled_at"].replace("Z", "+00:00"))
        preprocessed = datetime.fromisoformat(
            timeline["preprocessed_at"].replace("Z", "+00:00")
        )
        reviewed = datetime.fromisoformat(timeline["reviewed_at"].replace("Z", "+00:00"))
        assessed = datetime.fromisoformat(timeline["assessed_at"].replace("Z", "+00:00"))

        # Verify sequence
        assert crawled < preprocessed < reviewed < assessed

    def test_timeline_data_consistency(self, reviewer_with_jobs):
        """Test that timeline data remains consistent after updates."""
        job_id = "job_1"

        # Get initial timeline
        timeline_1 = reviewer_with_jobs.get_job_timeline(job_id)

        # Save a new review (should preserve timeline fields)
        reviewer_with_jobs.save_review(
            job_id, "Python Dev (Updated)", "Remote", "confirmed", company="TechCorp"
        )

        # Get timeline again
        timeline_2 = reviewer_with_jobs.get_job_timeline(job_id)

        # crawled_at and preprocessed_at should still exist
        assert timeline_2["crawled_at"] == timeline_1["crawled_at"]
        assert timeline_2["preprocessed_at"] == timeline_1["preprocessed_at"]


class TestTimelineIntegration:
    """Integration tests for timeline with review workflow."""

    def test_timeline_display_integration(self, reviewer_with_jobs, capsys):
        """Test that timeline can be displayed without errors."""
        reviewer_with_jobs._display_job_timeline("job_1")

        captured = capsys.readouterr()
        assert "Timeline" in captured.out or "Crawled" in captured.out

    def test_complete_job_lifecycle(self, temp_db):
        """Test complete job lifecycle from crawl to assessment."""
        reviewer = JobReviewer(temp_db)

        job_id = "lifecycle_test"

        # Step 1: Save initial review (with crawled_at)
        reviewer.save_review(
            job_id, "Test Job", "Remote", "pending_review", company="TestCorp"
        )
        reviewer.set_crawled_at(job_id, "2026-07-01T08:00:00+00:00")

        # Step 2: Preprocess
        reviewer.set_preprocessed_at(job_id)

        # Step 3: Review
        reviewer.save_review(
            job_id,
            "Test Job",
            "Remote",
            "confirmed",
            tokens=500,
            estimated_cost=0.0015,
            company="TestCorp",
        )

        # Verify timeline
        timeline = reviewer.get_job_timeline(job_id)
        assert timeline["crawled_at"] == "2026-07-01T08:00:00+00:00"
        assert timeline["preprocessed_at"] is not None
        assert timeline["reviewed_at"] is not None

        reviewer._close_db()

    def test_timeline_with_multiple_reviews(self, temp_db):
        """Test timeline when job is reviewed multiple times."""
        from src.verification.reviewer import ReviewStats

        reviewer = JobReviewer(temp_db)

        job_id = "multi_review_job"

        # First review
        reviewer.save_review(
            job_id, "Job Title", "Remote", "confirmed", company="Corp1"
        )
        first_reviewed = reviewer.get_prior_review(job_id)

        # Re-review
        reviewer.save_review(
            job_id, "Job Title", "Remote", "rejected", reason="location", company="Corp1"
        )
        second_reviewed = reviewer.get_prior_review(job_id)

        # Both should have reviewed_at set
        assert first_reviewed is not None
        assert second_reviewed is not None
        assert second_reviewed.get("reviewed_at") is not None

        reviewer._close_db()
