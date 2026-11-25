"""Tests for the stats CLI command (#985)."""

from pathlib import Path

from typer.testing import CliRunner

from src.cli import app
from src.storage.assessment_store import AssessmentStore

runner = CliRunner()
HELP_ENV = {"COLUMNS": "200"}
EMPTY_LINES = [
    "📈 Statistics:",
    "   Total assessments: 0",
    "⚠️  No assessments in database yet. Run 'assess' first.",
]


def _save(
    store: AssessmentStore,
    job_id: str,
    score: float,
    input_tokens: int,
    output_tokens: int,
    cost: float,
) -> None:
    store.save_assessment(
        job_id=job_id,
        title="Synthetic Job",
        company="Synthetic Co",
        location=None,
        overall_score=score,
        tech_score=score,
        seniority_score=score,
        location_score=score,
        recommendations=[],
        summary="SYNTHETIC: assessment row for stats tests",
        tokens_used=input_tokens + output_tokens,
        actual_cost=cost,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def _seed_three(db: Path) -> None:
    store = AssessmentStore(str(db))
    _save(store, "job-a", 42.0, 1000, 1000, 0.040000)
    _save(store, "job-b", 93.0, 2000, 1912, 0.050000)
    _save(store, "job-c", 70.0, 15240, 1000, 0.023400)


class TestStatsCommand:
    """Test stats CLI command."""

    def test_stats_help(self) -> None:
        result = runner.invoke(app, ["stats", "--help"], env=HELP_ENV)
        assert result.exit_code == 0
        assert "--db" in result.stdout
        assert "--show-token-usage" in result.stdout
        assert "--no-show-token-usage" in result.stdout

    def test_stats_empty_db(self, tmp_path: Path) -> None:
        db = tmp_path / "empty.db"
        result = runner.invoke(app, ["stats", "--db", str(db)])
        assert result.exit_code == 0
        assert result.stdout.splitlines() == EMPTY_LINES

    def test_stats_without_flag_hides_token_usage(self, tmp_path: Path) -> None:
        db = tmp_path / "seeded.db"
        _seed_three(db)
        result = runner.invoke(app, ["stats", "--db", str(db)])
        assert result.exit_code == 0
        assert "Token Usage" not in result.stdout
        assert result.stdout.splitlines() == [
            "📈 Statistics:",
            "   Total assessments: 3",
            "   Average score:     68.3",
            "   Score range:       42 - 93",
        ]

    def test_stats_with_flag_shows_token_usage(self, tmp_path: Path) -> None:
        db = tmp_path / "seeded.db"
        _seed_three(db)
        result = runner.invoke(app, ["stats", "--db", str(db), "--show-token-usage"])
        assert result.exit_code == 0
        assert result.stdout.splitlines() == [
            "📈 Statistics:",
            "   Total assessments: 3",
            "   Average score:     68.3",
            "   Score range:       42 - 93",
            "",
            "💰 Token Usage:",
            "   Input tokens:   18,240",
            "   Output tokens:  3,912",
            "   Total cost:     $0.113400",
            "   Avg cost/job:   $0.037800",
        ]

    def test_stats_empty_db_with_flag_has_no_token_section(self, tmp_path: Path) -> None:
        db = tmp_path / "empty.db"
        result = runner.invoke(app, ["stats", "--db", str(db), "--show-token-usage"])
        assert result.exit_code == 0
        assert "Token Usage" not in result.stdout
        assert result.stdout.splitlines() == EMPTY_LINES
