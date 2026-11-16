"""Integration tests for cost tracking (Phase 3A)."""

import sqlite3
import tempfile
from pathlib import Path
from typing import Generator, Optional

import pytest

from src.config.models import DEFAULT_MODEL, get_model_pricing
from src.storage.assessment_store import AssessmentStore
from src.storage.cost_models import CostComparisonReport
from src.storage.job_store import JobStore

HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-5"


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

        # 5 jobs at 1000 tokens (v1.0) vs 650 (v2.0); DEFAULT_MODEL input price is $3.00/1M.
        v1_total = 5 * 1000
        v2_total = 5 * 650
        tokens_saved = v1_total - v2_total
        rate_per_token = get_model_pricing(DEFAULT_MODEL)[0] / 1_000_000
        expected_savings = tokens_saved * rate_per_token

        assert expected_savings == pytest.approx(0.00525, abs=1e-12)
        assert report.estimated_savings_usd == pytest.approx(expected_savings, abs=1e-8)

        store.close()


def _save_assessment(assessments: AssessmentStore, job_id: str, model: Optional[str]) -> None:
    """Save a minimal assessment row for job_id with the given model."""
    assessments.save_assessment(
        job_id=job_id,
        title="Synthetic Job",
        company="Synthetic Co",
        location=None,
        overall_score=50.0,
        tech_score=50.0,
        seniority_score=50.0,
        location_score=50.0,
        recommendations=[],
        summary="SYNTHETIC: assessment row for blended-rate tests",
        tokens_used=0,
        actual_cost=0.0,
        model=model,
    )


class TestBlendedTokenRates:
    """Blended per-version token rates in the cost comparison report."""

    def test_mixed_models_per_version_rates_and_savings(self, temp_db: str) -> None:
        """v1.0 rate follows its Haiku assessments; v2.0 rate follows its Sonnet assessments."""
        # SYNTHETIC: jobs and assessment models for blended-rate coverage
        store = JobStore(temp_db)
        assessments = AssessmentStore(temp_db)
        store.add_job(job_id="v1_a", title="A", preprocessing_version="v1.0", tokens=1000)
        store.add_job(job_id="v1_b", title="B", preprocessing_version="v1.0", tokens=2000)
        store.add_job(job_id="v2_a", title="C", preprocessing_version="v2.0", tokens=600)
        _save_assessment(assessments, "v1_a", HAIKU_MODEL)
        _save_assessment(assessments, "v1_b", HAIKU_MODEL)
        _save_assessment(assessments, "v2_a", SONNET_MODEL)

        report = store.get_cost_comparison_report()

        rate_v1 = get_model_pricing(HAIKU_MODEL)[0]
        rate_v2 = get_model_pricing(SONNET_MODEL)[0]
        assert report.weighted_token_rate_v1_0_usd_per_1m == pytest.approx(rate_v1)
        assert report.weighted_token_rate_v2_0_usd_per_1m == pytest.approx(rate_v2)

        expected_savings = 3000 * rate_v1 / 1_000_000 - 600 * rate_v2 / 1_000_000
        assert report.estimated_savings_usd == pytest.approx(expected_savings, abs=1e-12)

        flat_default_savings = (3000 - 600) * get_model_pricing(DEFAULT_MODEL)[0] / 1_000_000
        assert report.estimated_savings_usd != pytest.approx(flat_default_savings, abs=1e-12)

        assessments._close_db()
        store.close()

    def test_token_weighted_blend_within_version(self, temp_db: str) -> None:
        """v1.0 rate is the token-weighted mean of its jobs' model rates."""
        # SYNTHETIC: two v1.0 jobs with different models and token counts
        store = JobStore(temp_db)
        assessments = AssessmentStore(temp_db)
        store.add_job(job_id="v1_a", title="A", preprocessing_version="v1.0", tokens=1000)
        store.add_job(job_id="v1_b", title="B", preprocessing_version="v1.0", tokens=3000)
        _save_assessment(assessments, "v1_a", HAIKU_MODEL)
        _save_assessment(assessments, "v1_b", SONNET_MODEL)

        report = store.get_cost_comparison_report()

        rate_h = get_model_pricing(HAIKU_MODEL)[0]
        rate_s = get_model_pricing(SONNET_MODEL)[0]
        expected = (1000 * rate_h + 3000 * rate_s) / (1000 + 3000)
        assert report.weighted_token_rate_v1_0_usd_per_1m == pytest.approx(expected)

        assessments._close_db()
        store.close()

    def test_null_model_falls_back_to_default_rate(self, temp_db: str) -> None:
        """Jobs without an assessment row or with NULL model use DEFAULT_MODEL rate."""
        # SYNTHETIC: one job with no assessment row, one with model=None
        store = JobStore(temp_db)
        assessments = AssessmentStore(temp_db)
        store.add_job(job_id="v1_no_row", title="A", preprocessing_version="v1.0", tokens=1000)
        store.add_job(job_id="v1_null", title="B", preprocessing_version="v1.0", tokens=1000)
        store.add_job(job_id="v2_null", title="C", preprocessing_version="v2.0", tokens=500)
        _save_assessment(assessments, "v1_null", None)
        _save_assessment(assessments, "v2_null", None)

        report = store.get_cost_comparison_report()

        default_rate = get_model_pricing(DEFAULT_MODEL)[0]
        assert report.weighted_token_rate_v1_0_usd_per_1m == pytest.approx(default_rate)
        assert report.weighted_token_rate_v2_0_usd_per_1m == pytest.approx(default_rate)

        assessments._close_db()
        store.close()

    def test_empty_v2_group_yields_zero_rate_and_savings(self, temp_db: str) -> None:
        """Only v1.0 jobs present: v2.0 rate and savings are both 0.0."""
        # SYNTHETIC: v1.0-only job set
        store = JobStore(temp_db)
        assessments = AssessmentStore(temp_db)
        store.add_job(job_id="v1_a", title="A", preprocessing_version="v1.0", tokens=1000)
        _save_assessment(assessments, "v1_a", HAIKU_MODEL)

        report = store.get_cost_comparison_report()

        assert report.weighted_token_rate_v2_0_usd_per_1m == 0.0
        assert report.estimated_savings_usd == 0.0
        assert report.weighted_token_rate_v1_0_usd_per_1m == pytest.approx(get_model_pricing(HAIKU_MODEL)[0])

        assessments._close_db()
        store.close()

    def test_old_db_without_model_column_uses_default_rate(self, temp_db: str) -> None:
        """job_assessments lacking a model column falls back to DEFAULT_MODEL rate without raising."""
        # SYNTHETIC: legacy job_assessments table with no model column
        store = JobStore(temp_db)
        store.add_job(job_id="v1_a", title="A", preprocessing_version="v1.0", tokens=1000)
        store.add_job(job_id="v2_a", title="B", preprocessing_version="v2.0", tokens=500)
        assert store.conn is not None
        store.conn.execute("CREATE TABLE job_assessments (job_id TEXT PRIMARY KEY, overall_score REAL)")
        store.conn.execute("INSERT INTO job_assessments (job_id, overall_score) VALUES ('v1_a', 50)")
        store.conn.commit()

        report = store.get_cost_comparison_report()

        default_rate = get_model_pricing(DEFAULT_MODEL)[0]
        assert report.weighted_token_rate_v1_0_usd_per_1m == pytest.approx(default_rate)
        assert report.weighted_token_rate_v2_0_usd_per_1m == pytest.approx(default_rate)

        store.close()

    def test_to_dict_includes_blended_rate_keys(self) -> None:
        """to_dict exposes both weighted token rate fields."""
        report = CostComparisonReport(
            weighted_token_rate_v1_0_usd_per_1m=0.8,
            weighted_token_rate_v2_0_usd_per_1m=3.0,
        )

        data = report.to_dict()

        assert data["weighted_token_rate_v1_0_usd_per_1m"] == pytest.approx(0.8)
        assert data["weighted_token_rate_v2_0_usd_per_1m"] == pytest.approx(3.0)
