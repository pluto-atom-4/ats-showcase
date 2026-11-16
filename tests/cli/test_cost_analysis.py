"""Tests for cost-analysis CLI command (Phase 3A)."""

import json
import re
import tempfile
from pathlib import Path
from typing import Optional

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.config.models import DEFAULT_MODEL, get_model_pricing
from src.storage.assessment_store import AssessmentStore
from src.storage.job_store import JobStore

runner = CliRunner()
HAIKU_MODEL = "claude-haiku-4-5-20251001"


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _printed_rate(output: str, version: str) -> float:
    match = re.search(rf"Token rate {re.escape(version)} \(blended\):\s+\$([\d.]+) per 1M tokens", output)
    assert match is not None, f"no blended rate line for {version}"
    return float(match.group(1))


def _save_assessment(assessments: AssessmentStore, job_id: str, model: Optional[str]) -> None:
    assessments.save_assessment(
        job_id=job_id,
        title="Synthetic Job",
        company="Synthetic Co",
        location=None,
        overall_score=50.0,
        tech_score=50.0,
        seniority_score=50.0,
        location_score=50.0,
        recommendations=[],
        summary="SYNTHETIC: assessment row for cost-analysis rate tests",
        tokens_used=0,
        actual_cost=0.0,
        model=model,
    )


class TestCostAnalysisCommand:
    """Test cost-analysis CLI command."""

    def test_cost_analysis_help(self) -> None:
        """Test cost-analysis command help."""
        result = runner.invoke(app, ["cost-analysis", "--help"])
        assert result.exit_code == 0
        clean_output = strip_ansi(result.stdout)
        assert "cost-analysis" in clean_output or "Cost" in clean_output
        assert "Phase 3A" in clean_output or "preprocessing" in clean_output

    def test_cost_analysis_empty_database(self) -> None:
        """Test cost-analysis on empty database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")

            result = runner.invoke(app, ["cost-analysis", "--db", db_path])

            assert result.exit_code == 0
            clean_output = strip_ansi(result.stdout)
            assert "Cost Analysis" in clean_output
            assert "v1.0" in clean_output or "0" in clean_output

    def test_cost_analysis_with_jobs(self) -> None:
        """Test cost-analysis command with actual jobs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")

            store = JobStore(db_path)
            store.add_job(
                job_id="job_1",
                title="Python Developer",
                company="Tech Corp",
                preprocessing_version="v1.0",
                tokens=1000,
                estimated_cost=0.003,
            )
            store.add_job(
                job_id="job_2",
                title="Senior Developer",
                company="Tech Corp",
                preprocessing_version="v2.0",
                tokens=650,
                estimated_cost=0.00195,
            )
            store.close()

            result = runner.invoke(app, ["cost-analysis", "--db", db_path])

            assert result.exit_code == 0
            clean_output = strip_ansi(result.stdout)
            assert "Cost Analysis" in clean_output
            assert "v1.0" in clean_output
            assert "v2.0" in clean_output
            assert "1" in clean_output

    def test_cost_analysis_json_format(self) -> None:
        """Test cost-analysis command with JSON output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")

            store = JobStore(db_path)
            store.add_job(
                job_id="job_1",
                title="Python Developer",
                company="Tech Corp",
                preprocessing_version="v1.0",
                tokens=1000,
            )
            store.add_job(
                job_id="job_2",
                title="Senior Developer",
                company="Tech Corp",
                preprocessing_version="v2.0",
                tokens=650,
            )
            store.close()

            result = runner.invoke(app, ["cost-analysis", "--db", db_path, "--format", "json"])

            assert result.exit_code == 0
            output = result.stdout.strip()
            json_start = output.find("{")
            if json_start >= 0:
                output = output[json_start:]
            output_data = json.loads(output)
            assert output_data["total_jobs_v1_0"] == 1
            assert output_data["total_jobs_v2_0"] == 1
            assert output_data["total_tokens_v1_0"] == 1000
            assert output_data["total_tokens_v2_0"] == 650

    def test_cost_analysis_csv_format(self) -> None:
        """Test cost-analysis command with CSV output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")

            store = JobStore(db_path)
            store.add_job(
                job_id="job_1",
                title="Python Developer",
                company="Tech Corp",
                preprocessing_version="v1.0",
                tokens=1000,
            )
            store.close()

            result = runner.invoke(app, ["cost-analysis", "--db", db_path, "--format", "csv"])

            assert result.exit_code == 0
            clean_output = strip_ansi(result.stdout.strip())
            lines = clean_output.split("\n")
            csv_lines = [line for line in lines if "Metric" in line or "," in line]
            assert any("Metric,Value" in line for line in csv_lines)
            assert any("v1.0 Jobs" in line for line in csv_lines)

    def test_cost_analysis_save_to_file(self) -> None:
        """Test cost-analysis command saving output to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            output_path = str(Path(tmpdir) / "report.txt")

            store = JobStore(db_path)
            store.add_job(
                job_id="job_1",
                title="Python Developer",
                company="Tech Corp",
                preprocessing_version="v1.0",
                tokens=1000,
            )
            store.close()

            result = runner.invoke(
                app,
                ["cost-analysis", "--db", db_path, "--output", output_path],
            )

            assert result.exit_code == 0
            clean_output = strip_ansi(result.stdout)
            assert "saved to" in clean_output.lower()

            assert Path(output_path).exists()
            content = Path(output_path).read_text()
            assert "Cost Analysis" in content

    def test_cost_analysis_table_format_default(self) -> None:
        """Test cost-analysis default table format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")

            store = JobStore(db_path)
            store.add_job(
                job_id="job_1",
                title="Python Developer",
                company="Tech Corp",
                preprocessing_version="v1.0",
                tokens=1000,
            )
            store.close()

            result = runner.invoke(app, ["cost-analysis", "--db", db_path])

            assert result.exit_code == 0
            clean_output = strip_ansi(result.stdout)
            assert "Cost Analysis" in clean_output
            assert any(section in clean_output for section in ["Job Counts", "Token Usage", "Cost Impact"])

    def test_cost_analysis_with_reprocessing_metrics(self) -> None:
        """Test cost-analysis includes re-preprocessing metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")

            store = JobStore(db_path)
            store.add_job(
                job_id="job_1",
                title="Python Developer",
                company="Tech Corp",
                preprocessing_version="v2.0",
                tokens=650,
            )

            store.log_reprocessing_metrics(
                job_id="job_1",
                tokens_before=1000,
                tokens_after=650,
                version_before="v1.0",
                version_after="v2.0",
                cost_before=0.003,
                cost_after=0.00195,
            )
            store.close()

            result = runner.invoke(app, ["cost-analysis", "--db", db_path, "--format", "json"])

            assert result.exit_code == 0
            output = result.stdout.strip()
            json_start = output.find("{")
            if json_start >= 0:
                output = output[json_start:]
            output_data = json.loads(output)
            assert output_data["reprocessing_runs"] == 1
            assert output_data["total_reprocessing_tokens_saved"] == 350

    def test_cost_analysis_json_output_file(self) -> None:
        """Test cost-analysis saving JSON output to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            output_path = str(Path(tmpdir) / "report.json")

            store = JobStore(db_path)
            store.add_job(
                job_id="job_1",
                title="Python Developer",
                company="Tech Corp",
                preprocessing_version="v1.0",
                tokens=1000,
            )
            store.add_job(
                job_id="job_2",
                title="Senior Developer",
                company="Tech Corp",
                preprocessing_version="v2.0",
                tokens=650,
            )
            store.close()

            result = runner.invoke(
                app,
                [
                    "cost-analysis",
                    "--db",
                    db_path,
                    "--format",
                    "json",
                    "--output",
                    output_path,
                ],
            )

            assert result.exit_code == 0
            assert Path(output_path).exists()

            with open(output_path) as f:
                data = json.load(f)
            assert data["total_jobs_v1_0"] == 1
            assert data["total_jobs_v2_0"] == 1

    def test_cost_analysis_migration_progress_displayed(self) -> None:
        """Test that migration progress is displayed in output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")

            store = JobStore(db_path)
            # 3 v1.0 + 1 v2.0 job = 25% migrated.
            for i in range(3):
                store.add_job(
                    job_id=f"job_v1_{i}",
                    title=f"Job v1 {i}",
                    company="Company A",
                    preprocessing_version="v1.0",
                    tokens=1000,
                )
            store.add_job(
                job_id="job_v2_0",
                title="Job v2 0",
                company="Company B",
                preprocessing_version="v2.0",
                tokens=650,
            )
            store.close()

            result = runner.invoke(app, ["cost-analysis", "--db", db_path, "--format", "json"])

            assert result.exit_code == 0
            output = result.stdout.strip()
            json_start = output.find("{")
            if json_start >= 0:
                output = output[json_start:]
            output_data = json.loads(output)
            assert output_data["migration_progress_percent"] == 25.0

    def test_cost_analysis_token_rate_matches_blended_model_pricing(self) -> None:
        """Each version's printed rate is the token-weighted rate of the models assessing its jobs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")

            store = JobStore(db_path)
            assessments = AssessmentStore(db_path)
            # SYNTHETIC: v1.0 mixes two models so the token weighting is observable
            store.add_job(job_id="job_v1_a", title="A", company="Tech Corp", preprocessing_version="v1.0", tokens=1000)
            store.add_job(job_id="job_v1_b", title="B", company="Tech Corp", preprocessing_version="v1.0", tokens=2000)
            store.add_job(job_id="job_v2", title="C", company="Tech Corp", preprocessing_version="v2.0", tokens=650)
            _save_assessment(assessments, "job_v1_a", HAIKU_MODEL)
            _save_assessment(assessments, "job_v1_b", DEFAULT_MODEL)
            _save_assessment(assessments, "job_v2", DEFAULT_MODEL)
            assessments._close_db()
            store.close()

            result = runner.invoke(app, ["cost-analysis", "--db", db_path])

        assert result.exit_code == 0
        clean_output = strip_ansi(result.stdout)
        expected_v1 = (1000 * get_model_pricing(HAIKU_MODEL)[0] + 2000 * get_model_pricing(DEFAULT_MODEL)[0]) / 3000
        expected_v2 = get_model_pricing(DEFAULT_MODEL)[0]
        assert _printed_rate(clean_output, "v1.0") == pytest.approx(expected_v1, abs=0.005)
        assert _printed_rate(clean_output, "v2.0") == pytest.approx(expected_v2, abs=0.005)

    def test_cost_analysis_token_rate_without_assessments_uses_default_model(self) -> None:
        """Jobs without assessment rows fall back to DEFAULT_MODEL input pricing for both rates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")

            store = JobStore(db_path)
            store.add_job(job_id="job_v1", title="A", company="Tech Corp", preprocessing_version="v1.0", tokens=1000)
            store.add_job(job_id="job_v2", title="B", company="Tech Corp", preprocessing_version="v2.0", tokens=650)
            store.close()

            result = runner.invoke(app, ["cost-analysis", "--db", db_path])

        assert result.exit_code == 0
        clean_output = strip_ansi(result.stdout)
        expected = get_model_pricing(DEFAULT_MODEL)[0]
        assert _printed_rate(clean_output, "v1.0") == pytest.approx(expected, abs=0.005)
        assert _printed_rate(clean_output, "v2.0") == pytest.approx(expected, abs=0.005)
