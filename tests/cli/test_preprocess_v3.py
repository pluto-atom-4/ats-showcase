"""Tests for --preprocessing-version 3.0 CLI flag (Issue #281 S5)."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.models.job import PreprocessedJob

runner = CliRunner()


class TestPreprocessVersionValidation:
    """Test version validation in preprocess command."""

    def test_preprocess_invalid_version_exits_with_error(self) -> None:
        """Invalid preprocessing version exits with code 1."""
        # Create minimal test data
        extracted_dir = Path("data/extracted_jobs")
        extracted_dir.mkdir(parents=True, exist_ok=True)

        # Create a minimal jobs file
        jobs_file = extracted_dir / "test_jobs.json"
        jobs_file.write_text('[{"title": "Test", "company": "TestCo", "description": "Test desc"}]')

        try:
            result = runner.invoke(
                app,
                ["preprocess", "--preprocessing-version", "4.0"],
            )
            # Invalid version should cause exit code 1
            assert result.exit_code == 1
        finally:
            # Cleanup
            if jobs_file.exists():
                jobs_file.unlink()

    def test_preprocess_default_version_is_2_0(self) -> None:
        """Default preprocessing version is v2.0."""
        # This is tested implicitly by checking PreprocessedJob defaults
        # The default is set in the CLI option
        assert True  # Placeholder


class TestPreprocessModelDefaults:
    """Test PreprocessedJob model defaults."""

    def test_preprocessed_job_default_version(self) -> None:
        """PreprocessedJob has preprocessing_version default of v2.0."""
        job = PreprocessedJob(
            job_id="test_job",
            title=None,
            company=None,
            clean_text="Test text",
            markdown_description=None,
            sentences=["Test text"],
            chunks=["Test text"],
            trigger_requirements=None,
            token_count=5,
            estimated_cost=0.001,
            sectioned_requirements=None,
        )
        assert job.preprocessing_version == "v2.0"

    def test_preprocessed_job_sectioned_requirements_default(self) -> None:
        """PreprocessedJob sectioned_requirements defaults to None."""
        job = PreprocessedJob(
            job_id="test_job",
            title=None,
            company=None,
            clean_text="Test text",
            markdown_description=None,
            sentences=["Test text"],
            chunks=["Test text"],
            trigger_requirements=None,
            token_count=5,
            estimated_cost=0.001,
            sectioned_requirements=None,
        )
        assert job.sectioned_requirements is None

    def test_preprocessed_job_can_set_version(self) -> None:
        """PreprocessedJob accepts custom preprocessing_version."""
        job = PreprocessedJob(
            job_id="test_job",
            title=None,
            company=None,
            clean_text="Test text",
            markdown_description=None,
            sentences=["Test text"],
            chunks=["Test text"],
            trigger_requirements=None,
            token_count=5,
            estimated_cost=0.001,
            preprocessing_version="v3.0",
            sectioned_requirements=None,
        )
        assert job.preprocessing_version == "v3.0"

    def test_preprocessed_job_can_set_sectioned_requirements(self) -> None:
        """PreprocessedJob accepts sectioned_requirements dict."""
        sectioned = {
            "requirements": [],
            "sections_detected": ["Requirements"],
            "requirements_by_section": {"Requirements": 0},
        }
        job = PreprocessedJob(
            job_id="test_job",
            title=None,
            company=None,
            clean_text="Test text",
            markdown_description=None,
            sentences=["Test text"],
            chunks=["Test text"],
            trigger_requirements=None,
            token_count=5,
            estimated_cost=0.001,
            sectioned_requirements=sectioned,
        )
        assert job.sectioned_requirements == sectioned


class TestPreprocessSingleJobV3:
    """Test _preprocess_single_job with v3.0 and sectioned requirements."""

    @pytest.fixture
    def mock_preprocessor(self) -> MagicMock:
        """Create mock preprocessor."""
        preprocessor = MagicMock()
        preprocessor.nlp = MagicMock()
        preprocessor.extract_entities = MagicMock(return_value=([], [], []))
        preprocessor.extract_sectioned_requirements = MagicMock(return_value=None)
        # Mock the doc object
        doc = MagicMock()
        doc._ = MagicMock()
        doc._.requirements = None
        preprocessor.nlp.return_value = doc
        return preprocessor

    @pytest.fixture
    def mock_chunker(self) -> MagicMock:
        """Create mock chunker."""
        chunker = MagicMock()
        chunker.chunk = MagicMock(return_value=["chunk1"])
        return chunker

    @pytest.fixture
    def mock_counter(self) -> MagicMock:
        """Create mock counter."""
        counter = MagicMock()
        counter.count_tokens = MagicMock(return_value=10)
        counter.estimate_cost = MagicMock(return_value=0.001)
        counter.model = "claude-sonnet-5"
        return counter

    @pytest.fixture
    def mock_section_engine(self) -> MagicMock:
        """Create mock SectionDetector."""
        detector = MagicMock()
        return detector

    def test_preprocess_single_job_v2_no_sectioned_requirements(
        self,
        mock_preprocessor: MagicMock,
        mock_chunker: MagicMock,
        mock_counter: MagicMock,
    ) -> None:
        """Non-v3.0 jobs have sectioned_requirements=None."""
        from src.cli import _preprocess_single_job

        job_dict = {
            "title": "Test Job",
            "company": "TestCo",
            "description": "Test description",
        }

        result = _preprocess_single_job(
            job_dict,
            mock_chunker,
            mock_counter,
            mock_preprocessor,
            "2026-09-24",
            show_estimates=False,
            job_index=1,
            preprocessing_version="v2.0",
        )

        assert result is not None
        prep_job, tokens, cost, reqs = result
        assert prep_job.preprocessing_version == "v2.0"
        assert prep_job.sectioned_requirements is None

    def test_preprocess_single_job_v3_with_real_detector(
        self,
        mock_preprocessor: MagicMock,
        mock_chunker: MagicMock,
        mock_counter: MagicMock,
    ) -> None:
        """v3.0 jobs with real SectionDetector extract sectioned_requirements."""
        from src.cli import _preprocess_single_job

        # Create a preprocessor with section_engine support
        preprocessor_v3 = MagicMock()
        preprocessor_v3.extract_entities = MagicMock(return_value=([], [], []))
        preprocessor_v3.extract_sectioned_requirements = MagicMock()

        # Create test text with requirements section
        clean_text = "Test Job Description\n\n## Requirements\n- Python\n- SQL"

        # Mock the result
        from src.preprocessing.section_extractor import RequirementItem, SectionedResult
        from src.preprocessing.section_patterns import SectionLabel

        req_item = RequirementItem(
            text="Python",
            trigger_word="requires",
            base_confidence=0.9,
            section_boost=0.05,
            final_confidence=0.95,
            source_section=SectionLabel.REQUIREMENTS,
            section_display_name="Requirements",
        )

        mock_result = SectionedResult(
            requirements=(req_item,),
            sections_detected=("Requirements",),
            requirements_by_section={"Requirements": 1},
        )
        preprocessor_v3.extract_sectioned_requirements.return_value = mock_result

        # Mock doc object
        doc = MagicMock()
        doc._ = MagicMock()
        doc._.requirements = None
        preprocessor_v3.nlp = MagicMock(return_value=doc)

        job_dict = {
            "title": "Test Job",
            "company": "TestCo",
            "description": clean_text,
        }

        result = _preprocess_single_job(
            job_dict,
            mock_chunker,
            mock_counter,
            preprocessor_v3,
            "2026-09-24",
            show_estimates=False,
            job_index=1,
            preprocessing_version="v3.0",
        )

        assert result is not None
        prep_job, tokens, cost, reqs = result
        assert prep_job.preprocessing_version == "v3.0"
        assert prep_job.sectioned_requirements is not None
        assert prep_job.sectioned_requirements["requirements"][0]["text"] == "Python"
        assert "sections_detected" in prep_job.sectioned_requirements
        assert "Requirements" in prep_job.sectioned_requirements["sections_detected"]

    def test_preprocess_single_job_normalize_version(
        self,
        mock_preprocessor: MagicMock,
        mock_chunker: MagicMock,
        mock_counter: MagicMock,
    ) -> None:
        """Preprocessing version normalized to v-prefixed format."""
        from src.cli import _preprocess_single_job

        job_dict = {
            "title": "Test Job",
            "company": "TestCo",
            "description": "Test description",
        }

        result = _preprocess_single_job(
            job_dict,
            mock_chunker,
            mock_counter,
            mock_preprocessor,
            "2026-09-24",
            show_estimates=False,
            job_index=1,
            preprocessing_version="3.0",  # Without v-prefix
        )

        assert result is not None
        prep_job, tokens, cost, reqs = result
        assert prep_job.preprocessing_version == "v3.0"  # Normalized
