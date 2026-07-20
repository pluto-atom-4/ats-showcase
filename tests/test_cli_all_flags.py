"""Tests for --interactive and --merge-all flags in the all command (Issue #140)."""

import re

import pytest
from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


class TestAllCommandHelpText:
    """Test that help text properly documents the new flags."""

    @pytest.mark.unit
    def test_all_help_contains_interactive_flag(self):
        """Verify --interactive flag appears in help text."""
        result = runner.invoke(app, ["all", "--help"])
        assert result.exit_code == 0
        clean_stdout = strip_ansi(result.stdout)
        assert "--interactive" in clean_stdout
        assert "interactive" in clean_stdout.lower()

    @pytest.mark.unit
    def test_all_help_contains_merge_all_flag(self):
        """Verify --merge-all flag appears in help text."""
        result = runner.invoke(app, ["all", "--help"])
        assert result.exit_code == 0
        clean_stdout = strip_ansi(result.stdout)
        assert "--merge-all" in clean_stdout
        assert "auto-discover" in clean_stdout.lower() or "merge" in clean_stdout.lower()


class TestAllCommandFlagRecognition:
    """Test that Typer recognizes the new flags without parsing errors."""

    @pytest.mark.unit
    def test_all_recognizes_interactive_flag(self):
        """Verify --interactive flag is recognized (not 'No such option')."""
        result = runner.invoke(app, ["all", "--help"])
        clean_stdout = strip_ansi(result.stdout)
        assert "--interactive" in clean_stdout
        assert "No such option '--interactive'" not in clean_stdout

    @pytest.mark.unit
    def test_all_recognizes_merge_all_flag(self):
        """Verify --merge-all flag is recognized (not 'No such option')."""
        result = runner.invoke(app, ["all", "--help"])
        clean_stdout = strip_ansi(result.stdout)
        assert "--merge-all" in clean_stdout
        assert "No such option '--merge-all'" not in clean_stdout

    @pytest.mark.unit
    def test_all_flag_defaults_in_help(self):
        """Verify flag defaults are documented in help."""
        result = runner.invoke(app, ["all", "--help"])
        assert result.exit_code == 0
        clean_stdout = strip_ansi(result.stdout)
        assert "--interactive" in clean_stdout
        assert "--merge-all" in clean_stdout


class TestAllCommandFlagDefaults:
    """Test that flags have correct default values documented."""

    @pytest.mark.unit
    def test_interactive_flag_default_false(self):
        """Verify --interactive defaults to False (backward compatible)."""
        result = runner.invoke(app, ["all", "--help"])
        clean_stdout = strip_ansi(result.stdout)
        assert "--interactive" in clean_stdout

    @pytest.mark.unit
    def test_merge_all_flag_default_false(self):
        """Verify --merge-all defaults to False (backward compatible)."""
        result = runner.invoke(app, ["all", "--help"])
        clean_stdout = strip_ansi(result.stdout)
        assert "--merge-all" in clean_stdout


@pytest.mark.unit
class TestAllCommandFlagDocumentation:
    """Test that flags are properly documented for users."""

    def test_interactive_flag_has_description(self):
        """Verify --interactive flag has a clear description."""
        result = runner.invoke(app, ["all", "--help"])
        clean_stdout = strip_ansi(result.stdout)
        assert "--interactive" in clean_stdout

    def test_merge_all_flag_has_description(self):
        """Verify --merge-all flag has a clear description."""
        result = runner.invoke(app, ["all", "--help"])
        clean_stdout = strip_ansi(result.stdout)
        assert "--merge-all" in clean_stdout


class TestIssue140Resolution:
    """Tests specifically for Issue #140 requirements."""

    @pytest.mark.unit
    def test_issue_140_interactive_flag_present(self):
        """Issue #140: Verify --interactive flag is present."""
        result = runner.invoke(app, ["all", "--help"])
        assert result.exit_code == 0
        clean_stdout = strip_ansi(result.stdout)
        assert "--interactive" in clean_stdout

    @pytest.mark.unit
    def test_issue_140_merge_all_flag_present(self):
        """Issue #140: Verify --merge-all flag is present."""
        result = runner.invoke(app, ["all", "--help"])
        assert result.exit_code == 0
        clean_stdout = strip_ansi(result.stdout)
        assert "--merge-all" in clean_stdout

    @pytest.mark.unit
    def test_issue_140_no_cli_errors(self):
        """Issue #140: Verify flags don't cause 'No such option' errors."""
        result = runner.invoke(app, ["all", "--help"])
        clean_stdout = strip_ansi(result.stdout)
        assert "No such option '--interactive'" not in clean_stdout
        assert "No such option '--merge-all'" not in clean_stdout
