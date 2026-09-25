"""MODEL-FREE tests for parity report (Issue #281 S6).

Tests parity_check.py functions without requiring spaCy model.
Uses monkeypatch to avoid model loading for most tests.
Includes regression test running real extraction path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

# Load parity_check module using importlib (no conftest.py needed)
_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
_PARITY_CHECK_PATH = _SCRIPTS_DIR / "parity_check.py"

_spec = importlib.util.spec_from_file_location("parity_check", _PARITY_CHECK_PATH)
parity_check = importlib.util.module_from_spec(_spec)
sys.modules["parity_check"] = parity_check
_spec.loader.exec_module(parity_check)


@pytest.fixture
def parity_no_headers_fixture() -> Path:
    """Path to parity_no_headers.md fixture."""
    return Path(__file__).parent / "fixtures" / "parity_no_headers.md"


@pytest.fixture
def parity_benefits_heavy_fixture() -> Path:
    """Path to parity_benefits_heavy.md fixture."""
    return Path(__file__).parent / "fixtures" / "parity_benefits_heavy.md"


@pytest.fixture
def raw_job_description_fixture() -> Path:
    """Path to raw_job_description.md fixture."""
    return Path(__file__).parent.parent / "poc" / "fixtures" / "raw_job_description.md"


class TestLoadFixture:
    """Test fixture loading."""

    def test_load_existing_fixture(self, parity_benefits_heavy_fixture: Path) -> None:
        """Load existing fixture file."""
        text = parity_check._load_fixture(parity_benefits_heavy_fixture)
        assert text is not None
        assert "Data Engineer" in text
        assert "Requirements" in text

    def test_load_missing_fixture(self) -> None:
        """Handle missing fixture file gracefully."""
        missing = Path("/nonexistent/path/fixture.md")
        text = parity_check._load_fixture(missing)
        assert text is None


class TestCheckModelAvailable:
    """Test model availability check."""

    def test_model_check_returns_bool(self) -> None:
        """Model check always returns bool."""
        result = parity_check._check_model_available("en_core_web_md")
        assert isinstance(result, bool)

    def test_model_check_with_invalid_name(self) -> None:
        """Invalid model name returns False."""
        result = parity_check._check_model_available("nonexistent_model_xyz_123")
        assert result is False


class TestExtractV3Metrics:
    """Test v3 extraction with section detection."""

    def test_v3_metrics_on_benefits_heavy(self, parity_benefits_heavy_fixture: Path) -> None:
        """Extract v3 metrics from benefits-heavy fixture."""
        text = parity_check._load_fixture(parity_benefits_heavy_fixture)
        assert text is not None

        # Monkeypatch Preprocessor._load_model to avoid model loading
        from src.tokenization import preprocessor as prep_module

        original_load_model = prep_module.Preprocessor._load_model

        def mock_load_model(self: Any) -> None:
            self.nlp = None

        prep_module.Preprocessor._load_model = mock_load_model  # type: ignore[method-assign]

        try:
            count, sections, req_by_section, avg_conf = parity_check._extract_v3_metrics(text)

            # Assertions: exact types and ranges
            assert isinstance(count, int)
            assert count >= 0
            assert isinstance(sections, list)
            assert all(isinstance(s, str) for s in sections)
            assert isinstance(req_by_section, dict)
            assert isinstance(avg_conf, float)
            assert 0.0 <= avg_conf <= 1.0

            # parity_benefits_heavy has "## Requirements" section
            # v3 should detect it
            assert "section_requirements" in [s.lower() for s in sections]

            # Benefits/Compensation should NOT be in requirements_by_section
            # (filtered by SKIP_SECTIONS in v3 extraction)
            # If "benefits" or "compensation" are present, their count must be 0
            if "benefits" in req_by_section:
                assert req_by_section["benefits"] == 0
            if "compensation" in req_by_section:
                assert req_by_section["compensation"] == 0

        finally:
            prep_module.Preprocessor._load_model = original_load_model  # type: ignore[method-assign]

    def test_v3_metrics_on_no_headers(self, parity_no_headers_fixture: Path) -> None:
        """Extract v3 metrics from fixture without headers."""
        text = parity_check._load_fixture(parity_no_headers_fixture)
        assert text is not None

        from src.tokenization import preprocessor as prep_module

        original_load_model = prep_module.Preprocessor._load_model

        def mock_load_model(self: Any) -> None:
            self.nlp = None

        prep_module.Preprocessor._load_model = mock_load_model  # type: ignore[method-assign]

        try:
            count, sections, req_by_section, avg_conf = parity_check._extract_v3_metrics(text)

            # No explicit headers => fewer sections detected
            assert isinstance(count, int)
            assert isinstance(sections, list)
            # For plain-text no-header fixture, sections should be empty or minimal
            # (spaCy patterns match explicit headers)
        finally:
            prep_module.Preprocessor._load_model = original_load_model  # type: ignore[method-assign]

    def test_v3_metrics_empty_text(self) -> None:
        """Extract v3 metrics from empty text."""
        from src.tokenization import preprocessor as prep_module

        original_load_model = prep_module.Preprocessor._load_model

        def mock_load_model(self: Any) -> None:
            self.nlp = None

        prep_module.Preprocessor._load_model = mock_load_model  # type: ignore[method-assign]

        try:
            count, sections, req_by_section, avg_conf = parity_check._extract_v3_metrics("")
            assert count == 0
            assert sections == []
            assert req_by_section == {}
            assert avg_conf == 0.0
        finally:
            prep_module.Preprocessor._load_model = original_load_model  # type: ignore[method-assign]

    def test_v3_metrics_real_extraction_regression(self, parity_benefits_heavy_fixture: Path) -> None:
        """REGRESSION: Real v3 extraction without monkeypatching (no model-free guarantee violation)."""
        text = parity_check._load_fixture(parity_benefits_heavy_fixture)
        assert text is not None

        # Run REAL extraction path without monkeypatch
        # extract_sectioned() is model-free, so this should work
        try:
            count, sections, req_by_section, avg_conf = parity_check._extract_v3_metrics(text)

            # Verify types and ranges
            assert isinstance(count, int)
            assert count >= 0
            assert isinstance(sections, list)
            assert all(isinstance(s, str) for s in sections)
            assert isinstance(req_by_section, dict)
            assert isinstance(avg_conf, float)
            assert 0.0 <= avg_conf <= 1.0

            # Verify consistency between count and req_by_section sum
            section_sum = sum(req_by_section.values())
            assert section_sum == count
        except Exception as e:
            # If real extraction fails, it's a regression - propagate error
            pytest.fail(f"Real v3 extraction failed (not model-free?): {e}")


class TestExtractLegacyMetrics:
    """Test legacy extraction (model-free path)."""

    def test_legacy_metrics_model_unavailable(self, parity_benefits_heavy_fixture: Path) -> None:
        """Legacy extraction with unavailable model returns empty."""
        text = parity_check._load_fixture(parity_benefits_heavy_fixture)
        assert text is not None

        # Monkeypatch _load_model to set nlp=None (model unavailable)
        from src.tokenization import preprocessor as prep_module

        original_load_model = prep_module.Preprocessor._load_model

        def mock_load_model(self: Any) -> None:
            self.nlp = None

        prep_module.Preprocessor._load_model = mock_load_model  # type: ignore[method-assign]

        try:
            count, reqs, error_msg = parity_check._extract_legacy_metrics(text)
            # With nlp=None, extract_entities returns empty lists
            assert count == 0
            assert reqs == []
        finally:
            prep_module.Preprocessor._load_model = original_load_model  # type: ignore[method-assign]


class TestValidateSchema:
    """Test schema validation."""

    def test_valid_schema(self) -> None:
        """Valid schema passes validation."""
        result = {
            "schema_version": "3.0",
            "requirements": [
                {
                    "text": "5+ years Python",
                    "final_confidence": 0.85,
                }
            ],
            "requirements_by_section": {
                "SECTION_REQUIREMENTS": 1,
            },
        }
        assert parity_check._validate_schema(result) is True

    def test_invalid_schema_version(self) -> None:
        """Invalid schema_version fails."""
        result = {
            "schema_version": "2.0",  # Wrong version
            "requirements": [],
            "requirements_by_section": {},
        }
        assert parity_check._validate_schema(result) is False

    def test_invalid_confidence_too_high(self) -> None:
        """Confidence > 1.0 fails."""
        result = {
            "schema_version": "3.0",
            "requirements": [
                {
                    "text": "5+ years Python",
                    "final_confidence": 1.5,  # Out of range
                }
            ],
            "requirements_by_section": {
                "requirements": 1,
            },
        }
        assert parity_check._validate_schema(result) is False

    def test_invalid_confidence_negative(self) -> None:
        """Confidence < 0.0 fails."""
        result = {
            "schema_version": "3.0",
            "requirements": [
                {
                    "text": "5+ years Python",
                    "final_confidence": -0.1,  # Out of range
                }
            ],
            "requirements_by_section": {
                "requirements": 1,
            },
        }
        assert parity_check._validate_schema(result) is False

    def test_count_mismatch(self) -> None:
        """Requirement count != section sum fails."""
        result = {
            "schema_version": "3.0",
            "requirements": [
                {"text": "req1", "final_confidence": 0.8},
                {"text": "req2", "final_confidence": 0.7},
            ],
            "requirements_by_section": {
                "requirements": 1,  # Should be 2
            },
        }
        assert parity_check._validate_schema(result) is False


class TestGenerateParityReport:
    """Test parity report generation."""

    def test_report_with_single_fixture(self, parity_benefits_heavy_fixture: Path) -> None:
        """Generate report for single fixture."""
        from src.tokenization import preprocessor as prep_module

        original_load_model = prep_module.Preprocessor._load_model

        def mock_load_model(self: Any) -> None:
            self.nlp = None

        prep_module.Preprocessor._load_model = mock_load_model  # type: ignore[method-assign]

        try:
            # Monkeypatch model check to return False
            with patch.object(parity_check, "_check_model_available", return_value=False):
                report, exit_code = parity_check._generate_parity_report([parity_benefits_heavy_fixture])

            # Assertions on report content
            assert "Parity Report" in report
            assert "parity_benefits_heavy.md" in report
            assert "Status" in report
            assert "v3 Count" in report
            assert "Legacy Count" in report

            # With model unavailable, status should be model-unavailable
            assert "model-unavailable" in report

            # Exit code 0 unless schema violation
            assert exit_code == 0
        finally:
            prep_module.Preprocessor._load_model = original_load_model  # type: ignore[method-assign]

    def test_report_markdown_table_structure(self, parity_benefits_heavy_fixture: Path) -> None:
        """Report contains proper markdown table."""
        from src.tokenization import preprocessor as prep_module

        original_load_model = prep_module.Preprocessor._load_model

        def mock_load_model(self: Any) -> None:
            self.nlp = None

        prep_module.Preprocessor._load_model = mock_load_model  # type: ignore[method-assign]

        try:
            with patch.object(parity_check, "_check_model_available", return_value=False):
                report, _ = parity_check._generate_parity_report([parity_benefits_heavy_fixture])

            # Check markdown table structure
            lines = report.split("\n")
            # Find the table header and separator
            table_start = -1
            for i, line in enumerate(lines):
                if "Fixture" in line and "Status" in line:
                    table_start = i
                    break

            assert table_start >= 0, "Table header not found"
            # Next line should be separator (|---|---|...)
            separator_line = lines[table_start + 1]
            assert separator_line.startswith("|")
            assert separator_line.endswith("|")
            assert "-" in separator_line
        finally:
            prep_module.Preprocessor._load_model = original_load_model  # type: ignore[method-assign]

    def test_report_output_file(self, parity_benefits_heavy_fixture: Path, tmp_path: Path) -> None:
        """Report can be written to file."""
        from src.tokenization import preprocessor as prep_module

        original_load_model = prep_module.Preprocessor._load_model

        def mock_load_model(self: Any) -> None:
            self.nlp = None

        prep_module.Preprocessor._load_model = mock_load_model  # type: ignore[method-assign]

        try:
            with patch.object(parity_check, "_check_model_available", return_value=False):
                report, exit_code = parity_check._generate_parity_report([parity_benefits_heavy_fixture])

            # Write to temp file
            output_file = tmp_path / "test_report.md"
            output_file.write_text(report, encoding="utf-8")

            assert output_file.exists()
            # Exact check: file has content and matches report
            assert output_file.read_text() == report
        finally:
            prep_module.Preprocessor._load_model = original_load_model  # type: ignore[method-assign]


class TestMain:
    """Test main entry point."""

    def test_main_with_output_file(self, parity_benefits_heavy_fixture: Path, tmp_path: Path, capsys: Any) -> None:
        """Main function with --output flag."""
        from src.tokenization import preprocessor as prep_module

        original_load_model = prep_module.Preprocessor._load_model

        def mock_load_model(self: Any) -> None:
            self.nlp = None

        prep_module.Preprocessor._load_model = mock_load_model  # type: ignore[method-assign]

        try:
            output_file = tmp_path / "parity_report.md"

            with patch.object(parity_check, "_check_model_available", return_value=False):
                exit_code = parity_check.main(
                    [
                        "--output",
                        str(output_file),
                        "--fixtures",
                        str(parity_benefits_heavy_fixture),
                    ]
                )

            # Check exit code
            assert exit_code == 0

            # Check output file was created
            assert output_file.exists()
            content = output_file.read_text()
            assert "Parity Report" in content

            # Check stderr message
            captured = capsys.readouterr()
            assert "Report written to" in captured.err
        finally:
            prep_module.Preprocessor._load_model = original_load_model  # type: ignore[method-assign]

    def test_main_stdout_output(self, parity_benefits_heavy_fixture: Path, capsys: Any) -> None:
        """Main function outputs to stdout when no --output."""
        from src.tokenization import preprocessor as prep_module

        original_load_model = prep_module.Preprocessor._load_model

        def mock_load_model(self: Any) -> None:
            self.nlp = None

        prep_module.Preprocessor._load_model = mock_load_model  # type: ignore[method-assign]

        try:
            with patch.object(parity_check, "_check_model_available", return_value=False):
                exit_code = parity_check.main(["--fixtures", str(parity_benefits_heavy_fixture)])

            captured = capsys.readouterr()
            # Report should be in stdout
            assert "Parity Report" in captured.out
            assert exit_code == 0
        finally:
            prep_module.Preprocessor._load_model = original_load_model  # type: ignore[method-assign]

    def test_main_missing_fixture(self) -> None:
        """Main returns error code for missing fixture."""
        exit_code = parity_check.main(["--fixtures", "/nonexistent/path/fixture.md"])
        assert exit_code == 2
