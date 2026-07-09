"""Unit tests for job verification module (Phase 3)."""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from verification import JobReviewer, ReviewStats


class TestReviewStats:
    """Test ReviewStats tracking."""

    def test_init(self):
        """Test stats initialization."""
        stats = ReviewStats()
        assert stats.total == 0
        assert stats.confirmed == 0
        assert stats.rejected == 0
        assert stats.skipped == 0

    def test_add_confirmed(self):
        """Test recording confirmed jobs."""
        stats = ReviewStats()
        stats.add_confirmed(100, 0.0003)
        assert stats.confirmed == 1
        assert stats.total_tokens == 100
        assert stats.total_cost == 0.0003

    def test_add_rejected(self):
        """Test recording rejected jobs."""
        stats = ReviewStats()
        stats.add_rejected("location")
        assert stats.rejected == 1
        assert stats.rejection_reasons["location"] == 1

    def test_add_skipped(self):
        """Test recording skipped jobs."""
        stats = ReviewStats()
        stats.add_skipped()
        assert stats.skipped == 1

    def test_get_summary(self):
        """Test summary generation."""
        stats = ReviewStats()
        stats.total = 5
        stats.confirmed = 3
        stats.rejected = 2
        summary = stats.get_summary()
        assert "3" in summary
        assert "2" in summary


class TestJobReviewer:
    """Test JobReviewer class."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        Path(db_path).unlink(missing_ok=True)

    def test_init_creates_db(self, temp_db):
        """Test reviewer initialization creates database."""
        reviewer = JobReviewer(db_path=temp_db)
        reviewer._close_db()

        assert Path(temp_db).exists()

    def test_save_and_retrieve_review(self, temp_db):
        """Test saving and retrieving reviews."""
        reviewer = JobReviewer(db_path=temp_db)

        # Save a confirmed job
        reviewer.save_review(
            job_id="job_1",
            title="Engineer",
            location="SF",
            status="confirmed",
            tokens=100,
            estimated_cost=0.0003,
        )

        # Retrieve and verify
        status = reviewer.get_review_status("job_1")
        assert status == "confirmed"

        reviewer._close_db()

    def test_save_and_retrieve_review_with_company(self, temp_db):
        """Test saving and retrieving reviews with company field."""
        reviewer = JobReviewer(db_path=temp_db)

        # Save a confirmed job with company
        reviewer.save_review(
            job_id="job_1",
            title="Senior Engineer",
            location="SF",
            company="TechCorp",
            status="confirmed",
            tokens=150,
            estimated_cost=0.00045,
        )

        # Retrieve and verify
        status = reviewer.get_review_status("job_1")
        assert status == "confirmed"

        # Verify company is stored
        confirmed = reviewer.get_confirmed_jobs()
        assert len(confirmed) == 1
        assert confirmed[0]["company"] == "TechCorp"

        reviewer._close_db()

    def test_save_rejection_with_reason(self, temp_db):
        """Test saving rejections with reasons."""
        reviewer = JobReviewer(db_path=temp_db)

        reviewer.save_review(
            job_id="job_2",
            title="Role",
            location="NYC",
            status="rejected",
            reason="location",
        )

        status = reviewer.get_review_status("job_2")
        assert status == "rejected"

        reviewer._close_db()

    def test_get_confirmed_jobs(self, temp_db):
        """Test retrieving confirmed jobs."""
        reviewer = JobReviewer(db_path=temp_db)

        reviewer.save_review(
            "job_1", "Engineer", "SF", "confirmed", tokens=100, estimated_cost=0.0003
        )
        reviewer.save_review("job_2", "Designer", "NYC", "rejected", reason="location")
        reviewer.save_review(
            "job_3", "Manager", "LA", "confirmed", tokens=80, estimated_cost=0.0002
        )

        confirmed = reviewer.get_confirmed_jobs()
        assert len(confirmed) == 2
        assert confirmed[0]["job_id"] == "job_1"
        assert confirmed[1]["job_id"] == "job_3"

        reviewer._close_db()

    def test_review_status_skip_reviewed(self, temp_db):
        """Test that already-reviewed jobs are skipped."""
        reviewer = JobReviewer(db_path=temp_db)

        reviewer.save_review("job_1", "Engineer", "SF", "confirmed", tokens=100)
        status = reviewer.get_review_status("job_1")
        assert status == "confirmed"

        reviewer._close_db()

    def test_database_schema_exists(self, temp_db):
        """Test that database schema is correctly created."""
        reviewer = JobReviewer(db_path=temp_db)

        # Verify table exists
        cursor = reviewer.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='job_reviews'")
        assert cursor.fetchone() is not None

        reviewer._close_db()

    def test_database_persistence(self, temp_db):
        """Test that database changes persist across connections."""
        # First connection
        reviewer1 = JobReviewer(db_path=temp_db)
        reviewer1.save_review("job_1", "Engineer", "SF", "confirmed", tokens=100)
        reviewer1._close_db()

        # Second connection
        reviewer2 = JobReviewer(db_path=temp_db)
        status = reviewer2.get_review_status("job_1")
        assert status == "confirmed"
        reviewer2._close_db()


class TestFilteringMethods:
    """Test Phase 3 filtering methods."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        Path(db_path).unlink(missing_ok=True)

    def test_check_review_status_rejected(self, temp_db):
        """Test filtering rejected jobs."""
        reviewer = JobReviewer(db_path=temp_db)
        reviewer.save_review("job_1", "Engineer", "SF", "rejected", reason="location")

        skip, reason = reviewer._check_review_status("job_1", skip_rejected=True)
        assert skip is True
        assert reason == "previously_rejected"

        reviewer._close_db()

    def test_check_review_status_no_skip_rejected(self, temp_db):
        """Test not filtering rejected jobs when skip_rejected=False."""
        reviewer = JobReviewer(db_path=temp_db)
        reviewer.save_review("job_1", "Engineer", "SF", "rejected", reason="location")

        skip, reason = reviewer._check_review_status("job_1", skip_rejected=False)
        assert skip is False
        assert reason is None

        reviewer._close_db()

    def test_check_review_status_confirmed(self, temp_db):
        """Test that confirmed jobs are NOT skipped by status filter alone.

        Mode filter (new-only vs all) handles skipping already-reviewed jobs.
        Status filter only checks skip_rejected flag.
        """
        reviewer = JobReviewer(db_path=temp_db)
        reviewer.save_review("job_1", "Engineer", "SF", "confirmed", tokens=100)

        skip, reason = reviewer._check_review_status("job_1", skip_rejected=True)
        assert skip is False  # Confirmed jobs not skipped by status filter
        assert reason is None

        reviewer._close_db()

    def test_check_review_status_not_reviewed(self, temp_db):
        """Test non-reviewed job doesn't skip."""
        reviewer = JobReviewer(db_path=temp_db)

        skip, reason = reviewer._check_review_status("job_1", skip_rejected=True)
        assert skip is False
        assert reason is None

        reviewer._close_db()

    def test_check_assessment_status_assessed(self, temp_db):
        """Test filtering assessed jobs."""
        reviewer = JobReviewer(db_path=temp_db)

        # Create job_assessments table
        if reviewer.conn:
            cursor = reviewer.conn.cursor()
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS job_assessments (
                   job_id TEXT PRIMARY KEY,
                   overall_score REAL
                )"""
            )
            cursor.execute("INSERT INTO job_assessments VALUES ('job_1', 85.0)")
            reviewer.conn.commit()

        skip, reason = reviewer._check_assessment_status("job_1")
        assert skip is True
        assert reason == "already_assessed"

        reviewer._close_db()

    def test_check_assessment_status_not_assessed(self, temp_db):
        """Test non-assessed job doesn't skip."""
        reviewer = JobReviewer(db_path=temp_db)

        # Create table but leave empty
        if reviewer.conn:
            cursor = reviewer.conn.cursor()
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS job_assessments (
                   job_id TEXT PRIMARY KEY,
                   overall_score REAL
                )"""
            )
            reviewer.conn.commit()

        skip, reason = reviewer._check_assessment_status("job_1")
        assert skip is False
        assert reason is None

        reviewer._close_db()

    def test_check_crawled_date_before_threshold(self, temp_db):
        """Test filtering jobs crawled before date."""
        reviewer = JobReviewer(db_path=temp_db)

        # Create jobs table with crawled_at
        if reviewer.conn:
            cursor = reviewer.conn.cursor()
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS jobs (
                   id TEXT PRIMARY KEY,
                   crawled_at TEXT
                )"""
            )
            cursor.execute("INSERT INTO jobs VALUES ('job_1', '2026-06-01')")
            reviewer.conn.commit()

        skip, reason = reviewer._check_crawled_date("job_1", "2026-07-01")
        assert skip is True
        assert "crawled_before" in reason

        reviewer._close_db()

    def test_check_crawled_date_after_threshold(self, temp_db):
        """Test job crawled after threshold doesn't skip."""
        reviewer = JobReviewer(db_path=temp_db)

        # Create jobs table
        if reviewer.conn:
            cursor = reviewer.conn.cursor()
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS jobs (
                   id TEXT PRIMARY KEY,
                   crawled_at TEXT
                )"""
            )
            cursor.execute("INSERT INTO jobs VALUES ('job_1', '2026-07-05')")
            reviewer.conn.commit()

        skip, reason = reviewer._check_crawled_date("job_1", "2026-07-01")
        assert skip is False
        assert reason is None

        reviewer._close_db()

    def test_should_skip_job_all_filters(self, temp_db):
        """Test should_skip_job with all filters combined."""
        reviewer = JobReviewer(db_path=temp_db)

        # Setup: rejected job + jobs table
        reviewer.save_review("job_1", "Engineer", "SF", "rejected", reason="location")
        if reviewer.conn:
            cursor = reviewer.conn.cursor()
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS jobs (
                   id TEXT PRIMARY KEY,
                   crawled_at TEXT
                )"""
            )
            cursor.execute("INSERT INTO jobs VALUES ('job_1', '2026-06-01')")
            reviewer.conn.commit()

        # Should skip due to rejection (test with mode="all" to bypass mode filter)
        skip, reason = reviewer.should_skip_job(
            "job_1", mode="all", skip_before_date="2026-07-01", skip_rejected=True, skip_assessed=False
        )
        assert skip is True
        assert reason == "previously_rejected"

        reviewer._close_db()

    def test_should_skip_job_date_filter_only(self, temp_db):
        """Test should_skip_job date filter only."""
        reviewer = JobReviewer(db_path=temp_db)

        if reviewer.conn:
            cursor = reviewer.conn.cursor()
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS jobs (
                   id TEXT PRIMARY KEY,
                   crawled_at TEXT
                )"""
            )
            cursor.execute("INSERT INTO jobs VALUES ('job_1', '2026-06-01')")
            reviewer.conn.commit()

        skip, reason = reviewer.should_skip_job(
            "job_1", mode="all", skip_before_date="2026-07-01", skip_rejected=False, skip_assessed=False
        )
        assert skip is True
        assert "crawled_before" in reason

        reviewer._close_db()

    def test_should_skip_job_no_filters(self, temp_db):
        """Test should_skip_job with no matching filters."""
        reviewer = JobReviewer(db_path=temp_db)

        skip, reason = reviewer.should_skip_job(
            "job_1", mode="all", skip_before_date=None, skip_rejected=False, skip_assessed=False
        )
        assert skip is False
        assert reason is None

        reviewer._close_db()


class TestSkipAction:
    """Test skip action persistence (Issue #119)."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        Path(db_path).unlink(missing_ok=True)

    def test_skip_saves_pending_review_status(self, temp_db):
        """Test that skip action saves job with status='pending_review'."""
        reviewer = JobReviewer(db_path=temp_db)

        reviewer.save_review(
            job_id="job_1",
            title="Engineer",
            location="SF",
            status="pending_review",
            company="TechCorp",
        )

        status = reviewer.get_review_status("job_1")
        assert status == "pending_review"

        reviewer._close_db()

    def test_skip_persists_across_sessions(self, temp_db):
        """Test that skipped jobs persist to database and can be retrieved."""
        # First session: skip a job
        reviewer1 = JobReviewer(db_path=temp_db)
        reviewer1.save_review(
            job_id="job_1",
            title="Senior Python Dev",
            location="Remote",
            status="pending_review",
            company="TechCorp",
        )
        reviewer1._close_db()

        # Second session: verify job exists with pending_review status
        reviewer2 = JobReviewer(db_path=temp_db)
        status = reviewer2.get_review_status("job_1")
        assert status == "pending_review"
        reviewer2._close_db()

    def test_skip_creates_job_reviews_entry(self, temp_db):
        """Test that skip action creates an entry in job_reviews table."""
        reviewer = JobReviewer(db_path=temp_db)

        reviewer.save_review(
            job_id="job_1",
            title="Role",
            location="NYC",
            status="pending_review",
            company="Corp",
        )

        # Verify entry exists
        if reviewer.conn:
            cursor = reviewer.conn.cursor()
            cursor.execute("SELECT * FROM job_reviews WHERE job_id = ?", ("job_1",))
            row = cursor.fetchone()
            assert row is not None
            assert row["status"] == "pending_review"
            assert row["title"] == "Role"
            assert row["company"] == "Corp"

        reviewer._close_db()

    def test_confirm_reject_skip_all_recorded(self, temp_db):
        """Test that confirm, reject, and skip all create database records."""
        reviewer = JobReviewer(db_path=temp_db)

        # Confirm
        reviewer.save_review("job_1", "Engineer", "SF", "confirmed", tokens=100)
        # Reject
        reviewer.save_review("job_2", "Designer", "NYC", "rejected", reason="location")
        # Skip
        reviewer.save_review("job_3", "Manager", "LA", "pending_review")

        assert reviewer.get_review_status("job_1") == "confirmed"
        assert reviewer.get_review_status("job_2") == "rejected"
        assert reviewer.get_review_status("job_3") == "pending_review"

        # Verify all 3 are in database
        if reviewer.conn:
            cursor = reviewer.conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM job_reviews")
            count = cursor.fetchone()["count"]
            assert count == 3

        reviewer._close_db()

    def test_skipped_job_reappears_in_new_only_mode(self, temp_db):
        """Test that skipped (pending_review) jobs reappear when using mode='new-only'."""
        reviewer = JobReviewer(db_path=temp_db)

        # Skip a job (status="pending_review")
        reviewer.save_review("job_1", "Engineer", "SF", "pending_review")

        # In new-only mode, pending_review jobs should be re-presented (not skipped)
        skip, reason = reviewer.should_skip_job(
            "job_1", mode="new-only", skip_before_date=None, skip_rejected=True, skip_assessed=False
        )
        assert skip is False
        assert reason is None

        reviewer._close_db()

    def test_confirmed_job_skipped_in_new_only_mode(self, temp_db):
        """Test that confirmed jobs are skipped in new-only mode."""
        reviewer = JobReviewer(db_path=temp_db)

        reviewer.save_review("job_1", "Engineer", "SF", "confirmed", tokens=100)

        skip, reason = reviewer.should_skip_job(
            "job_1", mode="new-only", skip_before_date=None, skip_rejected=True, skip_assessed=False
        )
        assert skip is True
        assert reason == "already_reviewed"

        reviewer._close_db()

    def test_rejected_job_skipped_in_new_only_mode(self, temp_db):
        """Test that rejected jobs are skipped in new-only mode."""
        reviewer = JobReviewer(db_path=temp_db)

        reviewer.save_review("job_1", "Designer", "NYC", "rejected", reason="location")

        skip, reason = reviewer.should_skip_job(
            "job_1", mode="new-only", skip_before_date=None, skip_rejected=True, skip_assessed=False
        )
        assert skip is True
        assert reason == "already_reviewed"

        reviewer._close_db()
