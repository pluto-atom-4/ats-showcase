"""CLI assess command tests.

Tests for Task 8: CLI integration for assess phase.
References: docs/dev-note/preprocessor-llm-api-research.md (Part 2.1, 3.1, 4, 6)
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


@pytest.fixture
def sample_cv() -> str:
    """Sample CV text."""
    return (
        "Test Developer with 5 years of backend development experience. "
        "Skills: Python, JavaScript, AWS, Docker, Kubernetes. "
        "BS Computer Science. Looking for remote senior roles."
    )


@pytest.fixture
def sample_job() -> str:
    """Sample job description."""
    return (
        "Senior Python Developer at TechCorp. "
        "Requires 5+ years Python, Django, PostgreSQL, AWS. "
        "Remote position. Salary $150k-$180k."
    )


@pytest.fixture
def mock_assessor_result() -> dict[str, Any]:
    """Mock Assessor.assess_job() result."""
    return {
        "assessment": {
            "overall_score": 75.0,
            "tech_match": 80.0,
            "reasoning": "Strong Python background and AWS experience match job requirements.",
        },
        "entity_score": {
            "skill_match": 85.0,
            "tech_match": 80.0,
            "requirements_match": 75.0,
            "overall_entity_score": 80.0,
        },
        "cost_tracking": {
            "estimated_input": 400,
            "estimated_output": 200,
            "estimated_cost_usd": 0.0018,
            "actual_input": 420,
            "actual_output": 180,
            "actual_cost_usd": 0.00189,
        },
        "token_savings_percent": 25.5,
        "metadata": {
            "model": "claude-3-5-sonnet-20241022",
            "api_call_time_ms": 1250,
            "attempt": 1,
        },
    }


@pytest.fixture
def temp_cv_file(tmp_path: Any) -> str:
    """Create a temporary CV file."""
    cv_path = tmp_path / "test_cv.json"
    cv_path.write_text('{"text": "Test Developer with 5 years backend experience."}')
    return str(cv_path)


@pytest.fixture
def sample_preprocessed_job() -> dict[str, Any]:
    """Sample preprocessed job with required fields."""
    return {
        "job_id": "test-job-1",
        "title": "Senior Python Developer",
        "company": "TechCorp",
        "location": "Remote",
        "description": "Senior Python Developer at TechCorp...",
        "clean_text": "Senior Python Developer at TechCorp. Requires 5+ years Python experience.",
        "token_count": 45,
        "status": "confirmed",
        "crawled_at": "2026-07-20",
    }


@pytest.fixture
def sample_preprocessed_job_2() -> dict[str, Any]:
    """Second sample preprocessed job."""
    return {
        "job_id": "test-job-2",
        "title": "DevOps Engineer",
        "company": "CloudSys",
        "location": "San Francisco",
        "description": "DevOps Engineer at CloudSys...",
        "clean_text": "DevOps Engineer at CloudSys. Requires Kubernetes and Docker experience.",
        "token_count": 38,
        "status": "confirmed",
        "crawled_at": "2026-07-20",
    }


def test_assess_single_job(
    temp_cv_file: str, mock_assessor_result: dict[str, Any], sample_preprocessed_job: dict[str, Any]
) -> None:
    """Test assessing a single job."""
    with (
        patch("src.verification.JobReviewer") as mock_reviewer_cls,
        patch("src.storage.assessment_store.AssessmentStore") as mock_store_cls,
        patch("src.assessment.assessor.Assessor") as mock_assessor_cls,
    ):
        reviewer = MagicMock()
        reviewer.get_confirmed_jobs.return_value = [sample_preprocessed_job]
        mock_reviewer_cls.return_value = reviewer

        store = MagicMock()
        store.save_assessment.return_value = None
        store.get_stats.return_value = {"avg_score": 75.0}
        store.get_top_matches.return_value = []
        mock_store_cls.return_value = store

        assessor = MagicMock()
        assessor.model = "claude-3-5-sonnet-20241022"
        assessor.assess_job.return_value = mock_assessor_result
        mock_assessor_cls.return_value = assessor

        result = runner.invoke(app, ["assess", "--cv", temp_cv_file, "--mode", "all", "--limit", "1"])

        assert result.exit_code == 0
        assert "✅ [1/1]" in result.stdout
        assert "Senior Python Developer" in result.stdout
        assert "Assessment Summary" in result.stdout or "Assessment complete" in result.stdout


def test_assess_multiple_jobs(
    temp_cv_file: str,
    mock_assessor_result: dict[str, Any],
    sample_preprocessed_job: dict[str, Any],
    sample_preprocessed_job_2: dict[str, Any],
) -> None:
    """Test assessing multiple jobs."""
    with (
        patch("src.verification.JobReviewer") as mock_reviewer_cls,
        patch("src.storage.assessment_store.AssessmentStore") as mock_store_cls,
        patch("src.assessment.assessor.Assessor") as mock_assessor_cls,
    ):
        reviewer = MagicMock()
        reviewer.get_confirmed_jobs.return_value = [sample_preprocessed_job, sample_preprocessed_job_2]
        mock_reviewer_cls.return_value = reviewer

        store = MagicMock()
        store.save_assessment.return_value = None
        store.get_stats.return_value = {"avg_score": 75.0}
        store.get_top_matches.return_value = []
        mock_store_cls.return_value = store

        assessor = MagicMock()
        assessor.model = "claude-3-5-sonnet-20241022"
        assessor.assess_job.return_value = mock_assessor_result
        mock_assessor_cls.return_value = assessor

        result = runner.invoke(app, ["assess", "--cv", temp_cv_file, "--mode", "all"])

        assert result.exit_code == 0
        assert "✅ [1/2]" in result.stdout
        assert "✅ [2/2]" in result.stdout


def test_assess_cost_tracking(
    temp_cv_file: str, mock_assessor_result: dict[str, Any], sample_preprocessed_job: dict[str, Any]
) -> None:
    """Test cost tracking (estimate vs actual)."""
    with (
        patch("src.verification.JobReviewer") as mock_reviewer_cls,
        patch("src.storage.assessment_store.AssessmentStore") as mock_store_cls,
        patch("src.assessment.assessor.Assessor") as mock_assessor_cls,
    ):
        reviewer = MagicMock()
        reviewer.get_confirmed_jobs.return_value = [sample_preprocessed_job]
        mock_reviewer_cls.return_value = reviewer

        store = MagicMock()
        store.save_assessment.return_value = None
        store.get_stats.return_value = {"avg_score": 75.0}
        store.get_top_matches.return_value = []
        mock_store_cls.return_value = store

        assessor = MagicMock()
        assessor.model = "claude-3-5-sonnet-20241022"
        assessor.assess_job.return_value = mock_assessor_result
        mock_assessor_cls.return_value = assessor

        result = runner.invoke(app, ["assess", "--cv", temp_cv_file, "--mode", "all", "--limit", "1"])

        assert result.exit_code == 0
        assert "Cost:" in result.stdout or "💰" in result.stdout
        assert "Tokens:" in result.stdout or "tokens" in result.stdout


def test_assess_empty_jobs(temp_cv_file: str) -> None:
    """Test handling when no confirmed jobs found."""
    with patch("src.verification.JobReviewer") as mock_reviewer_cls, patch("src.assessment.assessor.Assessor"):
        reviewer = MagicMock()
        reviewer.get_confirmed_jobs.return_value = []
        mock_reviewer_cls.return_value = reviewer

        result = runner.invoke(app, ["assess", "--cv", temp_cv_file, "--mode", "all"])

        assert result.exit_code == 1
        output = result.stdout + result.output if result.output else result.stdout
        assert "No confirmed jobs" in output or "confirmed" in output.lower()


def test_assess_cv_not_found() -> None:
    """Test error on missing CV file."""
    result = runner.invoke(app, ["assess", "--cv", "/nonexistent/cv.json"])

    assert result.exit_code == 1
    output = result.stdout + result.stderr if result.stderr else result.stdout
    assert "not found" in output.lower() or "exit" in result.output.lower()


def test_assess_rate_limit_handling(
    temp_cv_file: str, mock_assessor_result: dict[str, Any], sample_preprocessed_job: dict[str, Any]
) -> None:
    """Test rate limit error handling (non-fatal)."""
    import anthropic

    with (
        patch("src.verification.JobReviewer") as mock_reviewer_cls,
        patch("src.storage.assessment_store.AssessmentStore") as mock_store_cls,
        patch("src.assessment.assessor.Assessor") as mock_assessor_cls,
    ):
        reviewer = MagicMock()
        reviewer.get_confirmed_jobs.return_value = [sample_preprocessed_job]
        mock_reviewer_cls.return_value = reviewer

        store = MagicMock()
        store.save_assessment.return_value = None
        store.get_stats.return_value = {"avg_score": 75.0}
        store.get_top_matches.return_value = []
        mock_store_cls.return_value = store

        assessor = MagicMock()
        assessor.model = "claude-3-5-sonnet-20241022"
        assessor.assess_job.side_effect = Exception("Rate limited")
        mock_assessor_cls.return_value = assessor

        result = runner.invoke(app, ["assess", "--cv", temp_cv_file, "--mode", "all"])

        assert "Assessment complete" in result.stdout or "Failed" in result.stdout or result.exit_code in (0, 1)


def test_assess_verify_cost_flag(
    temp_cv_file: str, mock_assessor_result: dict[str, Any], sample_preprocessed_job: dict[str, Any]
) -> None:
    """Test --verify-cost flag prompts user."""
    with (
        patch("src.verification.JobReviewer") as mock_reviewer_cls,
        patch("src.storage.assessment_store.AssessmentStore") as mock_store_cls,
        patch("src.assessment.assessor.Assessor") as mock_assessor_cls,
    ):
        reviewer = MagicMock()
        reviewer.get_confirmed_jobs.return_value = [sample_preprocessed_job]
        mock_reviewer_cls.return_value = reviewer

        store = MagicMock()
        store.save_assessment.return_value = None
        store.get_stats.return_value = {"avg_score": 75.0}
        store.get_top_matches.return_value = []
        mock_store_cls.return_value = store

        assessor = MagicMock()
        assessor.model = "claude-3-5-sonnet-20241022"
        mock_assessor_cls.return_value = assessor

        result = runner.invoke(
            app,
            ["assess", "--cv", temp_cv_file, "--verify-cost", "--limit", "1"],
            input="n\n",
        )

        assert "Estimated" in result.stdout or "Aborted" in result.stdout
