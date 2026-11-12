"""CLI export command tests.

Tests for Task 9: Export command (markdown report generation).
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli import app
from storage.assessment_store import AssessmentStore

runner = CliRunner()


@pytest.fixture
def temp_db() -> Generator[str, None, None]:
    """Create temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def store_with_sample_assessments(temp_db: str) -> AssessmentStore:
    """Create store with sample assessments."""
    store = AssessmentStore(temp_db)

    assessments = [
        {
            "job_id": "job1",
            "title": "Senior Python Developer",
            "company": "TechCorp",
            "location": "Remote",
            "overall_score": 92,
            "tech_score": 95,
            "seniority_score": 88,
            "location_score": 80,
            "recommendations": ["Learn Kubernetes", "Master Docker"],
            "summary": "Excellent fit for senior role",
            "tokens_used": 650,
            "actual_cost": 0.002,
            "input_tokens": 600,
            "output_tokens": 50,
        },
        {
            "job_id": "job2",
            "title": "ML Engineer",
            "company": "DataInc",
            "location": "San Francisco",
            "overall_score": 78,
            "tech_score": 85,
            "seniority_score": 75,
            "location_score": 60,
            "recommendations": ["Study PyTorch"],
            "summary": "Good fit, some gaps",
            "tokens_used": 670,
            "actual_cost": 0.002,
            "input_tokens": 620,
            "output_tokens": 50,
        },
        {
            "job_id": "job3",
            "title": "Frontend Developer",
            "company": "WebDev Inc",
            "location": "Austin",
            "overall_score": 65,
            "tech_score": 70,
            "seniority_score": 60,
            "location_score": 50,
            "recommendations": [],
            "summary": "Moderate fit",
            "tokens_used": 640,
            "actual_cost": 0.002,
            "input_tokens": 590,
            "output_tokens": 50,
        },
    ]

    for assessment in assessments:
        store.save_assessment(
            job_id=assessment["job_id"],
            title=assessment["title"],
            company=assessment["company"],
            location=assessment["location"],
            overall_score=assessment["overall_score"],
            tech_score=assessment["tech_score"],
            seniority_score=assessment["seniority_score"],
            location_score=assessment["location_score"],
            recommendations=assessment["recommendations"],
            summary=assessment["summary"],
            tokens_used=assessment["tokens_used"],
            actual_cost=assessment["actual_cost"],
            input_tokens=assessment["input_tokens"],
            output_tokens=assessment["output_tokens"],
        )

    return store


def test_export_basic(store_with_sample_assessments: AssessmentStore) -> None:
    """Test basic export with default options."""
    with patch("src.cli.AssessmentStore") as mock_store_cls:
        mock_store_cls.return_value = store_with_sample_assessments

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.md"
            result = runner.invoke(app, ["export", "--output", str(output_path)])

            assert result.exit_code == 0
            assert "Exported to" in result.stdout
            assert output_path.exists()

            report_content = output_path.read_text()
            assert "# Job Assessment Report" in report_content
            assert "Total Assessed:" in report_content
            assert "3" in report_content


def test_export_with_min_score(store_with_sample_assessments: AssessmentStore) -> None:
    """Test export with score filter."""
    with patch("src.cli.AssessmentStore") as mock_store_cls:
        mock_store_cls.return_value = store_with_sample_assessments

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "filtered.md"
            result = runner.invoke(
                app,
                ["export", "--output", str(output_path), "--min-score", "75"],
            )

            assert result.exit_code == 0
            assert "Filtered:" in result.stdout

            report_content = output_path.read_text()
            assert "TechCorp" in report_content
            assert "DataInc" in report_content
            assert "WebDev Inc" not in report_content


def test_export_with_max_score(store_with_sample_assessments: AssessmentStore) -> None:
    """Test export with max score filter."""
    with patch("src.cli.AssessmentStore") as mock_store_cls:
        mock_store_cls.return_value = store_with_sample_assessments

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "filtered.md"
            result = runner.invoke(
                app,
                ["export", "--output", str(output_path), "--max-score", "80"],
            )

            assert result.exit_code == 0

            report_content = output_path.read_text()
            assert "TechCorp" not in report_content
            assert "DataInc" in report_content
            assert "WebDev Inc" in report_content


def test_export_sort_by_company(store_with_sample_assessments: AssessmentStore) -> None:
    """Test export with company sorting."""
    with patch("src.cli.AssessmentStore") as mock_store_cls:
        mock_store_cls.return_value = store_with_sample_assessments

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "sorted.md"
            result = runner.invoke(
                app,
                ["export", "--output", str(output_path), "--sort-by", "company"],
            )

            assert result.exit_code == 0
            assert output_path.exists()


def test_export_template_summary(store_with_sample_assessments: AssessmentStore) -> None:
    """Test export with summary template."""
    with patch("src.cli.AssessmentStore") as mock_store_cls:
        mock_store_cls.return_value = store_with_sample_assessments

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "summary.md"
            result = runner.invoke(
                app,
                ["export", "--output", str(output_path), "--template", "summary"],
            )

            assert result.exit_code == 0
            assert "summary" in result.stdout.lower()

            report_content = output_path.read_text()
            assert "## Top 10 Matches" in report_content


def test_export_no_assessments() -> None:
    """Test export when no assessments exist."""
    with patch("src.cli.AssessmentStore") as mock_store_cls:
        mock_store = MagicMock()
        mock_store.count_assessments.return_value = 0
        mock_store_cls.return_value = mock_store

        result = runner.invoke(app, ["export"])

        assert result.exit_code == 1
        output = result.stdout + (result.stderr or "")
        assert "No assessments found" in output or "No assessments" in output


def test_export_invalid_min_score() -> None:
    """Test export with invalid min score."""
    result = runner.invoke(app, ["export", "--min-score", "-1"])

    assert result.exit_code == 1
    output = result.stdout + (result.stderr or "")
    assert "min_score" in output.lower() and "0-100" in output


def test_export_invalid_max_score() -> None:
    """Test export with invalid max score."""
    result = runner.invoke(app, ["export", "--max-score", "101"])

    assert result.exit_code == 1
    output = result.stdout + (result.stderr or "")
    assert "max_score" in output.lower() and "0-100" in output


def test_export_min_greater_than_max() -> None:
    """Test export with min > max."""
    result = runner.invoke(
        app,
        ["export", "--min-score", "75", "--max-score", "50"],
    )

    assert result.exit_code == 1
    output = result.stdout + (result.stderr or "")
    assert "min_score" in output.lower() and "max_score" in output.lower()


def test_export_invalid_sort_by() -> None:
    """Test export with invalid sort_by option."""
    with patch("src.cli.AssessmentStore") as mock_store_cls:
        mock_store = MagicMock()
        mock_store.count_assessments.return_value = 1
        mock_store_cls.return_value = mock_store

        result = runner.invoke(
            app,
            ["export", "--sort-by", "invalid"],
        )

        assert result.exit_code in (1, 2)


def test_export_invalid_template() -> None:
    """Test export with invalid template."""
    with patch("src.cli.AssessmentStore") as mock_store_cls:
        mock_store = MagicMock()
        mock_store.count_assessments.return_value = 1
        mock_store_cls.return_value = mock_store

        result = runner.invoke(
            app,
            ["export", "--template", "html"],
        )

        assert result.exit_code in (1, 2)


def test_export_file_creation(store_with_sample_assessments: AssessmentStore) -> None:
    """Test that export creates output file."""
    with patch("src.cli.AssessmentStore") as mock_store_cls:
        mock_store_cls.return_value = store_with_sample_assessments

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "subdir" / "report.md"
            result = runner.invoke(app, ["export", "--output", str(output_path)])

            assert result.exit_code == 0
            assert output_path.exists()
            assert output_path.stat().st_size > 0


def test_export_markdown_formatting(
    store_with_sample_assessments: AssessmentStore,
) -> None:
    """Test that export generates valid markdown."""
    with patch("src.cli.AssessmentStore") as mock_store_cls:
        mock_store_cls.return_value = store_with_sample_assessments

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.md"
            result = runner.invoke(app, ["export", "--output", str(output_path)])

            assert result.exit_code == 0

            report_content = output_path.read_text()
            assert report_content.startswith("# ")
            assert "##" in report_content
            assert report_content.count("```") % 2 == 0
            assert "---" in report_content


def test_export_includes_top_matches(
    store_with_sample_assessments: AssessmentStore,
) -> None:
    """Test that export includes top matches section."""
    with patch("src.cli.AssessmentStore") as mock_store_cls:
        mock_store_cls.return_value = store_with_sample_assessments

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.md"
            result = runner.invoke(app, ["export", "--output", str(output_path)])

            assert result.exit_code == 0

            report_content = output_path.read_text()
            assert "## Top" in report_content
            assert "TechCorp" in report_content


def test_export_includes_analytics(
    store_with_sample_assessments: AssessmentStore,
) -> None:
    """Test that export includes analytics section."""
    with patch("src.cli.AssessmentStore") as mock_store_cls:
        mock_store_cls.return_value = store_with_sample_assessments

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.md"
            result = runner.invoke(
                app,
                ["export", "--output", str(output_path), "--include-stats"],
            )

            assert result.exit_code == 0

            report_content = output_path.read_text()
            assert "## Analytics" in report_content


def test_export_excludes_recommendations(
    store_with_sample_assessments: AssessmentStore,
) -> None:
    """Test export without recommendations."""
    with patch("src.cli.AssessmentStore") as mock_store_cls:
        mock_store_cls.return_value = store_with_sample_assessments

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.md"
            result = runner.invoke(
                app,
                ["export", "--output", str(output_path), "--no-include-recommendations"],
            )

            assert result.exit_code in (0, 2)


def test_export_from_date(store_with_sample_assessments: AssessmentStore) -> None:
    """Test export with from_date filter."""
    with patch("src.cli.AssessmentStore") as mock_store_cls:
        mock_store_cls.return_value = store_with_sample_assessments

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.md"
            result = runner.invoke(
                app,
                ["export", "--output", str(output_path), "--from-date", "2020-01-01"],
            )

            assert result.exit_code == 0

            report_content = output_path.read_text()
            assert "Date:" in report_content


def test_export_to_date(store_with_sample_assessments: AssessmentStore) -> None:
    """Test export with to_date filter."""
    with patch("src.cli.AssessmentStore") as mock_store_cls:
        mock_store_cls.return_value = store_with_sample_assessments

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.md"
            result = runner.invoke(
                app,
                ["export", "--output", str(output_path), "--to-date", "2099-12-31"],
            )

            assert result.exit_code == 0

            report_content = output_path.read_text()
            assert "Date:" in report_content


def test_export_invalid_date_format() -> None:
    """Test export with invalid date format."""
    with patch("src.cli.AssessmentStore") as mock_store_cls:
        mock_store = MagicMock()
        mock_store.count_assessments.return_value = 1
        mock_store_cls.return_value = mock_store

        result = runner.invoke(
            app,
            ["export", "--from-date", "05-15-2026"],
        )

        assert result.exit_code == 1
        output = result.stdout + (result.stderr or "")
        assert "Invalid date format" in output or "date" in output.lower()


def test_export_output_summary(store_with_sample_assessments: AssessmentStore) -> None:
    """Test that export shows summary in output."""
    with patch("src.cli.AssessmentStore") as mock_store_cls:
        mock_store_cls.return_value = store_with_sample_assessments

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.md"
            result = runner.invoke(app, ["export", "--output", str(output_path)])

            assert result.exit_code == 0
            assert "✅ Exported to" in result.stdout
            assert "Filtered:" in result.stdout
            assert "File size:" in result.stdout
            assert "Template:" in result.stdout
