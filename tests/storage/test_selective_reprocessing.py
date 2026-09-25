"""Unit and integration tests for Phase 3C selective filtering (Issue #230)."""

import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator

import pytest

from src.storage.job_store import JobStore


@pytest.fixture
def temp_db() -> Generator[str, None, None]:
    """Create temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        yield db_path


class TestJobStoreSelectiveFiltering:
    """Test selective filtering methods in JobStore (Phase 3C)."""

    def test_get_jobs_for_reprocessing_basic_version_filter(self, temp_db: str) -> None:
        """Test basic version filtering returns only v1.0 jobs."""
        store = JobStore(temp_db)

        # Add v1.0 and v2.0 jobs
        store.add_job(
            job_id="job_v1_1",
            title="Job V1",
            company="Company A",
            preprocessing_version="v1.0",
            tokens=500,
        )
        store.add_job(
            job_id="job_v2_1",
            title="Job V2",
            company="Company A",
            preprocessing_version="v2.0",
            tokens=300,
        )

        # Query for v1.0 jobs
        jobs = store.get_jobs_for_reprocessing(version="v1.0")

        assert len(jobs) == 1
        assert jobs[0]["job_id"] == "job_v1_1"
        assert jobs[0]["preprocessing_version"] == "v1.0"

        store.close()

    def test_get_jobs_for_reprocessing_version_normalization(self, temp_db: str) -> None:
        """Test that version '1.0' and 'v1.0' are treated identically."""
        store = JobStore(temp_db)

        store.add_job(
            job_id="job_1",
            title="Test Job",
            preprocessing_version="v1.0",
            tokens=500,
        )

        # Query with 'v1.0'
        jobs_v = store.get_jobs_for_reprocessing(version="v1.0")
        # Query with '1.0'
        jobs_plain = store.get_jobs_for_reprocessing(version="1.0")

        assert len(jobs_v) == 1
        assert len(jobs_plain) == 1
        assert jobs_v[0]["job_id"] == jobs_plain[0]["job_id"]

        store.close()

    def test_get_jobs_for_reprocessing_invalid_version(self, temp_db: str) -> None:
        """Test that invalid version raises ValueError."""
        store = JobStore(temp_db)

        with pytest.raises(ValueError, match="Invalid preprocessing version"):
            store.get_jobs_for_reprocessing(version="v4.0")

        store.close()

    def test_get_jobs_for_reprocessing_v3_version(self, temp_db: str) -> None:
        """Test that v3.0 version is now valid (Issue #281 S5)."""
        store = JobStore(temp_db)

        # Add some test jobs
        store.add_job("job1", "Job 1", "Co1", "Remote", preprocessing_version="v3.0", tokens=500)
        store.add_job("job2", "Job 2", "Co2", "Remote", preprocessing_version="v2.0", tokens=400)

        # Query for v3.0 jobs should work without raising an error
        jobs = store.get_jobs_for_reprocessing(version="v3.0")
        assert len(jobs) == 1
        assert jobs[0]["job_id"] == "job1"

        store.close()

    def test_get_jobs_for_reprocessing_age_filter(self, temp_db: str) -> None:
        """Test age filtering returns only jobs preprocessed N+ days ago."""
        store = JobStore(temp_db)

        # Manually insert jobs with different preprocessed_at timestamps
        assert store.conn is not None
        cursor = store.conn.cursor()
        now = datetime.now()
        old_time = now - timedelta(days=31)
        recent_time = now - timedelta(days=5)

        cursor.execute(
            """INSERT INTO job_reviews
               (job_id, title, preprocessing_version, tokens, preprocessed_at)
               VALUES (?, ?, ?, ?, ?)""",
            ("old_job", "Old Job", "v1.0", 500, old_time.isoformat()),
        )
        cursor.execute(
            """INSERT INTO job_reviews
               (job_id, title, preprocessing_version, tokens, preprocessed_at)
               VALUES (?, ?, ?, ?, ?)""",
            ("recent_job", "Recent Job", "v1.0", 600, recent_time.isoformat()),
        )
        store.conn.commit()

        # Filter for jobs at least 30 days old
        jobs = store.get_jobs_for_reprocessing(version="v1.0", min_age_days=30)

        assert len(jobs) == 1
        assert jobs[0]["job_id"] == "old_job"

        store.close()

    def test_get_jobs_for_reprocessing_token_filter(self, temp_db: str) -> None:
        """Test token filtering returns only high-token jobs."""
        store = JobStore(temp_db)

        # Add jobs with varying token counts
        store.add_job("job_100", "Title 1", tokens=100, preprocessing_version="v1.0")
        store.add_job("job_500", "Title 2", tokens=500, preprocessing_version="v1.0")
        store.add_job("job_1000", "Title 3", tokens=1000, preprocessing_version="v1.0")
        store.add_job("job_1500", "Title 4", tokens=1500, preprocessing_version="v1.0")

        # Filter for jobs with 1000+ tokens (most savings potential)
        jobs = store.get_jobs_for_reprocessing(version="v1.0", min_tokens=1000)

        assert len(jobs) == 2
        job_ids = {j["job_id"] for j in jobs}
        assert job_ids == {"job_1000", "job_1500"}

        store.close()

    def test_get_jobs_for_reprocessing_company_filter(self, temp_db: str) -> None:
        """Test company filtering restricts to specific companies."""
        store = JobStore(temp_db)

        # Add jobs from different companies
        store.add_job("amazon_1", "Job 1", company="Amazon", preprocessing_version="v1.0", tokens=500)
        store.add_job("google_1", "Job 2", company="Google", preprocessing_version="v1.0", tokens=500)
        store.add_job("meta_1", "Job 3", company="Meta", preprocessing_version="v1.0", tokens=500)
        store.add_job("amazon_2", "Job 4", company="Amazon", preprocessing_version="v1.0", tokens=500)

        # Filter for Amazon and Google only
        jobs = store.get_jobs_for_reprocessing(version="v1.0", company_names=["Amazon", "Google"])

        assert len(jobs) == 3
        job_ids = {j["job_id"] for j in jobs}
        assert job_ids == {"amazon_1", "google_1", "amazon_2"}

        store.close()

    def test_get_jobs_for_reprocessing_combined_filters(self, temp_db: str) -> None:
        """Test combining multiple filters (age + token + company)."""
        store = JobStore(temp_db)

        # Setup: old jobs with high token count from Amazon
        assert store.conn is not None
        cursor = store.conn.cursor()
        old_time = (datetime.now() - timedelta(days=35)).isoformat()

        cursor.execute(
            """INSERT INTO job_reviews
               (job_id, title, company, preprocessing_version, tokens, preprocessed_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("amazon_old_1000", "Old Amazon Job", "Amazon", "v1.0", 1000, old_time),
        )
        cursor.execute(
            """INSERT INTO job_reviews
               (job_id, title, company, preprocessing_version, tokens, preprocessed_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("amazon_old_500", "Old Amazon Job 2", "Amazon", "v1.0", 500, old_time),
        )
        cursor.execute(
            """INSERT INTO job_reviews
               (job_id, title, company, preprocessing_version, tokens, preprocessed_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("google_old_1000", "Old Google Job", "Google", "v1.0", 1000, old_time),
        )

        # Recent job from Amazon (should be filtered out by age)
        recent_time = (datetime.now() - timedelta(days=5)).isoformat()
        cursor.execute(
            """INSERT INTO job_reviews
               (job_id, title, company, preprocessing_version, tokens, preprocessed_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("amazon_recent_1000", "Recent Amazon Job", "Amazon", "v1.0", 1000, recent_time),
        )

        store.conn.commit()

        # Filter: v1.0, 30+ days old, 1000+ tokens, Amazon only
        jobs = store.get_jobs_for_reprocessing(
            version="v1.0",
            min_age_days=30,
            min_tokens=1000,
            company_names=["Amazon"],
        )

        assert len(jobs) == 1
        assert jobs[0]["job_id"] == "amazon_old_1000"

        store.close()

    def test_get_jobs_for_reprocessing_limit_enforcement(self, temp_db: str) -> None:
        """Test that limit parameter restricts batch size."""
        store = JobStore(temp_db)

        # Add 10 v1.0 jobs
        for i in range(10):
            store.add_job(f"job_{i}", f"Title {i}", preprocessing_version="v1.0", tokens=500)

        # Query with limit=5
        jobs = store.get_jobs_for_reprocessing(version="v1.0", limit=5)

        assert len(jobs) == 5

        store.close()

    def test_get_jobs_for_reprocessing_ordered_by_age(self, temp_db: str) -> None:
        """Test that results are ordered by preprocessed_at ASC (oldest first)."""
        store = JobStore(temp_db)

        assert store.conn is not None
        cursor = store.conn.cursor()
        now = datetime.now()

        # Insert jobs in reverse chronological order
        for days_ago in [5, 15, 10, 20, 1]:
            timestamp = (now - timedelta(days=days_ago)).isoformat()
            cursor.execute(
                """INSERT INTO job_reviews
                   (job_id, title, preprocessing_version, tokens, preprocessed_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (f"job_{days_ago}", f"Job {days_ago}", "v1.0", 500, timestamp),
            )
        store.conn.commit()

        # Get all jobs
        jobs = store.get_jobs_for_reprocessing(version="v1.0")

        # Should be ordered oldest first (20, 15, 10, 5, 1)
        job_ids = [j["job_id"] for j in jobs]
        assert job_ids == ["job_20", "job_15", "job_10", "job_5", "job_1"]

        store.close()

    def test_get_jobs_for_reprocessing_empty_result(self, temp_db: str) -> None:
        """Test that filtering with no matches returns empty list."""
        store = JobStore(temp_db)

        store.add_job("job_1", "Title", company="Amazon", preprocessing_version="v1.0", tokens=500)

        # Filter for non-existent company
        jobs = store.get_jobs_for_reprocessing(version="v1.0", company_names=["Google"])

        assert len(jobs) == 0

        store.close()

    def test_get_jobs_for_reprocessing_no_connection(self) -> None:
        """Test that filtering without database connection returns empty list."""
        store = JobStore(":memory:")
        store.conn = None  # Simulate closed connection

        jobs = store.get_jobs_for_reprocessing(version="v1.0")

        assert jobs == []

    def test_get_jobs_for_reprocessing_with_null_tokens(self, temp_db: str) -> None:
        """Test that jobs with NULL tokens are handled gracefully."""
        store = JobStore(temp_db)

        assert store.conn is not None
        cursor = store.conn.cursor()
        cursor.execute(
            """INSERT INTO job_reviews
               (job_id, title, preprocessing_version, tokens, crawled_at)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            ("job_null_tokens", "Job with Null Tokens", "v1.0", None),
        )
        store.conn.commit()

        # Should not error on NULL tokens
        jobs = store.get_jobs_for_reprocessing(version="v1.0")

        assert len(jobs) == 1
        assert jobs[0]["tokens"] is None

        store.close()

    def test_get_jobs_for_reprocessing_token_filter_with_null(self, temp_db: str) -> None:
        """Test that NULL tokens are skipped by token filter."""
        store = JobStore(temp_db)

        assert store.conn is not None
        cursor = store.conn.cursor()
        cursor.execute(
            """INSERT INTO job_reviews
               (job_id, title, preprocessing_version, tokens, crawled_at)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            ("job_null", "Null Tokens Job", "v1.0", None),
        )
        cursor.execute(
            """INSERT INTO job_reviews
               (job_id, title, preprocessing_version, tokens, crawled_at)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            ("job_1500", "High Token Job", "v1.0", 1500),
        )
        store.conn.commit()

        # Filter for min_tokens=1000 should skip NULL
        jobs = store.get_jobs_for_reprocessing(version="v1.0", min_tokens=1000)

        assert len(jobs) == 1
        assert jobs[0]["job_id"] == "job_1500"

        store.close()

    def test_get_jobs_for_reprocessing_company_case_sensitivity(self, temp_db: str) -> None:
        """Test that company filtering is case-sensitive (exact match required)."""
        store = JobStore(temp_db)

        store.add_job("job_1", "Job", company="Amazon", preprocessing_version="v1.0", tokens=500)
        store.add_job("job_2", "Job", company="AMAZON", preprocessing_version="v1.0", tokens=500)

        # Filter for exact case "Amazon"
        jobs = store.get_jobs_for_reprocessing(version="v1.0", company_names=["Amazon"])

        assert len(jobs) == 1
        assert jobs[0]["company"] == "Amazon"

        store.close()


class TestSelectiveFilteringIntegration:
    """Integration tests for realistic re-preprocessing workflows."""

    def test_gradual_migration_workflow(self, temp_db: str) -> None:
        """Test realistic gradual migration: old v1.0 jobs in batches."""
        store = JobStore(temp_db)

        # Simulate 100 v1.0 jobs from varied dates
        assert store.conn is not None
        cursor = store.conn.cursor()
        now = datetime.now()

        for i in range(100):
            days_ago = 1 + (i % 60)  # 1-60 days old
            timestamp = (now - timedelta(days=days_ago)).isoformat()
            cursor.execute(
                """INSERT INTO job_reviews
                   (job_id, title, company, preprocessing_version, tokens, preprocessed_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    f"job_{i}",
                    f"Title {i}",
                    ["Amazon", "Google", "Meta"][i % 3],
                    "v1.0",
                    500 + (i * 10),
                    timestamp,
                ),
            )
        store.conn.commit()

        # Batch 1: Process oldest 50 jobs from 30+ days ago
        batch_1 = store.get_jobs_for_reprocessing(version="v1.0", min_age_days=30, limit=50)
        assert len(batch_1) <= 50

        # Batch 2: Process next 50 jobs from 20+ days ago
        batch_2 = store.get_jobs_for_reprocessing(version="v1.0", min_age_days=20, limit=50)
        assert len(batch_2) <= 50

        # Verify batches were retrieved successfully
        assert batch_1 or batch_2  # At least one batch should have results

        store.close()

    def test_ab_testing_high_value_jobs(self, temp_db: str) -> None:
        """Test A/B testing: select high-token jobs from specific companies."""
        store = JobStore(temp_db)

        # Create jobs with varied tokens and companies
        for company in ["Amazon", "Google", "Meta"]:
            for tokens in [300, 600, 1200, 2000]:
                store.add_job(
                    f"{company.lower()}_job_{tokens}",
                    f"{company} Job",
                    company=company,
                    preprocessing_version="v1.0",
                    tokens=tokens,
                )

        # Select for A/B test: high-value jobs from Amazon and Google only
        ab_test_jobs = store.get_jobs_for_reprocessing(
            version="v1.0",
            min_tokens=1200,
            company_names=["Amazon", "Google"],
            limit=10,
        )

        assert len(ab_test_jobs) == 4  # 2 companies × 2 high-token jobs
        for job in ab_test_jobs:
            assert job["company"] in ["Amazon", "Google"]
            assert job["tokens"] >= 1200

        store.close()

    def test_token_optimization_targets(self, temp_db: str) -> None:
        """Test identifying jobs with maximum token savings potential."""
        store = JobStore(temp_db)

        # Create jobs with varied token counts
        for i, tokens in enumerate([100, 500, 800, 1200, 1500, 2000, 2500]):
            store.add_job(
                f"job_{i}",
                f"Job {i}",
                preprocessing_version="v1.0",
                tokens=tokens,
            )

        # Get jobs with highest savings potential (1500+ tokens)
        high_value = store.get_jobs_for_reprocessing(version="v1.0", min_tokens=1500, limit=5)

        assert len(high_value) == 3
        for job in high_value:
            assert job["tokens"] >= 1500

        store.close()
