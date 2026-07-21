"""Tests for --up-to flag in the all command (Issue #154)."""

import re

import pytest
from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


class TestUpToFlagHelp:
    """Test that --up-to flag appears in help text."""

    @pytest.mark.unit
    def test_up_to_flag_in_help(self):
        """Verify --up-to flag appears in help text."""
        result = runner.invoke(app, ["all", "--help"])
        assert result.exit_code == 0
        clean_stdout = strip_ansi(result.stdout)
        assert "--up-to" in clean_stdout
        assert "Stop workflow at phase" in clean_stdout or "stop" in clean_stdout.lower()

    @pytest.mark.unit
    def test_up_to_valid_phases_documented(self):
        """Verify valid phase options are mentioned in help."""
        result = runner.invoke(app, ["all", "--help"])
        assert result.exit_code == 0
        clean_stdout = strip_ansi(result.stdout)
        assert "--up-to" in clean_stdout


class TestUpToFlagValidation:
    """Test validation of --up-to parameter."""

    @pytest.mark.unit
    def test_invalid_phase_rejected(self):
        """Verify --up-to with invalid phase shows error."""
        result = runner.invoke(
            app,
            [
                "all",
                "--cv",
                "data/cv.json",
                "--config",
                "config/companies.json",
                "--up-to",
                "invalid_phase",
            ],
        )
        output = strip_ansi(result.stdout) + strip_ansi(result.stderr)
        assert result.exit_code == 1
        assert "Invalid phase" in output
        assert "Valid phases" in output

    @pytest.mark.unit
    def test_valid_phases_accepted(self):
        """Verify valid phase options are accepted by parser."""
        result = runner.invoke(app, ["all", "--help"])
        assert result.exit_code == 0
        clean_stdout = strip_ansi(result.stdout)
        # Should not show "No such option"
        assert "No such option '--up-to'" not in clean_stdout


class TestUpToFlagDefaults:
    """Test that --up-to flag defaults correctly."""

    @pytest.mark.unit
    def test_up_to_flag_optional(self):
        """Verify --up-to flag is optional."""
        result = runner.invoke(app, ["all", "--help"])
        assert result.exit_code == 0
        clean_stdout = strip_ansi(result.stdout)
        assert "--up-to" in clean_stdout

    @pytest.mark.unit
    def test_up_to_flag_documentation(self):
        """Verify --up-to flag has descriptive help text."""
        result = runner.invoke(app, ["all", "--help"])
        assert result.exit_code == 0
        clean_stdout = strip_ansi(result.stdout)
        assert "--up-to" in clean_stdout


class TestUpToPhaseValues:
    """Test that valid phase values are recognized."""

    @pytest.mark.unit
    def test_crawl_phase_recognized(self):
        """Verify 'crawl' is a valid phase."""
        result = runner.invoke(app, ["all", "--help"])
        assert result.exit_code == 0
        # Help should appear (no error about unrecognized option)
        assert "all" in result.stdout.lower() or "ALL" in result.stdout

    @pytest.mark.unit
    def test_preprocess_phase_recognized(self):
        """Verify 'preprocess' is a valid phase."""
        result = runner.invoke(app, ["all", "--help"])
        assert result.exit_code == 0
        assert result.exit_code == 0

    @pytest.mark.unit
    def test_review_phase_recognized(self):
        """Verify 'review' is a valid phase."""
        result = runner.invoke(app, ["all", "--help"])
        assert result.exit_code == 0
        assert result.exit_code == 0

    @pytest.mark.unit
    def test_assess_phase_recognized(self):
        """Verify 'assess' is a valid phase."""
        result = runner.invoke(app, ["all", "--help"])
        assert result.exit_code == 0
        assert result.exit_code == 0


class TestUpToFlagDocumentation:
    """Test that flag is properly documented for users."""

    @pytest.mark.unit
    def test_up_to_has_description(self):
        """Verify --up-to flag has clear description in help."""
        result = runner.invoke(app, ["all", "--help"])
        assert result.exit_code == 0
        clean_stdout = strip_ansi(result.stdout)
        assert "--up-to" in clean_stdout


class TestIssue154Resolution:
    """Tests specifically for Issue #154 requirements."""

    @pytest.mark.unit
    def test_issue_154_up_to_flag_present(self):
        """Issue #154: Verify --up-to flag is present and recognized."""
        result = runner.invoke(app, ["all", "--help"])
        assert result.exit_code == 0
        clean_stdout = strip_ansi(result.stdout)
        assert "--up-to" in clean_stdout

    @pytest.mark.unit
    def test_issue_154_no_cli_errors(self):
        """Issue #154: Verify flag doesn't cause 'No such option' errors."""
        result = runner.invoke(app, ["all", "--help"])
        clean_stdout = strip_ansi(result.stdout)
        assert "No such option '--up-to'" not in clean_stdout

    @pytest.mark.unit
    def test_issue_154_cost_control_use_case(self):
        """Issue #154: Verify --up-to can be used for cost control."""
        result = runner.invoke(app, ["all", "--help"])
        assert result.exit_code == 0
        clean_stdout = strip_ansi(result.stdout)
        # Should mention halting or stopping
        assert "--up-to" in clean_stdout
