"""Tests for assess-command cost estimate pricing by model."""

import re
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import typer

from src.cli import _verify_assessment_cost

CV_TEXT = "cv"
TOKENS_PER_JOB = 1000
PROMPT_OVERHEAD = 200


def _jobs(count: int) -> list[dict[str, Any]]:
    return [{"description": f"job {i}", "title": f"t{i}"} for i in range(count)]


def _run_estimate(jobs: list[dict[str, Any]], **kwargs: Any) -> float:
    counter = MagicMock()
    counter.count_tokens.return_value = TOKENS_PER_JOB
    with (
        patch("src.tokenization.counter.TokenCounter", return_value=counter),
        patch("src.cli.typer.echo") as echo,
        patch("src.cli.typer.confirm", return_value=True),
    ):
        assert _verify_assessment_cost(jobs, CV_TEXT, True, **kwargs) is True
    printed = " ".join(str(c.args[0]) for c in echo.call_args_list if c.args)
    match = re.search(r"jobs: [$]([0-9.]+)", printed)
    assert match is not None, printed
    return float(match.group(1))


def test_default_model_uses_sonnet_input_rate() -> None:
    jobs = _jobs(3)
    total_tokens = 3 * (TOKENS_PER_JOB + PROMPT_OVERHEAD)
    estimate = _run_estimate(jobs)
    assert estimate == pytest.approx(total_tokens * 3.0 / 1_000_000, abs=1e-6)


def test_haiku_model_uses_haiku_input_rate() -> None:
    jobs = _jobs(3)
    total_tokens = 3 * (TOKENS_PER_JOB + PROMPT_OVERHEAD)
    estimate = _run_estimate(jobs, model="haiku")
    assert estimate == pytest.approx(total_tokens * 0.80 / 1_000_000, abs=1e-6)
    assert estimate != pytest.approx(_run_estimate(jobs), abs=1e-6)


def test_unknown_model_raises_value_error() -> None:
    counter = MagicMock()
    counter.count_tokens.return_value = TOKENS_PER_JOB
    with (
        patch("src.tokenization.counter.TokenCounter", return_value=counter),
        patch("src.cli.typer.echo"),
        patch("src.cli.typer.confirm", return_value=True),
        pytest.raises(ValueError),
    ):
        _verify_assessment_cost(_jobs(1), CV_TEXT, True, model="not-a-model")


def test_declined_confirmation_exits() -> None:
    counter = MagicMock()
    counter.count_tokens.return_value = TOKENS_PER_JOB
    with (
        patch("src.tokenization.counter.TokenCounter", return_value=counter),
        patch("src.cli.typer.echo"),
        patch("src.cli.typer.confirm", return_value=False),
        pytest.raises(typer.Exit),
    ):
        _verify_assessment_cost(_jobs(1), CV_TEXT, True, model="haiku")
