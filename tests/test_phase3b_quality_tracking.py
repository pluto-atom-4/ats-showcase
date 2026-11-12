"""Unit and integration tests for Phase 3B: Quality Impact Tracking."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.storage.assessment_store import AssessmentStore
from src.storage.cost_models import QualityComparisonReport, QualityImpactMetrics
from src.storage.job_store import JobStore


class TestQualityImpactMetrics:
    """Test QualityImpactMetrics dataclass."""

    def test_score_delta_positive(self):
        """Test score delta calculation (improvement)."""
        metric = QualityImpactMetrics(
            job_id="job_1",
            preprocessing_version_before="v1.0",
            preprocessing_version_after="v2.0",
            previous_assessment_score=70,
            new_assessment_score=85,
        )

        assert metric.score_delta == 15
        assert metric.is_improvement is True
        assert metric.is_regression is False

    def test_score_delta_negative(self):
        """Test score delta calculation (regression)."""
        metric = QualityImpactMetrics(
            job_id="job_2",
            preprocessing_version_before="v1.0",
            preprocessing_version_after="v2.0",
            previous_assessment_score=80,
            new_assessment_score=65,
        )

        assert metric.score_delta == -15
        assert metric.is_improvement is False
        assert metric.is_regression is True

    def test_score_delta_zero(self):
        """Test score delta when unchanged."""
        metric = QualityImpactMetrics(
            job_id="job_3",
            preprocessing_version_before="v1.0",
            preprocessing_version_after="v2.0",
            previous_assessment_score=75,
            new_assessment_score=75,
        )

        assert metric.score_delta == 0
        assert metric.is_improvement is False
        assert metric.is_regression is False


class TestQualityComparisonReport:
    """Test QualityComparisonReport dataclass."""

    def test_empty_report(self):
        """Test empty report initialization."""
        report = QualityComparisonReport()

        assert report.total_comparisons == 0
        assert report.avg_score_before == 0.0
        assert report.avg_score_after == 0.0
        assert report.regression_risk_percent == 0.0

    def test_regression_risk_percent(self):
        """Test regression risk percentage calculation."""
        report = QualityComparisonReport(
            total_comparisons=10,
            score_improved=6,
            score_declined=3,
            score_unchanged=1,
        )

        assert report.regression_risk_percent == 30.0

    def test_improvement_rate(self):
        """Test improvement rate calculation."""
        report = QualityComparisonReport(
            total_comparisons=10,
            score_improved=6,
            score_declined=3,
            score_unchanged=1,
        )

        assert report.improvement_rate == 60.0

    def test_avg_score_delta(self):
        """Test average score delta calculation."""
        metric1 = QualityImpactMetrics(
            job_id="job_1",
            preprocessing_version_before="v1.0",
            preprocessing_version_after="v2.0",
            previous_assessment_score=70,
            new_assessment_score=80,
        )
        metric2 = QualityImpactMetrics(
            job_id="job_2",
            preprocessing_version_before="v1.0",
            preprocessing_version_after="v2.0",
            previous_assessment_score=75,
            new_assessment_score=70,
        )

        report = QualityComparisonReport(
            total_comparisons=2,
            score_improved=1,
            score_declined=1,
            quality_metrics=[metric1, metric2],
        )

        assert report.avg_score_delta == 2.5

    def test_report_to_dict(self):
        """Test report serialization."""
        report = QualityComparisonReport(
            total_comparisons=5,
            avg_score_before=72.0,
            avg_score_after=78.0,
            score_improved=3,
            score_declined=1,
            score_unchanged=1,
            max_score_improvement=15,
            max_score_decline=-8,
        )

        result_dict = report.to_dict()
        assert result_dict["total_comparisons"] == 5
        assert result_dict["avg_score_before"] == 72.0
        assert result_dict["score_improved"] == 3


class TestJobStoreQualityTracking:
    """Test JobStore quality tracking methods (Phase 3B)."""

    @pytest.fixture
    def store(self):
        """Create temporary job store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            store = JobStore(db_path)
            yield store
            store.close()

    def test_log_quality_impact(self, store):
        """Test logging a single quality impact metric."""
        store.add_job(
            job_id="job_1",
            title="Test Job",
            company="TestCo",
            location="Remote",
            preprocessing_version="v1.0",
        )

        store.log_quality_impact(
            job_id="job_1",
            previous_assessment_score=70,
            new_assessment_score=85,
            preprocessing_version_before="v1.0",
            preprocessing_version_after="v2.0",
        )

        if store.conn:
            cursor = store.conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM quality_tracking")
            count = cursor.fetchone()[0]
            assert count == 1

    def test_log_quality_impact_normalized_versions(self, store):
        """Test that versions are normalized when logging."""
        store.add_job(
            job_id="job_1",
            title="Test Job",
            company="TestCo",
            location="Remote",
        )

        store.log_quality_impact(
            job_id="job_1",
            previous_assessment_score=75,
            new_assessment_score=82,
            preprocessing_version_before="1.0",
            preprocessing_version_after="2.0",
        )

        if store.conn:
            cursor = store.conn.cursor()
            cursor.execute(
                """SELECT preprocessing_version_before, preprocessing_version_after
                   FROM quality_tracking WHERE job_id = ?""",
                ("job_1",),
            )
            row = cursor.fetchone()
            assert row[0] == "v1.0"
            assert row[1] == "v2.0"

    def test_log_multiple_quality_impacts(self, store):
        """Test logging multiple quality impact metrics."""
        for i in range(5):
            job_id = f"job_{i}"
            store.add_job(
                job_id=job_id,
                title=f"Test Job {i}",
                company="TestCo",
                location="Remote",
            )
            store.log_quality_impact(
                job_id=job_id,
                previous_assessment_score=70 + i * 5,
                new_assessment_score=75 + i * 5,
            )

        if store.conn:
            cursor = store.conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM quality_tracking")
            count = cursor.fetchone()[0]
            assert count == 5

    def test_log_quality_impact_no_connection(self):
        """Test error handling when database connection missing."""
        store = JobStore(":memory:")
        store.conn = None

        with pytest.raises(RuntimeError, match="Database connection not available"):
            store.log_quality_impact(
                job_id="job_1",
                previous_assessment_score=70,
                new_assessment_score=80,
            )

    def test_get_quality_comparison_report_empty(self, store):
        """Test quality report with no data."""
        report = store.get_quality_comparison_report()

        assert report.total_comparisons == 0
        assert report.avg_score_before == 0.0
        assert report.avg_score_after == 0.0

    def test_get_quality_comparison_report_single_improvement(self, store):
        """Test quality report with single score improvement."""
        store.add_job("job_1", "Test", "TestCo", "Remote")
        store.log_quality_impact(
            job_id="job_1",
            previous_assessment_score=70,
            new_assessment_score=85,
        )

        report = store.get_quality_comparison_report()

        assert report.total_comparisons == 1
        assert report.avg_score_before == 70.0
        assert report.avg_score_after == 85.0
        assert report.score_improved == 1
        assert report.score_declined == 0
        assert report.score_unchanged == 0
        assert report.max_score_improvement == 15

    def test_get_quality_comparison_report_single_regression(self, store):
        """Test quality report with single score regression."""
        store.add_job("job_1", "Test", "TestCo", "Remote")
        store.log_quality_impact(
            job_id="job_1",
            previous_assessment_score=85,
            new_assessment_score=65,
        )

        report = store.get_quality_comparison_report()

        assert report.total_comparisons == 1
        assert report.score_improved == 0
        assert report.score_declined == 1
        assert report.max_score_decline == -20

    def test_get_quality_comparison_report_mixed(self, store):
        """Test quality report with mixed improvements and regressions."""
        jobs_data = [
            ("job_1", 70, 85),
            ("job_2", 80, 75),
            ("job_3", 60, 60),
            ("job_4", 72, 85),
            ("job_5", 90, 70),
        ]

        for job_id, prev_score, new_score in jobs_data:
            store.add_job(job_id, "Test", "TestCo", "Remote")
            store.log_quality_impact(
                job_id=job_id,
                previous_assessment_score=prev_score,
                new_assessment_score=new_score,
            )

        report = store.get_quality_comparison_report()

        assert report.total_comparisons == 5
        assert report.score_improved == 2
        assert report.score_declined == 2
        assert report.score_unchanged == 1
        assert report.max_score_improvement == 15
        assert report.max_score_decline == -20
        assert report.avg_score_before == pytest.approx(74.4, abs=0.1)
        assert report.avg_score_after == 75.0

    def test_get_quality_comparison_report_regression_risk_threshold(self, store):
        """Test regression risk flagging for score declines >= 10 points."""
        jobs_data = [
            ("job_1", 90, 85),
            ("job_2", 85, 70),
            ("job_3", 80, 75),
            ("job_4", 95, 80),
        ]

        for job_id, prev_score, new_score in jobs_data:
            store.add_job(job_id, "Test", "TestCo", "Remote")
            store.log_quality_impact(
                job_id=job_id,
                previous_assessment_score=prev_score,
                new_assessment_score=new_score,
            )

        report = store.get_quality_comparison_report()

        assert len(report.regression_risk_jobs) == 2
        assert "job_2" in report.regression_risk_jobs
        assert "job_4" in report.regression_risk_jobs

    def test_get_quality_comparison_report_limit(self, store):
        """Test limiting quality report to N comparisons."""
        for i in range(10):
            job_id = f"job_{i}"
            store.add_job(job_id, "Test", "TestCo", "Remote")
            store.log_quality_impact(
                job_id=job_id,
                previous_assessment_score=70,
                new_assessment_score=75 + i,
            )

        report = store.get_quality_comparison_report(limit_jobs=5)

        assert report.total_comparisons == 5

    def test_get_regression_risk_jobs(self, store):
        """Test retrieving regression risk jobs."""
        jobs_data = [
            ("job_1", 90, 85),
            ("job_2", 85, 70),
            ("job_3", 80, 60),
            ("job_4", 95, 90),
        ]

        for job_id, prev_score, new_score in jobs_data:
            store.add_job(job_id, "Test", "TestCo", "Remote")
            store.log_quality_impact(
                job_id=job_id,
                previous_assessment_score=prev_score,
                new_assessment_score=new_score,
            )

        risk_jobs = store.get_regression_risk_jobs(threshold=-10)

        assert len(risk_jobs) == 2
        assert any(job["job_id"] == "job_2" for job in risk_jobs)
        assert any(job["job_id"] == "job_3" for job in risk_jobs)

    def test_get_regression_risk_jobs_empty(self, store):
        """Test regression risk when no jobs meet threshold."""
        jobs_data = [
            ("job_1", 90, 85),
            ("job_2", 85, 80),
        ]

        for job_id, prev_score, new_score in jobs_data:
            store.add_job(job_id, "Test", "TestCo", "Remote")
            store.log_quality_impact(
                job_id=job_id,
                previous_assessment_score=prev_score,
                new_assessment_score=new_score,
            )

        risk_jobs = store.get_regression_risk_jobs(threshold=-10)

        assert len(risk_jobs) == 0


class TestAssessmentStoreQualityTracking:
    """Test AssessmentStore quality tracking methods (Phase 3B)."""

    @pytest.fixture
    def store(self):
        """Create temporary assessment store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            store = AssessmentStore(db_path)
            yield store
            store._close_db()

    def test_save_assessment_with_quality_tracking(self, store):
        """Test saving assessment with quality tracking data."""
        store.save_assessment(
            job_id="job_1",
            title="Test Job",
            company="TestCo",
            location="Remote",
            overall_score=85.0,
            tech_score=90.0,
            seniority_score=80.0,
            location_score=85.0,
            recommendations=["Learn AWS"],
            summary="Good fit",
            tokens_used=650,
            actual_cost=0.002,
            preprocessing_version="v2.0",
            preprocessing_quality_check=True,
            previous_assessment_score=70,
        )

        assessment = store.get_assessment_by_id("job_1")

        assert assessment is not None
        assert assessment["preprocessing_version"] == "v2.0"
        assert assessment["preprocessing_quality_check"] == 1  # SQLite stores bool as int
        assert assessment["previous_assessment_score"] == 70
        assert assessment["score_delta"] == 15

    def test_save_assessment_score_delta_calculation(self, store):
        """Test that score delta is calculated correctly."""
        store.save_assessment(
            job_id="job_1",
            title="Test Job",
            company="TestCo",
            location="Remote",
            overall_score=65.0,
            tech_score=60.0,
            seniority_score=65.0,
            location_score=65.0,
            recommendations=[],
            summary="Needs work",
            tokens_used=600,
            actual_cost=0.002,
            preprocessing_version="v2.0",
            preprocessing_quality_check=True,
            previous_assessment_score=80,
        )

        assessment = store.get_assessment_by_id("job_1")

        assert assessment["score_delta"] == -15

    def test_save_assessment_without_quality_tracking(self, store):
        """Test saving regular assessment without quality tracking."""
        store.save_assessment(
            job_id="job_1",
            title="Test Job",
            company="TestCo",
            location="Remote",
            overall_score=75.0,
            tech_score=80.0,
            seniority_score=75.0,
            location_score=75.0,
            recommendations=[],
            summary="Good fit",
            tokens_used=600,
            actual_cost=0.002,
        )

        assessment = store.get_assessment_by_id("job_1")

        assert assessment is not None
        assert assessment["preprocessing_version"] is None
        assert assessment["preprocessing_quality_check"] == 0
        assert assessment["previous_assessment_score"] is None
        assert assessment["score_delta"] is None


class TestQualityReportSerialization:
    """Test quality report serialization for API responses."""

    def test_quality_report_to_dict_structure(self):
        """Test quality report serialization structure."""
        metric = QualityImpactMetrics(
            job_id="job_1",
            preprocessing_version_before="v1.0",
            preprocessing_version_after="v2.0",
            previous_assessment_score=70,
            new_assessment_score=85,
        )

        report = QualityComparisonReport(
            total_comparisons=1,
            avg_score_before=70.0,
            avg_score_after=85.0,
            score_improved=1,
            score_declined=0,
            score_unchanged=0,
            max_score_improvement=15,
            max_score_decline=0,
            quality_metrics=[metric],
        )

        result_dict = report.to_dict()

        assert result_dict["total_comparisons"] == 1
        assert result_dict["avg_score_before"] == 70.0
        assert result_dict["avg_score_after"] == 85.0
        assert result_dict["score_improved"] == 1
        assert result_dict["score_declined"] == 0
        assert result_dict["improvement_rate"] == 100.0
        assert result_dict["regression_risk_percent"] == 0.0

    def test_quality_report_to_dict_regression_risk_truncation(self):
        """Test that regression risk jobs list is truncated in dict."""
        jobs_list = [f"job_{i}" for i in range(50)]

        report = QualityComparisonReport(
            total_comparisons=50,
            regression_risk_jobs=jobs_list,
        )

        result_dict = report.to_dict()

        assert result_dict["regression_risk_jobs_count"] == 50
        assert len(result_dict["regression_risk_jobs"]) == 20
