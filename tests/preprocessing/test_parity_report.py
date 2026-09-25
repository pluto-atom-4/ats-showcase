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
assert _spec is not None, "Failed to load spec for parity_check.py"
assert _spec.loader is not None, "spec.loader is None for parity_check.py"

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
        assert text.startswith("Data Engineer Role")
        assert "## Requirements" in text

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
            count, sections, req_by_section, avg_conf, result = parity_check._extract_v3_metrics(text)

            # Exact assertions for parity_benefits_heavy.md
            assert count == 5
            assert sections == ["SECTION_REQUIREMENTS"]
            assert avg_conf == pytest.approx(1.0, abs=0.01)
            assert req_by_section == {"SECTION_REQUIREMENTS": 5}

            # Benefits/Compensation should NOT be in requirements_by_section
            # (filtered by SKIP_SECTIONS in v3 extraction)
            assert "benefits" not in req_by_section
            assert "compensation" not in req_by_section

            # Result should be valid SectionedResult
            assert result is not None
            assert result.schema_version == "3.0"

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
            count, sections, req_by_section, avg_conf, result = parity_check._extract_v3_metrics(text)

            # Exact assertions for parity_no_headers.md
            assert count == 0
            assert sections == []
            assert req_by_section == {}
            assert avg_conf == 0.0
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
            count, sections, req_by_section, avg_conf, result = parity_check._extract_v3_metrics("")
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
            count, sections, req_by_section, avg_conf, result = parity_check._extract_v3_metrics(text)

            # Exact assertions (same as monkeypatched test)
            assert count == 5
            assert sections == ["SECTION_REQUIREMENTS"]
            assert avg_conf == pytest.approx(1.0, abs=0.01)
            assert req_by_section == {"SECTION_REQUIREMENTS": 5}
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


class TestValidateSchemaResult:
    """Test schema validation against real SectionedResult."""

    def test_valid_schema_none_result(self) -> None:
        """None result is valid (empty extraction)."""
        assert parity_check._validate_schema_result(None) is True

    def test_valid_schema_with_requirements(self, parity_benefits_heavy_fixture: Path) -> None:
        """Real SectionedResult from valid extraction passes validation."""
        from src.tokenization import preprocessor as prep_module

        original_load_model = prep_module.Preprocessor._load_model

        def mock_load_model(self: Any) -> None:
            self.nlp = None

        prep_module.Preprocessor._load_model = mock_load_model  # type: ignore[method-assign]

        try:
            text = parity_check._load_fixture(parity_benefits_heavy_fixture)
            assert text is not None

            _, _, _, _, result = parity_check._extract_v3_metrics(text)
            assert result is not None
            # Real result should pass validation
            assert parity_check._validate_schema_result(result) is True
        finally:
            prep_module.Preprocessor._load_model = original_load_model  # type: ignore[method-assign]

    def test_invalid_schema_version(self) -> None:
        """Invalid schema_version fails validation."""
        # Create mock result with wrong version
        mock_result = MagicMock()
        mock_result.schema_version = "2.0"  # Wrong version
        mock_result.requirements = []
        mock_result.requirements_by_section = {}

        assert parity_check._validate_schema_result(mock_result) is False

    def test_invalid_confidence_too_high(self) -> None:
        """Confidence > 1.0 fails validation."""
        mock_req = MagicMock()
        mock_req.text = "5+ years Python"
        mock_req.final_confidence = 1.5  # Out of range

        mock_result = MagicMock()
        mock_result.schema_version = "3.0"
        mock_result.requirements = [mock_req]
        mock_result.requirements_by_section = {"SECTION_REQUIREMENTS": 1}

        assert parity_check._validate_schema_result(mock_result) is False

    def test_invalid_confidence_negative(self) -> None:
        """Confidence < 0.0 fails validation."""
        mock_req = MagicMock()
        mock_req.text = "5+ years Python"
        mock_req.final_confidence = -0.1  # Out of range

        mock_result = MagicMock()
        mock_result.schema_version = "3.0"
        mock_result.requirements = [mock_req]
        mock_result.requirements_by_section = {"SECTION_REQUIREMENTS": 1}

        assert parity_check._validate_schema_result(mock_result) is False

    def test_count_mismatch(self) -> None:
        """Requirement count != section sum fails validation."""
        mock_req1 = MagicMock()
        mock_req1.text = "req1"
        mock_req1.final_confidence = 0.8
        mock_req2 = MagicMock()
        mock_req2.text = "req2"
        mock_req2.final_confidence = 0.7

        mock_result = MagicMock()
        mock_result.schema_version = "3.0"
        mock_result.requirements = [mock_req1, mock_req2]
        mock_result.requirements_by_section = {"SECTION_REQUIREMENTS": 1}  # Should be 2

        assert parity_check._validate_schema_result(mock_result) is False


class TestNormalizeText:
    """Test text normalization for comparison."""

    def test_normalize_whitespace(self) -> None:
        """Normalize collapses multiple whitespaces."""
        text = "5+   years   Python"
        normalized = parity_check._normalize_text(text)
        assert normalized == "5+ years python"

    def test_normalize_lowercase(self) -> None:
        """Normalize converts to lowercase."""
        text = "5+ Years PYTHON"
        normalized = parity_check._normalize_text(text)
        assert normalized == "5+ years python"

    def test_normalize_tabs_newlines(self) -> None:
        """Normalize handles tabs and newlines."""
        text = "5+\tyears\nPython"
        normalized = parity_check._normalize_text(text)
        assert normalized == "5+ years python"


class TestComputeTextDiff:
    """Test text difference computation."""

    def test_identical_texts(self) -> None:
        """Identical texts have no diff."""
        v3_texts = ["5+ years Python", "Experience with Django"]
        legacy_texts = ["5+ years Python", "Experience with Django"]
        v3_only, legacy_only = parity_check._compute_text_diff(v3_texts, legacy_texts)
        assert v3_only == 0
        assert legacy_only == 0

    def test_v3_only_texts(self) -> None:
        """v3 with extra texts."""
        v3_texts = ["5+ years Python", "Experience with Django", "FastAPI knowledge"]
        legacy_texts = ["5+ years Python", "Experience with Django"]
        v3_only, legacy_only = parity_check._compute_text_diff(v3_texts, legacy_texts)
        assert v3_only == 1
        assert legacy_only == 0

    def test_legacy_only_texts(self) -> None:
        """Legacy with extra texts."""
        v3_texts = ["5+ years Python", "Experience with Django"]
        legacy_texts = ["5+ years Python", "Experience with Django", "FastAPI knowledge"]
        v3_only, legacy_only = parity_check._compute_text_diff(v3_texts, legacy_texts)
        assert v3_only == 0
        assert legacy_only == 1

    def test_normalization_in_diff(self) -> None:
        """Text diff uses normalized comparison."""
        v3_texts = ["5+ Years PYTHON", "Experience with Django"]
        legacy_texts = ["5+ years python", "EXPERIENCE WITH DJANGO"]
        v3_only, legacy_only = parity_check._compute_text_diff(v3_texts, legacy_texts)
        # After normalization, they're identical
        assert v3_only == 0
        assert legacy_only == 0


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

            # Exact assertions on report content
            assert "# Parity Report: v3 vs Legacy Preprocessing\n" in report
            expected_row = (
                "| parity_benefits_heavy.md | model-unavailable | 5 | SECTION_REQUIREMENTS | "
                "1.00 | 0 | spaCy model not available; legacy extraction skipped |"
            )
            assert expected_row in report
            assert "- spaCy model `en_core_web_md` available: False\n" in report
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
                if line.startswith("| Fixture | Status | v3 Count"):
                    table_start = i
                    break

            assert table_start >= 0, "Table header not found"
            # Next line should be separator (|---|---|...)
            separator_line = lines[table_start + 1]
            expected_sep = "|---------|--------|----------|-------------|----------------|--------------|-------|"
            assert separator_line == expected_sep
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
            # Exact check: file content matches report exactly
            assert output_file.read_text(encoding="utf-8") == report
        finally:
            prep_module.Preprocessor._load_model = original_load_model  # type: ignore[method-assign]

    def test_report_schema_violation_exit_code(self, parity_benefits_heavy_fixture: Path) -> None:
        """Schema violation sets exit code to 1 (not 0)."""
        from src.tokenization import preprocessor as prep_module

        original_load_model = prep_module.Preprocessor._load_model

        def mock_load_model(self: Any) -> None:
            self.nlp = None

        prep_module.Preprocessor._load_model = mock_load_model  # type: ignore[method-assign]

        try:
            text = parity_check._load_fixture(parity_benefits_heavy_fixture)
            assert text is not None

            # Monkeypatch _validate_schema_result to return False (schema violation)
            with patch.object(parity_check, "_validate_schema_result", return_value=False):
                with patch.object(parity_check, "_check_model_available", return_value=False):
                    report, exit_code = parity_check._generate_parity_report([parity_benefits_heavy_fixture])

            # Schema violation should set exit code to 1
            assert exit_code == 1
        finally:
            prep_module.Preprocessor._load_model = original_load_model  # type: ignore[method-assign]

    def test_report_v3_extraction_exception_exit_code_0(self, tmp_path: Path) -> None:
        """v3 extraction exception sets status=error but exit code stays 0."""
        # Create temporary fixture that will cause extraction to fail
        temp_fixture = tmp_path / "bad_fixture.md"
        temp_fixture.write_text("Some text", encoding="utf-8")

        from src.tokenization import preprocessor as prep_module

        original_load_model = prep_module.Preprocessor._load_model

        def mock_load_model(self: Any) -> None:
            self.nlp = None

        prep_module.Preprocessor._load_model = mock_load_model  # type: ignore[method-assign]

        try:
            # Monkeypatch _extract_v3_metrics to raise exception
            def mock_extract_v3(*args: Any, **kwargs: Any) -> Any:
                raise RuntimeError("Extraction failed")

            with patch.object(parity_check, "_extract_v3_metrics", side_effect=mock_extract_v3):
                with patch.object(parity_check, "_check_model_available", return_value=False):
                    report, exit_code = parity_check._generate_parity_report([temp_fixture])

            # Exception should NOT set exit code to 1; exit code should be 0
            assert exit_code == 0
            # Report should mention error
            assert "| error | Error |" in report
            assert "Extraction failed" in report
        finally:
            prep_module.Preprocessor._load_model = original_load_model  # type: ignore[method-assign]

    def test_report_v3_only_legacy_only_count(self, parity_benefits_heavy_fixture: Path) -> None:
        """Report includes v3-only/legacy-only text counts when legacy runs."""
        # Mock v3 and legacy to return controlled texts for diff testing
        v3_texts = ["Python", "SQL", "Spark", "Docker", "v3-unique"]
        legacy_texts = ["Python", "SQL", "Spark", "Docker", "legacy-unique"]

        def mock_v3_extract(text: str) -> tuple[int, list[str], dict[str, int], float, Any]:
            # Return real SectionedResult mock with v3_texts
            result = MagicMock()
            result.schema_version = "3.0"
            result.requirements = [MagicMock(text=t, final_confidence=0.9) for t in v3_texts]
            result.requirements_by_section = {"SECTION_REQUIREMENTS": len(v3_texts)}
            return len(v3_texts), ["SECTION_REQUIREMENTS"], {"SECTION_REQUIREMENTS": len(v3_texts)}, 0.9, result

        def mock_legacy_extract(text: str, model_name: str = "en_core_web_md") -> tuple[int, list[str], Optional[str]]:
            return len(legacy_texts), legacy_texts, None

        with patch.object(parity_check, "_extract_v3_metrics", side_effect=mock_v3_extract):
            with patch.object(parity_check, "_extract_legacy_metrics", side_effect=mock_legacy_extract):
                with patch.object(parity_check, "_check_model_available", return_value=True):
                    report, exit_code = parity_check._generate_parity_report([parity_benefits_heavy_fixture])

        # Report should mention text diff counts
        assert "v3-only: 1" in report
        assert "legacy-only: 1" in report
        assert exit_code == 0


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
            content = output_file.read_text(encoding="utf-8")
            # Exact check: file starts with exact report header
            assert content.startswith("# Parity Report: v3 vs Legacy Preprocessing\n")

            # Check stderr message exactly
            captured = capsys.readouterr()
            assert f"Report written to {output_file}" in captured.err
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
            # Report should start with exact header in stdout
            assert captured.out.startswith("# Parity Report: v3 vs Legacy Preprocessing\n")
            assert exit_code == 0
        finally:
            prep_module.Preprocessor._load_model = original_load_model  # type: ignore[method-assign]

    def test_main_missing_fixture(self) -> None:
        """Main returns error code for missing fixture."""
        exit_code = parity_check.main(["--fixtures", "/nonexistent/path/fixture.md"])
        assert exit_code == 2
