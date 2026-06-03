"""Unit tests for Phase 4 LLM assessment."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from llm.provider import AssessmentResult, LLMProvider
from storage.assessment_store import AssessmentStore


class TestAssessmentResult:
    """Test AssessmentResult class."""

    def test_init(self):
        """Test initialization."""
        result = AssessmentResult(
            job_id="job_1",
            overall_score=85.0,
            tech_score=90.0,
            seniority_score=80.0,
            location_score=85.0,
            recommendations=["Learn Kubernetes"],
            summary="Good fit",
            tokens_used=650,
            actual_cost=0.002,
        )

        assert result.job_id == "job_1"
        assert result.overall_score == 85.0
        assert result.tech_score == 90.0

    def test_to_dict(self):
        """Test conversion to dict."""
        result = AssessmentResult(
            job_id="job_1",
            overall_score=85.0,
            tech_score=90.0,
            seniority_score=80.0,
            location_score=85.0,
            recommendations=["Learn Kubernetes"],
            summary="Good fit",
            tokens_used=650,
            actual_cost=0.002,
        )

        result_dict = result.to_dict()
        assert result_dict["job_id"] == "job_1"
        assert result_dict["overall_score"] == 85.0
        assert isinstance(result_dict, dict)

    def test_to_assessment_model(self):
        """Test conversion to Pydantic model."""
        result = AssessmentResult(
            job_id="job_1",
            overall_score=85.0,
            tech_score=90.0,
            seniority_score=80.0,
            location_score=85.0,
            recommendations=["Learn Kubernetes"],
            summary="Good fit",
            tokens_used=650,
            actual_cost=0.002,
        )

        model = result.to_assessment_model()
        assert model.job_id == "job_1"
        assert model.overall_score == 85.0


class TestLLMProvider:
    """Test LLMProvider class."""

    @pytest.fixture
    def mock_anthropic(self):
        """Mock Anthropic client."""
        with patch("anthropic.Anthropic") as mock_class:
            client = MagicMock()
            mock_class.return_value = client

            # Mock successful response with proper content structure
            response = MagicMock()
            response.usage.input_tokens = 600
            response.usage.output_tokens = 50

            # Create a proper TextBlock-like object with .text attribute
            text_block = MagicMock()
            text_block.text = json.dumps(
                {
                    "tech_score": 85,
                    "seniority_score": 80,
                    "location_score": 70,
                    "overall_score": 78,
                    "recommendations": ["Learn AWS"],
                    "summary": "Good fit",
                }
            )

            # Make response.content iterable as a list
            response.content = [text_block]
            client.messages.create.return_value = response

            yield mock_class, client

    def test_init_with_api_key(self, mock_anthropic):
        """Test initialization with API key."""
        mock, _ = mock_anthropic
        provider = LLMProvider(api_key="test-key")

        assert provider.api_key == "test-key"
        assert provider.MODEL == "claude-opus-4-1-20250805"

    def test_init_without_api_key_raises(self):
        """Test initialization without API key raises error."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError):
                LLMProvider()

    def test_assess_job_success(self, mock_anthropic):
        """Test successful job assessment."""
        mock, client = mock_anthropic
        provider = LLMProvider(api_key="test-key")

        result = provider.assess_job(
            job_id="job_1",
            job_chunks=["Senior Engineer", "Seattle, WA"],
            cv_text="Python developer with 5 years experience",
        )

        assert result.job_id == "job_1"
        assert result.overall_score == 78
        assert result.tech_score == 85
        assert result.tokens_used == 650

    def test_assess_job_with_markdown_json(self, mock_anthropic):
        """Test assessment with markdown-wrapped JSON response."""
        mock, client = mock_anthropic

        # Mock response with markdown code block - proper content structure
        response = MagicMock()
        response.usage.input_tokens = 600
        response.usage.output_tokens = 50

        text_block = MagicMock()
        text_block.text = (
            "```json\n"
            + json.dumps(
                {
                    "tech_score": 85,
                    "seniority_score": 80,
                    "location_score": 70,
                    "overall_score": 78,
                    "recommendations": ["Learn AWS"],
                    "summary": "Good fit",
                }
            )
            + "\n```"
        )
        response.content = [text_block]
        client.messages.create.return_value = response

        provider = LLMProvider(api_key="test-key")
        result = provider.assess_job(
            job_id="job_1",
            job_chunks=["Senior Engineer"],
            cv_text="Python developer",
        )

        assert result.overall_score == 78

    def test_assess_job_token_cost_calculation(self, mock_anthropic):
        """Test token cost calculation."""
        mock, client = mock_anthropic
        provider = LLMProvider(api_key="test-key")

        result = provider.assess_job(
            job_id="job_1",
            job_chunks=["Job description"],
            cv_text="CV text",
        )

        # Cost: (input_tokens / 1M * $0.003) + (output_tokens / 1M * $0.015)
        expected_cost = (600 / 1_000_000) * 0.003 + (50 / 1_000_000) * 0.015
        assert abs(result.actual_cost - expected_cost) < 0.000001

    def test_build_assessment_prompt(self):
        """Test prompt building."""
        provider = LLMProvider(api_key="test-key")

        prompt = provider._build_assessment_prompt(
            cv_text="Python developer",
            job_text="Senior Engineer",
        )

        assert "Python developer" in prompt
        assert "Senior Engineer" in prompt
        assert "tech_score" in prompt
        assert "overall_score" in prompt


class TestAssessmentStore:
    """Test AssessmentStore class."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        Path(db_path).unlink(missing_ok=True)

    def test_init_creates_db(self, temp_db):
        """Test database initialization."""
        store = AssessmentStore(db_path=temp_db)
        store._close_db()

        assert Path(temp_db).exists()

    def test_save_assessment(self, temp_db):
        """Test saving assessment."""
        store = AssessmentStore(db_path=temp_db)

        store.save_assessment(
            job_id="job_1",
            title="Senior Engineer",
            company="TechCorp",
            location="SF, CA",
            overall_score=85.0,
            tech_score=90.0,
            seniority_score=80.0,
            location_score=75.0,
            recommendations=["Learn AWS"],
            summary="Good fit",
            tokens_used=650,
            actual_cost=0.002,
        )

        result = store.get_assessment_by_id("job_1")
        assert result is not None
        assert result["overall_score"] == 85.0
        assert result["title"] == "Senior Engineer"

        store._close_db()

    def test_get_top_matches(self, temp_db):
        """Test getting top matches."""
        store = AssessmentStore(db_path=temp_db)

        # Save multiple assessments
        for i in range(5):
            store.save_assessment(
                job_id=f"job_{i}",
                title=f"Job {i}",
                company="TechCorp",
                location="SF",
                overall_score=70 + (i * 5),
                tech_score=75,
                seniority_score=75,
                location_score=75,
                recommendations=[],
                summary="",
                tokens_used=650,
                actual_cost=0.002,
            )

        top = store.get_top_matches(limit=2)
        assert len(top) == 2
        assert top[0]["overall_score"] >= top[1]["overall_score"]

        store._close_db()

    def test_get_assessments_by_score(self, temp_db):
        """Test filtering by score."""
        store = AssessmentStore(db_path=temp_db)

        # Save assessments with different scores
        for i, score in enumerate([45, 55, 65, 75, 85, 95]):
            store.save_assessment(
                job_id=f"job_{i}",
                title=f"Job {i}",
                company="TechCorp",
                location="SF",
                overall_score=float(score),
                tech_score=75,
                seniority_score=75,
                location_score=75,
                recommendations=[],
                summary="",
                tokens_used=650,
                actual_cost=0.002,
            )

        results = store.get_assessments_by_score(min_score=70)
        assert len(results) == 3  # 75, 85, 95

        store._close_db()

    def test_search_assessments(self, temp_db):
        """Test full-text search."""
        store = AssessmentStore(db_path=temp_db)

        store.save_assessment(
            job_id="job_1",
            title="Python Developer",
            company="TechCorp",
            location="SF",
            overall_score=80.0,
            tech_score=85,
            seniority_score=75,
            location_score=75,
            recommendations=["Learn AWS"],
            summary="Strong Python skills",
            tokens_used=650,
            actual_cost=0.002,
        )

        results = store.search_assessments("Python")
        assert len(results) >= 1

        store._close_db()

    def test_get_stats(self, temp_db):
        """Test getting statistics."""
        store = AssessmentStore(db_path=temp_db)

        for i in range(3):
            store.save_assessment(
                job_id=f"job_{i}",
                title=f"Job {i}",
                company="TechCorp",
                location="SF",
                overall_score=80.0,
                tech_score=85,
                seniority_score=75,
                location_score=75,
                recommendations=[],
                summary="",
                tokens_used=650,
                actual_cost=0.002,
            )

        stats = store.get_stats()
        assert stats["total_assessments"] == 3
        assert stats["avg_score"] == 80.0
        assert abs(stats["total_cost"] - 0.006) < 0.0001

        store._close_db()

    def test_get_score_distribution(self, temp_db):
        """Test score distribution."""
        store = AssessmentStore(db_path=temp_db)

        # Save assessments in different ranges
        scores = [25, 55, 72, 88]
        for i, score in enumerate(scores):
            store.save_assessment(
                job_id=f"job_{i}",
                title=f"Job {i}",
                company="TechCorp",
                location="SF",
                overall_score=float(score),
                tech_score=75,
                seniority_score=75,
                location_score=75,
                recommendations=[],
                summary="",
                tokens_used=650,
                actual_cost=0.002,
            )

        distribution = store.get_score_distribution()
        assert distribution["0-50"] >= 1  # Job with score 25
        assert distribution["50-70"] >= 1  # Job with score 55
        assert distribution["70-85"] >= 1  # Job with score 72
        assert distribution["85-100"] >= 1  # Job with score 88

        store._close_db()

    def test_count_assessments(self, temp_db):
        """Test counting assessments."""
        store = AssessmentStore(db_path=temp_db)

        for i in range(5):
            store.save_assessment(
                job_id=f"job_{i}",
                title=f"Job {i}",
                company="TechCorp",
                location="SF",
                overall_score=80.0,
                tech_score=85,
                seniority_score=75,
                location_score=75,
                recommendations=[],
                summary="",
                tokens_used=650,
                actual_cost=0.002,
            )

        assert store.count_assessments() == 5

        store._close_db()

    def test_delete_assessment(self, temp_db):
        """Test deleting assessment."""
        store = AssessmentStore(db_path=temp_db)

        store.save_assessment(
            job_id="job_1",
            title="Senior Engineer",
            company="TechCorp",
            location="SF",
            overall_score=85.0,
            tech_score=90,
            seniority_score=80,
            location_score=75,
            recommendations=[],
            summary="",
            tokens_used=650,
            actual_cost=0.002,
        )

        assert store.count_assessments() == 1

        store.delete_assessment("job_1")

        assert store.count_assessments() == 0

        store._close_db()

    def test_persistence(self, temp_db):
        """Test database persistence."""
        # First connection
        store1 = AssessmentStore(db_path=temp_db)
        store1.save_assessment(
            job_id="job_1",
            title="Job",
            company="Corp",
            location="SF",
            overall_score=80.0,
            tech_score=85,
            seniority_score=75,
            location_score=75,
            recommendations=[],
            summary="",
            tokens_used=650,
            actual_cost=0.002,
        )
        store1._close_db()

        # Second connection
        store2 = AssessmentStore(db_path=temp_db)
        result = store2.get_assessment_by_id("job_1")
        assert result is not None
        assert result["title"] == "Job"
        store2._close_db()
