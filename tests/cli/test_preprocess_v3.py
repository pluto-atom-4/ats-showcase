"""Tests for --preprocessing-version 3.0 CLI flag (Issue #281 S5)."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from src.cli import _build_sectioned_requirements, app
from src.models.job import PreprocessedJob
from src.preprocessing.section_detector import SectionDetector
from src.tokenization.preprocessor import Preprocessor

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


class TestBuildSectionedRequirements:
    """Test _build_sectioned_requirements helper with real detector."""

    def test_build_sectioned_requirements_with_real_detector(self, monkeypatch: Any) -> None:
        """Real Preprocessor with SectionDetector extracts requirements correctly."""
        # Monkeypatch to skip spaCy model loading
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        # Create real detector and preprocessor
        detector = SectionDetector()
        preprocessor = Preprocessor(extract_requirements=False, section_engine=detector)

        # Test text with Requirements section and Benefits section
        clean_text = """## Requirements
- 5+ years Python experience required
- Must know SQL

## Benefits
- Health insurance
- 401k matching"""

        # Call the helper
        result = _build_sectioned_requirements(preprocessor, clean_text)

        # Print real output first for verification
        print("\n=== Real Sectioned Requirements Output ===")
        print(f"Result type: {type(result)}")
        print(f"Result: {result}")

        # Assert exact values
        assert result is not None, "Should return dict for v3.0 with section_engine"
        assert isinstance(result, dict), "Should return dict, not SectionedResult object"
        assert "requirements" in result, "Must have 'requirements' key"
        assert "sections_detected" in result, "Must have 'sections_detected' key"
        assert "schema_version" in result, "Must have 'schema_version' key"
        assert result["schema_version"] == "3.0", "Schema version must be 3.0"

        # Check that requirements were extracted from Requirements section
        requirements = result["requirements"]
        assert len(requirements) > 0, "Should have extracted requirements"
        # Verify first requirement is from Requirements section
        req_texts = [req["text"] for req in requirements]
        assert any("Python" in t for t in req_texts), "Should extract Python requirement"
        assert any("SQL" in t for t in req_texts), "Should extract SQL requirement"

        # Check sections detected includes Requirements
        sections = result["sections_detected"]
        assert "SECTION_REQUIREMENTS" in sections, "Should detect SECTION_REQUIREMENTS"
        # Benefits may or may not be detected depending on matching requirements

    def test_build_sectioned_requirements_without_engine_returns_none(self, monkeypatch: Any) -> None:
        """Preprocessor without section_engine returns None (v2.0 path)."""
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        # Create preprocessor WITHOUT section_engine (v2.0 behavior)
        preprocessor = Preprocessor(extract_requirements=False, section_engine=None)

        clean_text = """## Requirements
- Python
- SQL"""

        result = _build_sectioned_requirements(preprocessor, clean_text)

        # Must return None when engine is not configured
        assert result is None, "Should return None when section_engine is None"


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
