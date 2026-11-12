"""Integration tests for cost tracking (Phase 3A)."""

import sqlite3
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from src.storage.cost_models import CostComparisonReport
from src.storage.job_store import JobStore


@pytest.fixture
def temp_db() -> Generator[str, None, None]:
    """Create temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        yield db_path


class TestJobStoreCostTracking:
    """Test cost tracking methods in JobStore."""

    def test_log_reprocessing_metrics(self, temp_db: str) -> None:
        """Test logging re-preprocessing metrics."""
        store = JobStore(temp_db)

        store.add_job(
            job_id="job_123",
            title="Test Job",
            company="Test Company",
            preprocessing_version="v1.0",
            tokens=1000,
            estimated_cost=0.003,
        )

        store.log_reprocessing_metrics(
            job_id="job_123",
            tokens_before=1000,
            tokens_after=650,
            version_before="v1.0",
            version_after="v2.0",
            cost_before=0.003,
            cost_after=0.00195,
        )

        # Row layout: job_id, phase, version_before/after, tokens_before/after, cost_before/after.
        assert store.conn is not None
        cursor = store.conn.cursor()
        cursor.execute(
            """SELECT job_id, phase, preprocessing_version_before, preprocessing_version_after,
                      tokens_before, tokens_after, estimated_cost_before, estimated_cost_after
               FROM cost_tracking WHERE job_id = 'job_123' AND is_re_preprocessing = TRUE"""
        )
        row = cursor.fetchone()

        assert row is not None
        assert row[0] == "job_123"
        assert row[1] == "reprocess"
        assert row[2] == "v1.0"
        assert row[3] == "v2.0"
        assert row[4] == 1000
        assert row[5] == 650
        assert row[6] == pytest.approx(0.003, abs=1e-6)
        assert row[7] == pytest.approx(0.00195, abs=1e-6)

        store.close()

    def test_log_reprocessing_metrics_no_db(self) -> None:
        """Test logging metrics without database connection raises error."""
        store = JobStore(":memory:")
        store.conn = None

        with pytest.raises(RuntimeError, match="Database connection not available"):
            store.log_reprocessing_metrics(
                job_id="job_123",
                tokens_before=1000,
                tokens_after=650,
                version_before="v1.0",
                version_after="v2.0",
                cost_before=0.003,
                cost_after=0.00195,
            )

    def test_get_cost_comparison_report_empty_db(self, temp_db: str) -> None:
        """Test cost comparison report with empty database."""
        store = JobStore(temp_db)

        report = store.get_cost_comparison_report()

        assert report.total_jobs_v1_0 == 0
        assert report.total_jobs_v2_0 == 0
        assert report.total_tokens_v1_0 == 0
        assert report.total_tokens_v2_0 == 0
        assert report.estimated_savings_usd == 0.0
        assert len(report.reprocessing_runs) == 0

        store.close()

    def test_get_cost_comparison_report_with_jobs(self, temp_db: str) -> None:
        """Test cost comparison report with mixed v1.0 and v2.0 jobs."""
        store = JobStore(temp_db)

        store.add_job(
            job_id="job_1",
            title="Job 1",
            company="Company A",
            preprocessing_version="v1.0",
            tokens=1000,
        )
        store.add_job(
            job_id="job_2",
            title="Job 2",
            company="Company A",
            preprocessing_version="v1.0",
            tokens=1200,
        )

        store.add_job(
            job_id="job_3",
            title="Job 3",
            company="Company B",
            preprocessing_version="v2.0",
            tokens=650,
        )
        store.add_job(
            job_id="job_4",
            title="Job 4",
            company="Company B",
            preprocessing_version="v2.0",
            tokens=700,
        )

        report = store.get_cost_comparison_report()

        assert report.total_jobs_v1_0 == 2
        assert report.total_jobs_v2_0 == 2
        assert report.total_tokens_v1_0 == 2200
        assert report.total_tokens_v2_0 == 1350
        assert report.avg_tokens_per_job_v1_0 == 1100.0
        assert report.avg_tokens_per_job_v2_0 == 675.0
        assert report.migration_progress_percent == pytest.approx(50.0, abs=0.1)

        store.close()

    def test_get_cost_comparison_report_with_reprocessing(self, temp_db: str) -> None:
        """Test cost comparison report includes re-preprocessing metrics."""
        store = JobStore(temp_db)

        store.add_job(
            job_id="job_1",
            title="Job 1",
            company="Company A",
            preprocessing_version="v2.0",
            tokens=650,
        )

        store.log_reprocessing_metrics(
            job_id="job_1",
            tokens_before=1000,
            tokens_after=650,
            version_before="v1.0",
            version_after="v2.0",
            cost_before=0.003,
            cost_after=0.00195,
        )

        report = store.get_cost_comparison_report()

        assert len(report.reprocessing_runs) == 1
        assert report.total_reprocessing_tokens_saved == 350
        assert report.total_reprocessing_cost_saved == pytest.approx(0.00105, abs=1e-5)
        assert report.jobs_already_migrated == 1

        store.close()

    def test_ensure_cost_tracking_table(self, temp_db: str) -> None:
        """Test that cost_tracking table is created with all required columns."""
        store = JobStore(temp_db)

        store._ensure_cost_tracking_table()

        assert store.conn is not None
        cursor = store.conn.cursor()
        cursor.execute("PRAGMA table_info(cost_tracking)")
        columns = {row[1] for row in cursor.fetchall()}

        required_columns = {
            "id",
            "job_id",
            "phase",
            "input_tokens",
            "output_tokens",
            "cost",
            "timestamp",
            "preprocessing_version_before",
            "preprocessing_version_after",
            "tokens_before",
            "tokens_after",
            "estimated_cost_before",
            "estimated_cost_after",
            "is_re_preprocessing",
        }

        assert required_columns.issubset(columns)
        store.close()

    def test_version_normalization_in_log(self, temp_db: str) -> None:
        """Test that version strings are normalized when logging metrics."""
        store = JobStore(temp_db)

        store.add_job(
            job_id="job_123",
            title="Test Job",
            company="Test Company",
        )

        store.log_reprocessing_metrics(
            job_id="job_123",
            tokens_before=1000,
            tokens_after=650,
            version_before="1.0",
            version_after="2.0",
            cost_before=0.003,
            cost_after=0.00195,
        )

        assert store.conn is not None
        cursor = store.conn.cursor()
        cursor.execute(
            "SELECT preprocessing_version_before, preprocessing_version_after "
            "FROM cost_tracking WHERE job_id = 'job_123'"
        )
        row = cursor.fetchone()

        assert row[0] == "v1.0"
        assert row[1] == "v2.0"

        store.close()

    def test_multiple_reprocessing_runs_same_job(self, temp_db: str) -> None:
        """Test multiple re-preprocessing runs for the same job."""
        store = JobStore(temp_db)

        store.add_job(
            job_id="job_1",
            title="Job 1",
            company="Company A",
            preprocessing_version="v2.0",
            tokens=650,
        )

        store.log_reprocessing_metrics(
            job_id="job_1",
            tokens_before=1000,
            tokens_after=650,
            version_before="v1.0",
            version_after="v2.0",
            cost_before=0.003,
            cost_after=0.00195,
        )

        assert store.conn is not None
        cursor = store.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cost_tracking WHERE is_re_preprocessing = TRUE")
        count = cursor.fetchone()[0]

        assert count == 1

        store.close()

    def test_cost_savings_calculation(self, temp_db: str) -> None:
        """Test cost savings calculations in report."""
        store = JobStore(temp_db)

        for i in range(5):
            store.add_job(
                job_id=f"job_v1_{i}",
                title=f"Job v1 {i}",
                company="Company A",
                preprocessing_version="v1.0",
                tokens=1000,
            )

        for i in range(5):
            store.add_job(
                job_id=f"job_v2_{i}",
                title=f"Job v2 {i}",
                company="Company B",
                preprocessing_version="v2.0",
                tokens=650,
            )

        report = store.get_cost_comparison_report()

        # Token rate is $0.003 per 1M tokens; 5 jobs at 1000 tokens (v1.0) vs 650 (v2.0).
        v1_total = 5 * 1000
        v2_total = 5 * 650
        tokens_saved = v1_total - v2_total
        expected_savings = tokens_saved * (0.003 / 1_000_000)

        assert report.estimated_savings_usd == pytest.approx(expected_savings, abs=1e-8)

        store.close()
