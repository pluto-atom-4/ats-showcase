"""Tests for JobStore API methods (Phase 2)."""

import sqlite3
from pathlib import Path

import pytest

from src.storage.job_store import JobStore


class TestJobStoreUpdatePreprocessingVersion:
    """Test update_preprocessing_version() method."""

    @pytest.fixture
    def store(self, tmp_path: Path) -> JobStore:
        """Create temporary test database."""
        db_path = tmp_path / "test.db"
        store = JobStore(str(db_path))
        return store

    def test_update_version_v1_to_v2(self, store: JobStore) -> None:
        """Update job version from v1.0 to v2.0."""
        # Add test job with v1.0
        store.add_job(
            job_id="job1",
            title="Test Job",
            company="TestCo",
            location="Remote",
            preprocessing_version="v1.0",
        )

        # Update to v2.0
        store.update_preprocessing_version("job1", "v2.0")

        # Verify
        job = store.get_job("job1")
        assert job is not None
        assert job["preprocessing_version"] == "v2.0"

    def test_update_version_v2_to_v3(self, store: JobStore) -> None:
        """Update job version from v2.0 to v3.0 (Issue #281 S5)."""
        # Add test job with v2.0
        store.add_job(
            job_id="job1",
            title="Test Job",
            company="TestCo",
            location="Remote",
            preprocessing_version="v2.0",
        )

        # Update to v3.0
        store.update_preprocessing_version("job1", "v3.0")

        # Verify
        job = store.get_job("job1")
        assert job is not None
        assert job["preprocessing_version"] == "v3.0"

    def test_update_version_normalize_format(self, store: JobStore) -> None:
        """Normalize version format (with or without 'v' prefix)."""
        store.add_job(
            job_id="job1",
            title="Test Job",
            company="TestCo",
            location="Remote",
            preprocessing_version="1.0",
        )

        # Update with version without 'v' prefix
        store.update_preprocessing_version("job1", "3.0")

        # Verify normalized to v-prefix format
        job = store.get_job("job1")
        assert job is not None
        assert job["preprocessing_version"] == "v3.0"

    def test_update_version_invalid_raises_error(self, store: JobStore) -> None:
        """Invalid version raises ValueError."""
        store.add_job(
            job_id="job1",
            title="Test Job",
            company="TestCo",
            location="Remote",
            preprocessing_version="v1.0",
        )

        with pytest.raises(ValueError, match="Invalid preprocessing version"):
            store.update_preprocessing_version("job1", "v4.0")

    def test_update_version_nonexistent_job_raises_error(self, store: JobStore) -> None:
        """Updating nonexistent job raises error."""
        with pytest.raises(sqlite3.OperationalError, match="Job not found"):
            store.update_preprocessing_version("nonexistent", "v2.0")


class TestJobStoreGetJobsByVersion:
    """Test get_jobs_by_version() method."""

    @pytest.fixture
    def store(self, tmp_path: Path) -> JobStore:
        """Create temporary test database."""
        db_path = tmp_path / "test.db"
        store = JobStore(str(db_path))
        return store

    def test_get_jobs_by_version_v1(self, store: JobStore) -> None:
        """Query returns only v1.0 jobs."""
        store.add_job(
            job_id="job1",
            title="Job 1",
            company="Co1",
            location="Remote",
            preprocessing_version="v1.0",
        )
        store.add_job(
            job_id="job2",
            title="Job 2",
            company="Co2",
            location="Remote",
            preprocessing_version="v2.0",
        )

        jobs = store.get_jobs_by_version("v1.0")
        assert len(jobs) == 1
        assert jobs[0]["job_id"] == "job1"

    def test_get_jobs_by_version_v2(self, store: JobStore) -> None:
        """Query returns only v2.0 jobs."""
        store.add_job(
            job_id="job1",
            title="Job 1",
            company="Co1",
            location="Remote",
            preprocessing_version="v1.0",
        )
        store.add_job(
            job_id="job2",
            title="Job 2",
            company="Co2",
            location="Remote",
            preprocessing_version="v2.0",
        )

        jobs = store.get_jobs_by_version("v2.0")
        assert len(jobs) == 1
        assert jobs[0]["job_id"] == "job2"

    def test_get_jobs_by_version_v3(self, store: JobStore) -> None:
        """Query returns only v3.0 jobs (Issue #281 S5)."""
        store.add_job(
            job_id="job1",
            title="Job 1",
            company="Co1",
            location="Remote",
            preprocessing_version="v2.0",
        )
        store.add_job(
            job_id="job2",
            title="Job 2",
            company="Co2",
            location="Remote",
            preprocessing_version="v3.0",
        )

        jobs = store.get_jobs_by_version("v3.0")
        assert len(jobs) == 1
        assert jobs[0]["job_id"] == "job2"

    def test_get_jobs_by_version_empty(self, store: JobStore) -> None:
        """No v1.0 jobs returns empty list."""
        store.add_job(
            job_id="job1",
            title="Job 1",
            company="Co1",
            location="Remote",
            preprocessing_version="v2.0",
        )

        jobs = store.get_jobs_by_version("v1.0")
        assert jobs == []

    def test_get_jobs_by_version_invalid_raises_error(self, store: JobStore) -> None:
        """Invalid version raises ValueError."""
        with pytest.raises(ValueError, match="Invalid preprocessing version"):
            store.get_jobs_by_version("v4.0")


class TestJobStoreGetVersionStats:
    """Test get_version_stats() method."""

    @pytest.fixture
    def store(self, tmp_path: Path) -> JobStore:
        """Create temporary test database."""
        db_path = tmp_path / "test.db"
        store = JobStore(str(db_path))
        return store

    def test_get_version_stats_mixed(self, store: JobStore) -> None:
        """Returns count for all versions."""
        # Add 3 v1.0 jobs
        for i in range(3):
            store.add_job(
                job_id=f"v1_job{i}",
                title=f"Job {i}",
                company="Co1",
                location="Remote",
                preprocessing_version="v1.0",
            )

        # Add 2 v2.0 jobs
        for i in range(3, 5):
            store.add_job(
                job_id=f"v2_job{i}",
                title=f"Job {i}",
                company="Co2",
                location="Remote",
                preprocessing_version="v2.0",
            )

        # Add 1 v3.0 job
        store.add_job(
            job_id="v3_job5",
            title="Job 5",
            company="Co3",
            location="Remote",
            preprocessing_version="v3.0",
        )

        stats = store.get_version_stats()
        assert stats["1.0"] == 3
        assert stats["2.0"] == 2
        assert stats["3.0"] == 1

    def test_get_version_stats_only_v2(self, store: JobStore) -> None:
        """Returns only v2.0 count if no v1.0."""
        store.add_job(
            job_id="job1",
            title="Job 1",
            company="Co1",
            location="Remote",
            preprocessing_version="v2.0",
        )

        stats = store.get_version_stats()
        assert stats.get("2.0") == 1
        assert stats.get("1.0", 0) == 0

    def test_get_version_stats_empty_db(self, store: JobStore) -> None:
        """Empty database returns zero counts."""
        stats = store.get_version_stats()
        assert len(stats) == 0 or (stats.get("1.0", 0) == 0 and stats.get("2.0", 0) == 0)
