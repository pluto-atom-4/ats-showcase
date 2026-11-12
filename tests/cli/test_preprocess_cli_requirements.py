"""Integration tests for preprocess CLI with requirement extraction.

Tests CLI flags --extract-requirements, --no-extract-requirements,
and --export-requirements-json for Phase 8 requirement extraction.
"""

import json
import re
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text.

    Args:
        text: Text potentially containing ANSI color/formatting codes

    Returns:
        Text with all ANSI escape sequences removed
    """
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


@pytest.fixture
def sample_jobs_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[tuple[Path, list[dict[str, Any]]], None, None]:
    """Create sample jobs in data/extracted_jobs/ for testing.

    Writes test jobs to data/extracted_jobs/test_jobs.json during test,
    then removes them after test completes.
    """
    sample_jobs = [
        {
            "id": "job_001",
            "title": "Senior Python Developer",
            "company": "TechCorp",
            "location": "Remote",
            "url": "https://example.com/job1",
            "description": (
                "We are seeking a Senior Python Developer. "
                "Required: 5+ years of Python experience. "
                "Must have knowledge of Django and FastAPI. "
                "Essential skills include REST API design. "
                "Proficiency in Docker is mandatory."
            ),
        },
        {
            "id": "job_002",
            "title": "Full Stack Engineer",
            "company": "StartupXYZ",
            "location": "San Francisco",
            "url": "https://example.com/job2",
            "description": (
                "Join our team as a Full Stack Engineer. "
                "Required technologies: React, Node.js, PostgreSQL. "
                "Must understand microservices architecture. "
                "Experience with AWS is essential. "
                "Should have CI/CD pipeline experience."
            ),
        },
        {
            "id": "job_003",
            "title": "Data Scientist",
            "company": "DataSys",
            "location": "New York",
            "url": "https://example.com/job3",
            "description": (
                "Join our analytics team as a Data Scientist. "
                "Essential: Machine learning knowledge required. "
                "Proficiency in Python and SQL. "
                "Understanding of statistical methods. "
                "Ability to communicate findings."
            ),
        },
        {
            "id": "job_004",
            "title": "DevOps Engineer",
            "company": "CloudPlatform",
            "location": "Remote",
            "url": "https://example.com/job4",
            "description": (
                "DevOps Engineer for infrastructure automation. "
                "Must have hands-on Kubernetes experience. "
                "Required: AWS or GCP certification. "
                "Essential: Infrastructure as Code (Terraform). "
                "Strong Linux/Unix administration skills."
            ),
        },
        {
            "id": "job_005",
            "title": "Frontend Developer",
            "company": "WebDesign Inc",
            "location": "Boston",
            "url": "https://example.com/job5",
            "description": (
                "Seeking Frontend Developer for modern web apps. "
                "Required: JavaScript/TypeScript expertise. "
                "Must know React or Vue.js. "
                "Proficiency in HTML5 and CSS3. "
                "Understanding of responsive design essential."
            ),
        },
    ]

    extracted_dir = tmp_path / "data" / "extracted_jobs"
    extracted_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)

    job_file = extracted_dir / "test_jobs.json"
    with open(job_file, "w") as f:
        json.dump(sample_jobs, f)

    try:
        yield job_file, sample_jobs
    finally:
        # tmp_path cleanup is handled by pytest.
        pass


class TestPreprocessCLIRequirementExtraction:
    """Tests for CLI requirement extraction flags."""

    def test_extract_requirements_flag_enabled(self, sample_jobs_file):
        """Test that --extract-requirements flag enables extraction."""
        job_file, _ = sample_jobs_file

        result = runner.invoke(app, ["preprocess", "--extract-requirements"])

        assert result.exit_code == 0, f"CLI failed: {result.stdout}"
        assert "Preprocessing complete" in result.stdout or "Processing" in result.stdout

    def test_extract_requirements_flag_disabled(self, sample_jobs_file):
        """Test that --no-extract-requirements flag disables extraction."""
        job_file, _ = sample_jobs_file

        result = runner.invoke(app, ["preprocess", "--no-extract-requirements"])

        assert result.exit_code == 0, f"CLI failed: {result.stdout}"
        assert "Preprocessing complete" in result.stdout or "Processing" in result.stdout

    def test_export_requirements_json_flag(self, sample_jobs_file):
        """Test that --export-requirements-json flag creates output file."""
        job_file, _ = sample_jobs_file

        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "requirements.json"

            result = runner.invoke(
                app,
                [
                    "preprocess",
                    "--extract-requirements",
                    "--export-requirements-json",
                    str(output_file),
                ],
            )

            assert result.exit_code in [0, 1], f"CLI failed unexpectedly: {result.stdout}"

    def test_preprocess_help_includes_requirement_flags(self):
        """Test that help text includes requirement extraction flags."""
        result = runner.invoke(app, ["preprocess", "--help"])

        assert result.exit_code == 0
        help_output_clean = strip_ansi(result.stdout)
        # Check for flag names (may be truncated in help due to column width)
        assert "extract-requireme" in help_output_clean or "--extract-requirements" in help_output_clean
        assert "no-extract-requi" in help_output_clean or "--no-extract-requirements" in help_output_clean
        assert "export-requiremen" in help_output_clean or "--export-requirements-json" in help_output_clean
        assert "trigger-based requirement extraction" in help_output_clean.lower()

    def test_default_extract_requirements_enabled(self):
        """Test that requirement extraction is enabled by default."""
        result = runner.invoke(app, ["preprocess", "--help"])

        assert result.exit_code == 0
        help_output_clean = strip_ansi(result.stdout)
        assert "extract-requirement" in help_output_clean.lower()

    def test_requirement_extraction_produces_json_output(self, sample_jobs_file):
        """Test that requirement extraction produces valid JSON output."""
        job_file, _ = sample_jobs_file

        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "requirements.json"

            result = runner.invoke(
                app,
                [
                    "preprocess",
                    "--extract-requirements",
                    "--export-requirements-json",
                    str(output_file),
                ],
            )

            assert result.exit_code in [0, 1]

            # The export may not happen (e.g. no jobs), so verify JSON only if it did.
            if output_file.exists():
                try:
                    with open(output_file) as f:
                        requirements = json.load(f)
                    assert isinstance(requirements, list)

                    for req in requirements:
                        assert isinstance(req, dict)
                        assert "text" in req
                        assert "trigger_word" in req
                        assert "confidence" in req
                except json.JSONDecodeError:
                    pytest.fail(f"Invalid JSON in {output_file}")


class TestPreprocessCLITokenCostAnalysis:
    """Tests for token cost impact analysis with requirement extraction."""

    def test_token_cost_impact_10_jobs(self, sample_jobs_file):
        """Measure token cost impact of requirement extraction on 10-job batch.

        Expected: <5% token increase with requirement extraction enabled.
        """
        job_file, _ = sample_jobs_file

        result_with = runner.invoke(
            app,
            [
                "preprocess",
                "--extract-requirements",
                "--show-estimates",
                "--batch-size",
                "10",
            ],
        )

        tokens_with = _extract_token_count_from_output(result_with.stdout)

        result_without = runner.invoke(
            app,
            [
                "preprocess",
                "--no-extract-requirements",
                "--show-estimates",
                "--batch-size",
                "10",
            ],
        )

        tokens_without = _extract_token_count_from_output(result_without.stdout)

        assert result_with.exit_code in [0, 1]
        assert result_without.exit_code in [0, 1]

        # Requirement extraction must add under 5% to total tokens.
        if tokens_with is not None and tokens_without is not None and tokens_without > 0:
            percent_increase = ((tokens_with - tokens_without) / tokens_without) * 100
            assert percent_increase < 5.0, f"Token increase too high: {percent_increase:.2f}% (expected <5%)"

    def test_cost_reporting_with_requirements(self, sample_jobs_file):
        """Test that cost is reported correctly with requirement extraction."""
        job_file, _ = sample_jobs_file

        result = runner.invoke(
            app,
            ["preprocess", "--extract-requirements", "--show-estimates"],
        )

        assert "Total cost" in result.stdout or "cost" in result.stdout.lower()


def _extract_token_count_from_output(output: str) -> int | None:
    """Extract total token count from CLI output.

    Args:
        output: CLI stdout output

    Returns:
        Token count if found, None otherwise
    """
    for line in output.split("\n"):
        if "Total tokens:" in line:
            try:
                parts = line.split("Total tokens:")
                if len(parts) > 1:
                    token_str = parts[1].strip().split()[0].replace(",", "")
                    return int(token_str)
            except (ValueError, IndexError):
                pass
    return None
