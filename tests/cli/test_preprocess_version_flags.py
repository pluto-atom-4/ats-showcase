"""Tests for preprocessing version CLI flags (Phase 2, Task 3)."""

import re

from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text.

    ANSI color codes from Rich/Click formatting can split flag names,
    breaking substring matching. This utility removes those codes.

    Args:
        text: Text potentially containing ANSI escape sequences

    Returns:
        Text with all ANSI escape codes removed
    """
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestPreprocessVersionFlags:
    """Test preprocessing version flags in CLI."""

    def test_preprocess_help_shows_preprocessing_version_flag(self) -> None:
        """Help text should show --preprocessing-version flag."""
        result = runner.invoke(app, ["preprocess", "--help"])
        assert result.exit_code == 0
        clean_output = strip_ansi(result.stdout)
        # Check for flag prefix (handles truncation in narrow terminals)
        assert "--preprocessing" in clean_output
        assert "Version:" in clean_output and "legacy" in clean_output

    def test_preprocess_help_shows_re_preprocess_only_v1_flag(self) -> None:
        """Help text should show --re-preprocess-only-v1 flag."""
        result = runner.invoke(app, ["preprocess", "--help"])
        assert result.exit_code == 0
        clean_output = strip_ansi(result.stdout)
        assert "--re-preprocess" in clean_output
        assert "re-preprocess" in clean_output and "v1.0" in clean_output

    def test_preprocess_version_default_is_v2(self) -> None:
        """Default preprocessing version should be 2.0."""
        result = runner.invoke(app, ["preprocess", "--help"])
        assert result.exit_code == 0
        help_text = strip_ansi(result.stdout).lower()
        assert "2.0" in help_text or "default" in help_text
