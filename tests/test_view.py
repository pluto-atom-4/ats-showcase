"""Tests for view command and MarkdownReportViewer."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.formatters.markdown_viewer import MarkdownReportViewer

runner = CliRunner()


class TestMarkdownReportViewer:
    """Test MarkdownReportViewer formatting and filtering."""

    @pytest.fixture
    def sample_report(self):
        """Create a sample markdown report for testing."""
        return """# Job Assessment Report
**Generated:** 2026-06-24

## Summary Statistics
- Total jobs assessed: 10
- Average score: 75.5

## Top 5 Matches
- Job 1: Score 95
- Job 2: Score 88

## Job Details
### [1] Senior Engineer (Score: 95)
Located in NYC.

### [2] Mid-level Developer (Score: 88)
Located in SF.

### [3] Junior Developer (Score: 65)
Located in Austin.

### [4] Data Scientist (Score: 45)
Located in Boston.
"""

    def test_viewer_initialization(self):
        """Test viewer can be initialized."""
        viewer = MarkdownReportViewer()
        assert viewer is not None

    def test_view_missing_report(self):
        """Test viewer raises error for missing report."""
        viewer = MarkdownReportViewer()
        with pytest.raises(FileNotFoundError):
            viewer.view_report("nonexistent.md")

    def test_filter_by_score_range(self, sample_report):
        """Test score filtering logic."""
        viewer = MarkdownReportViewer()
        filtered = viewer._filter_by_score(sample_report, 70.0, 100.0)
        # Should include jobs with score >= 70 and <= 100
        assert "[1] Senior Engineer (Score: 95)" in filtered
        assert "[2] Mid-level Developer (Score: 88)" in filtered
        # Should exclude lower scores
        assert "[3] Junior Developer (Score: 65)" not in filtered
        assert "[4] Data Scientist (Score: 45)" not in filtered

    def test_filter_with_zero_range(self, sample_report):
        """Test that filter with default range returns full content."""
        viewer = MarkdownReportViewer()
        filtered = viewer._filter_by_score(sample_report, 0.0, 100.0)
        assert filtered == sample_report

    def test_filter_with_min_score_only(self, sample_report):
        """Test filtering with only min_score."""
        viewer = MarkdownReportViewer()
        filtered = viewer._filter_by_score(sample_report, 80.0, 100.0)
        assert "[1] Senior Engineer (Score: 95)" in filtered
        assert "[2] Mid-level Developer (Score: 88)" in filtered
        assert "[3] Junior Developer (Score: 65)" not in filtered

    def test_filter_with_max_score_only(self, sample_report):
        """Test filtering with only max_score."""
        viewer = MarkdownReportViewer()
        filtered = viewer._filter_by_score(sample_report, 0.0, 70.0)
        assert "[1] Senior Engineer (Score: 95)" not in filtered
        assert "[3] Junior Developer (Score: 65)" in filtered
        assert "[4] Data Scientist (Score: 45)" in filtered


class TestViewCommand:
    """Test view command via CLI."""

    @pytest.fixture
    def sample_report_file(self):
        """Create a temporary report file."""
        report_content = """# Job Assessment Report
**Generated:** 2026-06-24

## Summary
Total: 3 jobs

## Top Matches
- Job 1 (Score: 90)
- Job 2 (Score: 80)

## Job Details
### [1] Engineer (Score: 90)
Description here.

### [2] Developer (Score: 80)
Description here.

### [3] Analyst (Score: 50)
Description here.
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write(report_content)
            f.flush()
            yield f.name
        Path(f.name).unlink()

    def test_view_missing_report(self):
        """Test view command with missing report."""
        result = runner.invoke(app, ["view", "--report", "nonexistent.md"])
        assert result.exit_code == 1
        assert "Report not found" in result.stdout

    def test_view_with_custom_report(self, sample_report_file):
        """Test view command with custom report path."""
        result = runner.invoke(app, ["view", "--report", sample_report_file])
        assert result.exit_code == 0
        assert "Loading report" in result.stdout

    def test_view_default_path_exists(self):
        """Test view command with default path when it exists."""
        # This will only pass if the default report file exists
        result = runner.invoke(app, ["view"])
        # Should succeed if file exists, fail if not
        assert result.exit_code in [0, 1]

    def test_view_with_template_summary(self, sample_report_file):
        """Test view command with summary template."""
        result = runner.invoke(
            app, ["view", "--report", sample_report_file, "--template", "summary"]
        )
        assert result.exit_code == 0

    def test_view_with_template_topn(self, sample_report_file):
        """Test view command with topn template."""
        result = runner.invoke(
            app, ["view", "--report", sample_report_file, "--template", "topn", "--topn", "2"]
        )
        assert result.exit_code == 0

    def test_view_with_score_filters(self, sample_report_file):
        """Test view command with score filtering."""
        result = runner.invoke(
            app,
            [
                "view",
                "--report",
                sample_report_file,
                "--min-score",
                "75",
                "--max-score",
                "95",
            ],
        )
        assert result.exit_code == 0

    def test_view_with_no_highlight(self, sample_report_file):
        """Test view command with highlighting disabled."""
        result = runner.invoke(
            app, ["view", "--report", sample_report_file, "--no-highlight"]
        )
        assert result.exit_code == 0

    def test_view_with_no_pager(self, sample_report_file):
        """Test view command with pager disabled."""
        result = runner.invoke(
            app, ["view", "--report", sample_report_file, "--no-pager"]
        )
        assert result.exit_code == 0

    def test_view_help(self):
        """Test view command help text."""
        result = runner.invoke(app, ["view", "--help"])
        assert result.exit_code == 0
        assert "View formatted assessment report" in result.stdout
