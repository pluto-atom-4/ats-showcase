"""Tests for re-preprocessing workflow (Phase 2, Task 4-5)."""

from pathlib import Path

import pytest

from src.storage.job_store import JobStore


class TestReprocessingWorkflow:
    """Test selective re-preprocessing workflow."""

    @pytest.fixture
    def store(self, tmp_path: Path) -> JobStore:
        """Create test database."""
        return JobStore(str(tmp_path / "test.db"))

    def test_reprocess_v1_jobs_only(self, store: JobStore) -> None:
        """Selective re-preprocess updates only v1.0 jobs."""
        store.add_job("job1", "Title 1", "Co1", "Remote", preprocessing_version="v1.0")
        store.add_job("job2", "Title 2", "Co2", "Remote", preprocessing_version="v2.0")

        v1_jobs = store.get_jobs_by_version("v1.0")
        assert len(v1_jobs) == 1

        for job in v1_jobs:
            store.update_preprocessing_version(job["job_id"], "v2.0")

        v1_after = store.get_jobs_by_version("v1.0")
        v2_after = store.get_jobs_by_version("v2.0")
        assert len(v1_after) == 0
        assert len(v2_after) == 2


class TestCostAnalysisByVersion:
    """Test cost tracking and analysis by version."""

    @pytest.fixture
    def store(self, tmp_path: Path) -> JobStore:
        """Create test database."""
        return JobStore(str(tmp_path / "test.db"))

    def test_version_stats_shows_cost_data(self, store: JobStore) -> None:
        """get_version_stats returns job counts by version."""
        store.add_job("job1", "Title 1", "Co1", "Remote", preprocessing_version="v1.0", tokens=650)
        store.add_job("job2", "Title 2", "Co2", "Remote", preprocessing_version="v2.0", tokens=420)

        stats = store.get_version_stats()
        assert stats["1.0"] == 1
        assert stats["2.0"] == 1

    def test_version_stats_empty_db(self, store: JobStore) -> None:
        """Empty database returns empty stats."""
        stats = store.get_version_stats()
        assert len(stats) == 0 or all(v == 0 for v in stats.values())


class TestBackwardCompatibility:
    """Test that queries work regardless of version."""

    @pytest.fixture
    def store(self, tmp_path: Path) -> JobStore:
        """Create test database."""
        return JobStore(str(tmp_path / "test.db"))

    def test_get_all_jobs_returns_both_versions(self, store: JobStore) -> None:
        """Query without version filter returns all jobs."""
        store.add_job("job1", "Title 1", "Co1", "Remote", preprocessing_version="v1.0")
        store.add_job("job2", "Title 2", "Co2", "Remote", preprocessing_version="v2.0")

        all_jobs = store.get_all_jobs()
        assert len(all_jobs) == 2
