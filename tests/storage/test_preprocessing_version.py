"""Tests for preprocessing version tracking (Phase 2)."""

import sqlite3
from pathlib import Path

import pytest

from src.verification.reviewer import JobReviewer


class TestPreprocessingVersionSchema:
    """Test preprocessing_version column in job_reviews table."""

    @pytest.fixture
    def reviewer(self, tmp_path: Path) -> JobReviewer:
        """Create temporary test database."""
        db_path = tmp_path / "test.db"
        reviewer = JobReviewer(str(db_path))
        return reviewer

    def test_preprocessing_version_column_exists(self, reviewer: JobReviewer) -> None:
        """Verify preprocessing_version column exists in job_reviews table."""
        assert reviewer.conn is not None, "Database not initialized"

        cursor = reviewer.conn.cursor()
        cursor.execute("PRAGMA table_info(job_reviews)")
        columns = {row[1] for row in cursor.fetchall()}

        assert "preprocessing_version" in columns, "preprocessing_version column not found"

    def test_preprocessing_version_default_is_v2(self, reviewer: JobReviewer) -> None:
        """Verify default preprocessing_version is v2.0 for new jobs."""
        assert reviewer.conn is not None, "Database not initialized"

        cursor = reviewer.conn.cursor()

        cursor.execute(
            """INSERT INTO job_reviews
               (job_id, title, location, company, status, crawled_at)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            ("test_job_1", "Test Title", "Remote", "TestCo", "pending"),
        )
        reviewer.conn.commit()

        cursor.execute("SELECT preprocessing_version FROM job_reviews WHERE job_id = ?", ("test_job_1",))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "v2.0", f"Expected default v2.0, got {row[0]}"

    def test_can_insert_v1_version(self, reviewer: JobReviewer) -> None:
        """Verify can insert and retrieve v1.0 version."""
        assert reviewer.conn is not None, "Database not initialized"

        cursor = reviewer.conn.cursor()

        cursor.execute(
            """INSERT INTO job_reviews
               (job_id, title, location, company, status, preprocessing_version, crawled_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            ("test_job_v1", "Test Title", "Remote", "TestCo", "pending", "v1.0"),
        )
        reviewer.conn.commit()

        cursor.execute("SELECT preprocessing_version FROM job_reviews WHERE job_id = ?", ("test_job_v1",))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "v1.0"

    def test_can_insert_v2_version(self, reviewer: JobReviewer) -> None:
        """Verify can insert and retrieve v2.0 version."""
        assert reviewer.conn is not None, "Database not initialized"

        cursor = reviewer.conn.cursor()

        cursor.execute(
            """INSERT INTO job_reviews
               (job_id, title, location, company, status, preprocessing_version, crawled_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            ("test_job_v2", "Test Title", "Remote", "TestCo", "pending", "v2.0"),
        )
        reviewer.conn.commit()

        cursor.execute("SELECT preprocessing_version FROM job_reviews WHERE job_id = ?", ("test_job_v2",))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "v2.0"

    def test_multiple_versions_coexist(self, reviewer: JobReviewer) -> None:
        """Verify v1.0 and v2.0 jobs can coexist in database."""
        assert reviewer.conn is not None, "Database not initialized"

        cursor = reviewer.conn.cursor()

        cursor.execute(
            """INSERT INTO job_reviews
               (job_id, title, location, company, status, preprocessing_version, crawled_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            ("job_v1_1", "Title1", "Remote", "Co1", "pending", "v1.0"),
        )

        cursor.execute(
            """INSERT INTO job_reviews
               (job_id, title, location, company, status, preprocessing_version, crawled_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            ("job_v2_1", "Title2", "Remote", "Co2", "pending", "v2.0"),
        )

        reviewer.conn.commit()

        cursor.execute("SELECT COUNT(*) as count FROM job_reviews WHERE preprocessing_version = ?", ("v1.0",))
        v1_count = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM job_reviews WHERE preprocessing_version = ?", ("v2.0",))
        v2_count = cursor.fetchone()["count"]

        assert v1_count == 1
        assert v2_count == 1
