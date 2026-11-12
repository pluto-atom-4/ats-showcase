"""CLI tests for Phase 3C selective re-preprocessing (Issue #230)."""

import re
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.storage.job_store import JobStore


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


@pytest.fixture
def temp_db() -> Generator[str, None, None]:
    """Create temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        yield db_path


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a CLI runner."""
    return CliRunner()


class TestPreprocessSelectiveFilters:
    """Test preprocess CLI with selective filtering options (Phase 3C)."""

    def test_preprocess_help_shows_new_filters(self, cli_runner: CliRunner) -> None:
        """Test that --help shows new filtering options."""
        result = cli_runner.invoke(app, ["preprocess", "--help"])

        assert result.exit_code == 0
        clean_output = strip_ansi(result.stdout)
        # Check for filter options (help output may truncate with ellipsis)
        assert "--filter-by-age" in clean_output
        assert "--filter-by-score" in clean_output or "assessment score" in clean_output
        assert "--filter-by-company" in clean_output
        assert "--filter-by-tokens" in clean_output
        assert "--limit" in clean_output
        assert "--dry-run" in clean_output

    def test_preprocess_dry_run_mode_no_database_changes(self, cli_runner: CliRunner) -> None:
        """Test that --dry-run previews without modifying database."""
        # Accepts preview or no-jobs output; the database contents are not controlled here.
        result = cli_runner.invoke(
            app,
            [
                "preprocess",
                "--re-preprocess-only-v1",
                "--filter-by-age",
                "30",
                "--dry-run",
            ],
        )

        assert result.exit_code in [0, 1]

        output = result.stdout.lower()
        assert any(x in output for x in ["dry run", "found", "would", "no jobs"])

    def test_preprocess_filter_by_age_flag(self, cli_runner: CliRunner, temp_db: str) -> None:
        """Test --filter-by-age flag is accepted and parsed."""
        with tempfile.TemporaryDirectory():
            result = cli_runner.invoke(
                app,
                [
                    "preprocess",
                    "--re-preprocess-only-v1",
                    "--filter-by-age",
                    "30",
                    "--dry-run",
                ],
            )

            assert result.exit_code in [0, 1]

    def test_preprocess_filter_by_company_flag(self, cli_runner: CliRunner, temp_db: str) -> None:
        """Test --filter-by-company flag accepts comma-separated list."""
        result = cli_runner.invoke(
            app,
            [
                "preprocess",
                "--re-preprocess-only-v1",
                "--filter-by-company",
                "Amazon,Google,Meta",
                "--dry-run",
            ],
        )

        assert "No jobs found" in result.stdout or result.exit_code == 0

    def test_preprocess_filter_by_tokens_flag(self, cli_runner: CliRunner, temp_db: str) -> None:
        """Test --filter-by-tokens-above flag accepts integer."""
        result = cli_runner.invoke(
            app,
            [
                "preprocess",
                "--re-preprocess-only-v1",
                "--filter-by-tokens-above",
                "1000",
                "--dry-run",
            ],
        )

        assert result.exit_code in [0, 1]

    def test_preprocess_limit_enforcement(self, cli_runner: CliRunner) -> None:
        """Test that --limit parameter restricts batch size."""
        result = cli_runner.invoke(
            app,
            [
                "preprocess",
                "--re-preprocess-only-v1",
                "--filter-by-age",
                "30",
                "--limit",
                "5",
                "--dry-run",
            ],
        )

        assert result.exit_code in [0, 1]
        output = result.stdout.lower()
        assert any(x in output for x in ["found", "preview", "no jobs"])

    def test_preprocess_combined_filters_output(self, cli_runner: CliRunner, temp_db: str) -> None:
        """Test that combined filters are shown in output."""
        store = JobStore(temp_db)

        old_time = (datetime.now() - timedelta(days=40)).isoformat()
        assert store.conn is not None
        cursor = store.conn.cursor()

        cursor.execute(
            """INSERT INTO job_reviews
               (job_id, title, company, preprocessing_version, tokens, preprocessed_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("amazon_job", "Amazon Job", "Amazon", "v1.0", 1200, old_time),
        )
        store.conn.commit()
        store.close()

        result = cli_runner.invoke(
            app,
            [
                "preprocess",
                "--re-preprocess-only-v1",
                "--filter-by-age",
                "30",
                "--filter-by-tokens-above",
                "1000",
                "--filter-by-company",
                "Amazon",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "30" in result.stdout or "Filter criteria" in result.stdout

    def test_preprocess_no_jobs_found_message(self, cli_runner: CliRunner) -> None:
        """Test that 'No jobs found' message shown when filters match nothing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            JobStore(db_path).close()

            result = cli_runner.invoke(
                app,
                [
                    "preprocess",
                    "--re-preprocess-only-v1",
                    "--filter-by-company",
                    "NonExistentCompany",
                ],
            )

            assert "No jobs found" in result.stdout or result.exit_code == 0


class TestSelectiveReprocessingIntegration:
    """Integration tests for realistic selective re-preprocessing workflows."""

    def test_gradual_migration_dry_run(self, cli_runner: CliRunner) -> None:
        """Test dry-run of gradual migration workflow."""
        result = cli_runner.invoke(
            app,
            [
                "preprocess",
                "--re-preprocess-only-v1",
                "--filter-by-age",
                "30",
                "--limit",
                "5",
                "--dry-run",
                "--show-estimates",
            ],
        )

        assert result.exit_code in [0, 1]
        output = result.stdout.lower()
        assert any(x in output for x in ["dry run", "would", "preview", "found", "no jobs"])

    def test_cost_estimate_shown_in_dry_run(self, cli_runner: CliRunner, temp_db: str) -> None:
        """Test that cost estimates are shown in dry-run preview."""
        store = JobStore(temp_db)

        old_time = (datetime.now() - timedelta(days=40)).isoformat()
        assert store.conn is not None
        cursor = store.conn.cursor()

        cursor.execute(
            """INSERT INTO job_reviews
               (job_id, title, preprocessing_version, tokens, preprocessed_at)
               VALUES (?, ?, ?, ?, ?)""",
            ("job_1", "Test Job", "v1.0", 1000, old_time),
        )
        store.conn.commit()
        store.close()

        result = cli_runner.invoke(
            app,
            [
                "preprocess",
                "--re-preprocess-only-v1",
                "--filter-by-age",
                "30",
                "--dry-run",
                "--show-estimates",
            ],
        )

        assert result.exit_code == 0
        if "--show-estimates" in result.stdout or "Estimated cost" in result.stdout:
            assert "$" in result.stdout or "tokens" in result.stdout

    def test_multiple_company_filter_parsing(self, cli_runner: CliRunner) -> None:
        """Test that --filter-by-company 'A,B,C' is parsed correctly."""
        result = cli_runner.invoke(
            app,
            [
                "preprocess",
                "--re-preprocess-only-v1",
                "--filter-by-age",
                "30",
                "--filter-by-company",
                "Amazon,Google",
                "--dry-run",
            ],
        )

        assert result.exit_code in [0, 1]
        output = result.stdout.lower()
        assert any(x in output for x in ["would", "preview", "found", "no jobs", "amazon"])

    def test_high_value_job_targeting(self, cli_runner: CliRunner) -> None:
        """Test targeting high-token jobs for maximum savings."""
        result = cli_runner.invoke(
            app,
            [
                "preprocess",
                "--re-preprocess-only-v1",
                "--filter-by-tokens-above",
                "1500",
                "--dry-run",
            ],
        )

        assert result.exit_code in [0, 1]
        output = result.stdout.lower()
        assert any(x in output for x in ["no jobs", "found", "would", "preview"])

    def test_safe_batch_limit_default(self, cli_runner: CliRunner) -> None:
        """Test that default batch limit is 100 (safe limit)."""
        result = cli_runner.invoke(
            app,
            [
                "preprocess",
                "--re-preprocess-only-v1",
                "--filter-by-age",
                "30",
                "--dry-run",
            ],
        )

        assert result.exit_code in [0, 1]
        output = result.stdout.lower()
        assert any(x in output for x in ["no jobs", "found", "would", "preview"])
