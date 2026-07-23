"""Tests for Assessor end-to-end assessment workflow."""

from typing import List, Tuple
from unittest.mock import MagicMock, patch

import pytest

from src.assessment.assessor import Assessor
from src.assessment.types import AssessmentResult


@pytest.fixture
def mock_assessor() -> Assessor:
    """Fixture: Assessor with mocked LLMProvider and Preprocessor."""
    with patch("src.assessment.assessor.LLMProvider"), patch(
        "src.assessment.assessor.Preprocessor"
    ):
        assessor = Assessor()
    return assessor


class TestAssessorInit:
    """Test Assessor initialization."""

    @patch("src.assessment.assessor.Preprocessor")
    @patch("src.assessment.assessor.LLMProvider")
    def test_init_with_defaults(self, mock_llm_class: MagicMock, mock_prep_class: MagicMock) -> None:
        """Initialize with default model."""
        assessor = Assessor()
        assert assessor.model == "claude-3-5-sonnet-20241022"
        assert assessor.use_examples is False
        assert assessor.llm_provider is not None
        assert assessor.preprocessor is not None
        assert assessor.data_reshaper is not None

    @patch("src.assessment.assessor.Preprocessor")
    @patch("src.assessment.assessor.LLMProvider")
    def test_init_with_custom_model(self, mock_llm_class: MagicMock, mock_prep_class: MagicMock) -> None:
        """Initialize with custom model."""
        assessor = Assessor(model="claude-3-5-haiku-20241022")
        assert assessor.model == "claude-3-5-haiku-20241022"

    @patch("src.assessment.assessor.Preprocessor")
    @patch("src.assessment.assessor.LLMProvider")
    def test_init_with_examples(self, mock_llm_class: MagicMock, mock_prep_class: MagicMock) -> None:
        """Initialize with use_examples enabled."""
        assessor = Assessor(use_examples=True)
        assert assessor.use_examples is True


class TestEntityScoring:
    """Test entity-based scoring logic."""

    def test_entity_score_perfect_match(self, mock_assessor: Assessor) -> None:
        """Perfect overlap: all CV skills match job requirements."""
        cv_entities: Tuple[List[str], List[str], List[str]] = (
            ["Python", "Django"],
            ["AWS"],
            ["5 years"],
        )
        job_entities: Tuple[List[str], List[str], List[str]] = (
            ["Python", "Django"],
            ["AWS"],
            ["5 years"],
        )

        score = mock_assessor._compute_entity_score(cv_entities, job_entities)

        assert score["skill_match"] == 100.0
        assert score["tech_match"] == 100.0
        assert score["requirements_match"] == 100.0
        assert score["overall_entity_score"] == 100.0

    def test_entity_score_partial_match(self, mock_assessor: Assessor) -> None:
        """Partial overlap: some skills match, some don't."""
        cv_entities: Tuple[List[str], List[str], List[str]] = (
            ["Python", "Java"],
            ["AWS"],
            [],
        )
        job_entities: Tuple[List[str], List[str], List[str]] = (
            ["Python", "Go"],
            ["AWS", "GCP"],
            [],
        )

        score = mock_assessor._compute_entity_score(cv_entities, job_entities)

        # CV has 1/2 job skills (50%), 1/2 job tech (50%), no reqs
        assert 40 < score["skill_match"] < 60
        assert 40 < score["tech_match"] < 60
        assert 30 < score["overall_entity_score"] < 70

    def test_entity_score_no_match(self, mock_assessor: Assessor) -> None:
        """No overlap: different skills and tech."""
        cv_entities: Tuple[List[str], List[str], List[str]] = (
            ["Java", "Spring"],
            ["MySQL"],
            [],
        )
        job_entities: Tuple[List[str], List[str], List[str]] = (
            ["Python", "Django"],
            ["PostgreSQL"],
            [],
        )

        score = mock_assessor._compute_entity_score(cv_entities, job_entities)

        assert score["skill_match"] == 0.0
        assert score["tech_match"] == 0.0
        assert score["requirements_match"] == 0.0

    def test_entity_score_empty_cv(self, mock_assessor: Assessor) -> None:
        """Empty CV entities."""
        cv_entities: Tuple[List[str], List[str], List[str]] = ([], [], [])
        job_entities: Tuple[List[str], List[str], List[str]] = (
            ["Python"],
            ["AWS"],
            [],
        )

        score = mock_assessor._compute_entity_score(cv_entities, job_entities)

        # Empty CV should score low
        assert score["skill_match"] == 0.0
        assert score["tech_match"] == 0.0

    def test_entity_score_empty_job(self, mock_assessor: Assessor) -> None:
        """Empty job entities (shouldn't happen but edge case)."""
        cv_entities: Tuple[List[str], List[str], List[str]] = (
            ["Python"],
            ["AWS"],
            [],
        )
        job_entities: Tuple[List[str], List[str], List[str]] = ([], [], [])

        score = mock_assessor._compute_entity_score(cv_entities, job_entities)

        # Empty job requirements = full score (no requirements to match)
        assert score["skill_match"] == 100.0
        assert score["tech_match"] == 100.0

    def test_entity_score_case_insensitive(self, mock_assessor: Assessor) -> None:
        """Entity matching is case-insensitive."""
        cv_entities: Tuple[List[str], List[str], List[str]] = (
            ["python", "Django"],
            ["aws"],
            [],
        )
        job_entities: Tuple[List[str], List[str], List[str]] = (
            ["Python", "Django"],
            ["AWS"],
            [],
        )

        score = mock_assessor._compute_entity_score(cv_entities, job_entities)

        assert score["skill_match"] == 100.0
        assert score["tech_match"] == 100.0

    def test_entity_score_special_characters(self, mock_assessor: Assessor) -> None:
        """Entity matching handles special characters."""
        cv_entities: Tuple[List[str], List[str], List[str]] = (
            ["C++", "C#"],
            ["Node.js"],
            [],
        )
        job_entities: Tuple[List[str], List[str], List[str]] = (
            ["C++", "C#"],
            ["Node.js"],
            [],
        )

        score = mock_assessor._compute_entity_score(cv_entities, job_entities)

        assert score["skill_match"] == 100.0
        assert score["tech_match"] == 100.0

    def test_entity_score_structure(self, mock_assessor: Assessor) -> None:
        """Entity score has required fields."""
        cv_entities: Tuple[List[str], List[str], List[str]] = (
            ["Python"],
            ["AWS"],
            [],
        )
        job_entities: Tuple[List[str], List[str], List[str]] = (
            ["Python", "Go"],
            ["AWS", "GCP"],
            [],
        )

        score = mock_assessor._compute_entity_score(cv_entities, job_entities)

        assert "skill_match" in score
        assert "tech_match" in score
        assert "requirements_match" in score
        assert "overall_entity_score" in score
        assert isinstance(score["skill_match"], float)
        assert 0 <= score["skill_match"] <= 100


class TestTokenSavings:
    """Test token savings measurement."""

    def test_baseline_token_count(self, mock_assessor: Assessor) -> None:
        """Baseline tokens counted correctly."""
        cv = "Senior Python Developer with 5 years experience"
        job = "We seek a Python expert with Django knowledge"

        baseline = mock_assessor._estimate_baseline_tokens(cv, job)

        assert baseline > 0
        assert isinstance(baseline, int)

    def test_baseline_grows_with_text_length(self, mock_assessor: Assessor) -> None:
        """Longer text → more baseline tokens."""
        cv = "Python Developer"
        job = "Python expert"

        baseline1 = mock_assessor._estimate_baseline_tokens(cv, job)

        cv_long = cv + " " + ("extra " * 50)
        baseline2 = mock_assessor._estimate_baseline_tokens(cv_long, job)

        assert baseline2 > baseline1

    def test_baseline_long_job_description(self, mock_assessor: Assessor) -> None:
        """Baseline for very long job description."""
        cv = "CV text"
        job = "Job description " * 100  # ~1600 chars

        baseline = mock_assessor._estimate_baseline_tokens(cv, job)

        assert baseline > 100  # Substantial token count


class TestAssessmentIntegration:
    """Test end-to-end assessment with mocked LLMProvider."""

    @patch("src.assessment.assessor.Preprocessor")
    @patch("src.assessment.assessor.LLMProvider")
    def test_assess_job_success(
        self, mock_llm_class: MagicMock, mock_preprocessor_class: MagicMock
    ) -> None:
        """Successful assessment returns AssessmentResult."""
        # Mock preprocessor
        mock_preprocessor = MagicMock()
        mock_preprocessor.extract_entities.side_effect = [
            (["Python"], ["AWS"], []),  # CV entities
            (["Python", "Go"], ["AWS", "GCP"], []),  # Job entities
        ]
        mock_preprocessor_class.return_value = mock_preprocessor

        # Mock LLM provider
        mock_llm = MagicMock()
        mock_llm.assess_job.return_value = {
            "assessment": {"overall_score": 75},
            "cost_tracking": {
                "estimated_input": 600,
                "estimated_output": 150,
                "estimated_cost_usd": 0.002,
                "actual_input": 550,
                "actual_output": 150,
                "actual_cost_usd": 0.00185,
            },
            "metadata": {
                "model": "claude-3-5-sonnet-20241022",
                "api_call_time_ms": 1200,
                "attempt": 1,
            },
        }
        mock_llm_class.return_value = mock_llm

        # Test
        assessor = Assessor()
        assessor.preprocessor = mock_preprocessor
        assessor.llm_provider = mock_llm

        result = assessor.assess_job("CV text", "Job text")

        assert "assessment" in result
        assert "entity_score" in result
        assert "cost_tracking" in result
        assert "token_savings_percent" in result
        assert "metadata" in result

    @patch("src.assessment.assessor.Preprocessor")
    @patch("src.assessment.assessor.LLMProvider")
    def test_assess_job_assessment_included(
        self, mock_llm_class: MagicMock, mock_preprocessor_class: MagicMock
    ) -> None:
        """Assessment from LLM included in result."""
        mock_preprocessor = MagicMock()
        mock_preprocessor.extract_entities.return_value = ([], [], [])
        mock_preprocessor_class.return_value = mock_preprocessor

        mock_llm = MagicMock()
        mock_assessment = {"overall_score": 82, "reasoning": "Good fit"}
        mock_llm.assess_job.return_value = {
            "assessment": mock_assessment,
            "cost_tracking": {
                "estimated_input": 600,
                "estimated_output": 150,
                "estimated_cost_usd": 0.002,
                "actual_input": 550,
                "actual_output": 150,
                "actual_cost_usd": 0.00185,
            },
            "metadata": {
                "model": "claude-3-5-sonnet-20241022",
                "api_call_time_ms": 1200,
                "attempt": 1,
            },
        }
        mock_llm_class.return_value = mock_llm

        assessor = Assessor()
        assessor.preprocessor = mock_preprocessor
        assessor.llm_provider = mock_llm

        result = assessor.assess_job("CV", "Job")

        assert result["assessment"] == mock_assessment
        assert result["assessment"]["overall_score"] == 82

    @patch("src.assessment.assessor.Preprocessor")
    @patch("src.assessment.assessor.LLMProvider")
    def test_assess_job_entity_score_included(
        self, mock_llm_class: MagicMock, mock_preprocessor_class: MagicMock
    ) -> None:
        """Entity score computed and included in result."""
        mock_preprocessor = MagicMock()
        mock_preprocessor.extract_entities.side_effect = [
            (["Python"], ["AWS"], []),
            (["Python"], ["AWS"], []),
        ]
        mock_preprocessor_class.return_value = mock_preprocessor

        mock_llm = MagicMock()
        mock_llm.assess_job.return_value = {
            "assessment": {"overall_score": 75},
            "cost_tracking": {
                "estimated_input": 600,
                "estimated_output": 150,
                "estimated_cost_usd": 0.002,
                "actual_input": 550,
                "actual_output": 150,
                "actual_cost_usd": 0.00185,
            },
            "metadata": {
                "model": "claude-3-5-sonnet-20241022",
                "api_call_time_ms": 1200,
                "attempt": 1,
            },
        }
        mock_llm_class.return_value = mock_llm

        assessor = Assessor()
        assessor.preprocessor = mock_preprocessor
        assessor.llm_provider = mock_llm

        result = assessor.assess_job("CV", "Job")

        assert result["entity_score"]["overall_entity_score"] == 100.0

    @patch("src.assessment.assessor.Preprocessor")
    @patch("src.assessment.assessor.LLMProvider")
    def test_assess_job_cost_tracking_propagated(
        self, mock_llm_class: MagicMock, mock_preprocessor_class: MagicMock
    ) -> None:
        """Cost tracking from LLM included in result."""
        mock_preprocessor = MagicMock()
        mock_preprocessor.extract_entities.return_value = ([], [], [])
        mock_preprocessor_class.return_value = mock_preprocessor

        mock_llm = MagicMock()
        mock_cost = {
            "estimated_input": 600,
            "estimated_output": 150,
            "estimated_cost_usd": 0.002,
            "actual_input": 550,
            "actual_output": 150,
            "actual_cost_usd": 0.00185,
        }
        mock_llm.assess_job.return_value = {
            "assessment": {"overall_score": 75},
            "cost_tracking": mock_cost,
            "metadata": {
                "model": "claude-3-5-sonnet-20241022",
                "api_call_time_ms": 1200,
                "attempt": 1,
            },
        }
        mock_llm_class.return_value = mock_llm

        assessor = Assessor()
        assessor.preprocessor = mock_preprocessor
        assessor.llm_provider = mock_llm

        result = assessor.assess_job("CV", "Job")

        assert result["cost_tracking"] == mock_cost

    @patch("src.assessment.assessor.Preprocessor")
    @patch("src.assessment.assessor.LLMProvider")
    def test_assess_job_metadata_included(
        self, mock_llm_class: MagicMock, mock_preprocessor_class: MagicMock
    ) -> None:
        """Metadata from LLM included in result."""
        mock_preprocessor = MagicMock()
        mock_preprocessor.extract_entities.return_value = ([], [], [])
        mock_preprocessor_class.return_value = mock_preprocessor

        mock_llm = MagicMock()
        mock_metadata = {
            "model": "claude-3-5-sonnet-20241022",
            "api_call_time_ms": 1200,
            "attempt": 1,
        }
        mock_llm.assess_job.return_value = {
            "assessment": {"overall_score": 75},
            "cost_tracking": {
                "estimated_input": 600,
                "estimated_output": 150,
                "estimated_cost_usd": 0.002,
                "actual_input": 550,
                "actual_output": 150,
                "actual_cost_usd": 0.00185,
            },
            "metadata": mock_metadata,
        }
        mock_llm_class.return_value = mock_llm

        assessor = Assessor()
        assessor.preprocessor = mock_preprocessor
        assessor.llm_provider = mock_llm

        result = assessor.assess_job("CV", "Job")

        assert result["metadata"] == mock_metadata

    @patch("src.assessment.assessor.Preprocessor")
    @patch("src.assessment.assessor.LLMProvider")
    def test_assess_job_token_savings_computed(
        self, mock_llm_class: MagicMock, mock_preprocessor_class: MagicMock
    ) -> None:
        """Token savings percentage computed."""
        mock_preprocessor = MagicMock()
        mock_preprocessor.extract_entities.return_value = ([], [], [])
        mock_preprocessor_class.return_value = mock_preprocessor

        mock_llm = MagicMock()
        mock_llm.assess_job.return_value = {
            "assessment": {"overall_score": 75},
            "cost_tracking": {
                "estimated_input": 600,
                "estimated_output": 150,
                "estimated_cost_usd": 0.002,
                "actual_input": 400,  # 400/600 = 66.7% of baseline
                "actual_output": 150,
                "actual_cost_usd": 0.00123,
            },
            "metadata": {
                "model": "claude-3-5-sonnet-20241022",
                "api_call_time_ms": 1200,
                "attempt": 1,
            },
        }
        mock_llm_class.return_value = mock_llm

        assessor = Assessor()
        assessor.preprocessor = mock_preprocessor
        assessor.llm_provider = mock_llm
        # Mock baseline to be 600 so savings = (1 - 400/600) * 100 ≈ 33.3%
        with patch.object(assessor, "_estimate_baseline_tokens", return_value=600):
            result = assessor.assess_job("CV", "Job")
            # Savings = (1 - actual/baseline) * 100 = (1 - 400/600) * 100 ≈ 33.3%
            assert result["token_savings_percent"] > 30
            assert result["token_savings_percent"] < 40


class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch("src.assessment.assessor.Preprocessor")
    @patch("src.assessment.assessor.LLMProvider")
    def test_assess_job_empty_cv(self, mock_llm_class: MagicMock, mock_prep_class: MagicMock) -> None:
        """Raises error if CV empty."""
        assessor = Assessor()

        with pytest.raises(ValueError, match="CV text cannot be empty"):
            assessor.assess_job("", "Job text")

    @patch("src.assessment.assessor.Preprocessor")
    @patch("src.assessment.assessor.LLMProvider")
    def test_assess_job_empty_job(self, mock_llm_class: MagicMock, mock_prep_class: MagicMock) -> None:
        """Raises error if job description empty."""
        assessor = Assessor()

        with pytest.raises(ValueError, match="Job description cannot be empty"):
            assessor.assess_job("CV text", "")

    @patch("src.assessment.assessor.Preprocessor")
    @patch("src.assessment.assessor.LLMProvider")
    def test_assess_job_whitespace_cv(self, mock_llm_class: MagicMock, mock_prep_class: MagicMock) -> None:
        """Raises error if CV is only whitespace."""
        assessor = Assessor()

        with pytest.raises(ValueError, match="CV text cannot be empty"):
            assessor.assess_job("   \n  ", "Job text")

    @patch("src.assessment.assessor.Preprocessor")
    @patch("src.assessment.assessor.LLMProvider")
    def test_assess_job_whitespace_job(self, mock_llm_class: MagicMock, mock_prep_class: MagicMock) -> None:
        """Raises error if job is only whitespace."""
        assessor = Assessor()

        with pytest.raises(ValueError, match="Job description cannot be empty"):
            assessor.assess_job("CV text", "   \t  ")

    @patch("src.assessment.assessor.Preprocessor")
    @patch("src.assessment.assessor.LLMProvider")
    def test_assess_job_with_special_characters(
        self, mock_llm_class: MagicMock, mock_preprocessor_class: MagicMock
    ) -> None:
        """Handles special characters in CV/job."""
        mock_preprocessor = MagicMock()
        mock_preprocessor.extract_entities.return_value = ([], [], [])
        mock_preprocessor_class.return_value = mock_preprocessor

        mock_llm = MagicMock()
        mock_llm.assess_job.return_value = {
            "assessment": {"overall_score": 75},
            "cost_tracking": {
                "estimated_input": 600,
                "estimated_output": 150,
                "estimated_cost_usd": 0.002,
                "actual_input": 550,
                "actual_output": 150,
                "actual_cost_usd": 0.00185,
            },
            "metadata": {
                "model": "claude-3-5-sonnet-20241022",
                "api_call_time_ms": 1200,
                "attempt": 1,
            },
        }
        mock_llm_class.return_value = mock_llm

        assessor = Assessor()
        assessor.preprocessor = mock_preprocessor
        assessor.llm_provider = mock_llm

        result = assessor.assess_job(
            "C++ & Python Developer ($100k)", "Rust/Go expert (100% remote)"
        )

        assert "assessment" in result

    @patch("src.assessment.assessor.Preprocessor")
    @patch("src.assessment.assessor.LLMProvider")
    def test_assess_job_very_long_text(
        self, mock_llm_class: MagicMock, mock_preprocessor_class: MagicMock
    ) -> None:
        """Handles very long CV and job descriptions."""
        mock_preprocessor = MagicMock()
        mock_preprocessor.extract_entities.return_value = ([], [], [])
        mock_preprocessor_class.return_value = mock_preprocessor

        mock_llm = MagicMock()
        mock_llm.assess_job.return_value = {
            "assessment": {"overall_score": 75},
            "cost_tracking": {
                "estimated_input": 2000,
                "estimated_output": 150,
                "estimated_cost_usd": 0.006,
                "actual_input": 1500,
                "actual_output": 150,
                "actual_cost_usd": 0.0045,
            },
            "metadata": {
                "model": "claude-3-5-sonnet-20241022",
                "api_call_time_ms": 2000,
                "attempt": 1,
            },
        }
        mock_llm_class.return_value = mock_llm

        assessor = Assessor()
        assessor.preprocessor = mock_preprocessor
        assessor.llm_provider = mock_llm
        # Mock baseline to be 2000 so savings = (1 - 1500/2000) * 100 = 25%
        with patch.object(assessor, "_estimate_baseline_tokens", return_value=2000):
            cv_long = "CV " * 500  # Very long CV
            job_long = "Job " * 500  # Very long job

            result = assessor.assess_job(cv_long, job_long)
            assert "assessment" in result
            assert result["token_savings_percent"] > 0
