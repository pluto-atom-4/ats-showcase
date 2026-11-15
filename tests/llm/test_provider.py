import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from anthropic import APIStatusError, AuthenticationError, RateLimitError

from src.llm.provider import LLMProvider

# SYNTHETIC: fabricated CV and job text, not real candidate or posting data
CV_TEXT = "Synthetic candidate: 5 years Python, FastAPI, PostgreSQL."
JOB_TEXT = "Synthetic posting: Backend engineer, Python, remote."
# SYNTHETIC: fabricated assessment payload, not real model output
ASSESSMENT = {
    "overall_score": 82,
    "tech_score": 90,
    "seniority_score": 75,
    "location_score": 80,
    "summary": "Synthetic summary.",
}
ASSESSMENT_JSON = json.dumps(ASSESSMENT)
ESTIMATED_INPUT_TOKENS = 1000
ESTIMATED_OUTPUT_TOKENS = 500


def _message(text: str, input_tokens: int = 1200, output_tokens: int = 150) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(text=text)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def _api_error(cls: type[APIStatusError], status: int) -> APIStatusError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status, request=request)
    return cls("synthetic API error", response=response, body=None)


@pytest.fixture(autouse=True)
def _no_real_tokenizer_or_sleep():
    counter = MagicMock()
    counter.count_tokens.return_value = ESTIMATED_INPUT_TOKENS
    with (
        patch("src.llm.provider._get_token_counter", return_value=counter),
        patch("src.llm.provider.time.sleep") as sleep,
    ):
        yield sleep


@pytest.fixture
def provider() -> Any:
    instance = LLMProvider(api_key="sk-test-key")  # pragma: allowlist secret
    instance.client = MagicMock()
    return instance


class TestAssessJobRawShape:
    def test_success_returns_assessment_cost_and_metadata(self, provider: Any) -> None:
        provider.client.messages.create.return_value = _message(ASSESSMENT_JSON)

        result = provider.assess_job_raw(CV_TEXT, JOB_TEXT)

        assert set(result) == {"assessment", "cost_tracking", "metadata"}
        assert result["assessment"] == ASSESSMENT
        assert set(result["cost_tracking"]) == {
            "estimated_input",
            "estimated_output",
            "estimated_cost_usd",
            "actual_input",
            "actual_output",
            "actual_cost_usd",
        }
        assert set(result["metadata"]) == {"model", "api_call_time_ms", "attempt"}
        assert result["metadata"]["model"] == "claude-sonnet-5"
        assert result["metadata"]["attempt"] == 1
        assert isinstance(result["metadata"]["api_call_time_ms"], int)

    def test_cost_tracking_reports_estimate_and_actual_tokens(self, provider: Any) -> None:
        provider.client.messages.create.return_value = _message(ASSESSMENT_JSON, 1200, 150)

        cost = provider.assess_job_raw(CV_TEXT, JOB_TEXT)["cost_tracking"]

        assert cost["estimated_input"] == ESTIMATED_INPUT_TOKENS
        assert cost["estimated_output"] == ESTIMATED_OUTPUT_TOKENS
        assert cost["actual_input"] == 1200
        assert cost["actual_output"] == 150

    def test_request_uses_selected_model_and_prompt(self, provider: Any) -> None:
        provider.client.messages.create.return_value = _message(ASSESSMENT_JSON)

        provider.assess_job_raw(CV_TEXT, JOB_TEXT)

        kwargs = provider.client.messages.create.call_args.kwargs
        assert kwargs["model"] == "claude-sonnet-5"
        assert kwargs["max_tokens"] == 500
        assert len(kwargs["messages"]) == 1
        assert kwargs["messages"][0]["role"] == "user"
        assert CV_TEXT in kwargs["messages"][0]["content"]
        assert JOB_TEXT in kwargs["messages"][0]["content"]

    def test_use_examples_selects_few_shot_prompt(self, provider: Any) -> None:
        provider.client.messages.create.return_value = _message(ASSESSMENT_JSON)

        with patch(
            "src.assessment.prompt_builder.PromptBuilder.build_prompt_with_examples", return_value="p"
        ) as with_examples:
            provider.assess_job_raw(CV_TEXT, JOB_TEXT, use_examples=True)

        with_examples.assert_called_once_with(CV_TEXT, JOB_TEXT)


class TestAssessJobRawCostSplit:
    def test_sonnet_split_uses_config_rates(self, provider: Any) -> None:
        # Sonnet $3.00 in / $15.00 out per 1M tokens
        provider.client.messages.create.return_value = _message(ASSESSMENT_JSON, 1200, 150)

        cost = provider.assess_job_raw(CV_TEXT, JOB_TEXT)["cost_tracking"]

        assert cost["estimated_cost_usd"] == pytest.approx(1000 * 3.0 / 1e6 + 500 * 15.0 / 1e6)
        assert cost["actual_cost_usd"] == pytest.approx(1200 * 3.0 / 1e6 + 150 * 15.0 / 1e6)

    def test_haiku_alias_split_uses_haiku_rates(self) -> None:
        # Haiku $0.80 in / $4.00 out per 1M tokens
        provider = LLMProvider(api_key="sk-test-key", model_id="haiku")  # pragma: allowlist secret
        provider.client = MagicMock()
        provider.client.messages.create.return_value = _message(ASSESSMENT_JSON, 1200, 150)

        result = provider.assess_job_raw(CV_TEXT, JOB_TEXT)

        assert result["metadata"]["model"] == "claude-haiku-4-5-20251001"
        assert result["cost_tracking"]["estimated_cost_usd"] == pytest.approx(1000 * 0.80 / 1e6 + 500 * 4.0 / 1e6)
        assert result["cost_tracking"]["actual_cost_usd"] == pytest.approx(1200 * 0.80 / 1e6 + 150 * 4.0 / 1e6)

    def test_estimate_is_computed_before_api_call(self, provider: Any) -> None:
        calls: list[str] = []

        def count_tokens(_prompt: str) -> int:
            calls.append("estimate")
            return ESTIMATED_INPUT_TOKENS

        def create(**_kwargs: Any) -> SimpleNamespace:
            calls.append("call")
            return _message(ASSESSMENT_JSON)

        counter = MagicMock()
        counter.count_tokens.side_effect = count_tokens
        provider.client.messages.create.side_effect = create

        with patch("src.llm.provider._get_token_counter", return_value=counter):
            provider.assess_job_raw(CV_TEXT, JOB_TEXT)

        assert calls == ["estimate", "call"]


class TestAssessJobRawRetries:
    def test_rate_limit_then_success_retries_with_backoff(
        self, provider: Any, _no_real_tokenizer_or_sleep: MagicMock
    ) -> None:
        provider.client.messages.create.side_effect = [
            _api_error(RateLimitError, 429),
            _message(ASSESSMENT_JSON),
        ]

        result = provider.assess_job_raw(CV_TEXT, JOB_TEXT)

        assert provider.client.messages.create.call_count == 2
        _no_real_tokenizer_or_sleep.assert_called_once_with(1)
        assert result["assessment"] == ASSESSMENT
        assert result["metadata"]["attempt"] == 2

    def test_server_error_then_success_retries(self, provider: Any, _no_real_tokenizer_or_sleep: MagicMock) -> None:
        provider.client.messages.create.side_effect = [
            _api_error(APIStatusError, 503),
            _message(ASSESSMENT_JSON),
        ]

        provider.assess_job_raw(CV_TEXT, JOB_TEXT)

        assert provider.client.messages.create.call_count == 2
        _no_real_tokenizer_or_sleep.assert_called_once_with(1)

    def test_retries_exhausted_raises_last_error(self, provider: Any, _no_real_tokenizer_or_sleep: MagicMock) -> None:
        provider.client.messages.create.side_effect = _api_error(RateLimitError, 429)

        with pytest.raises(RateLimitError):
            provider.assess_job_raw(CV_TEXT, JOB_TEXT, max_retries=3)

        assert provider.client.messages.create.call_count == 3
        assert [c.args[0] for c in _no_real_tokenizer_or_sleep.call_args_list] == [1, 2]

    def test_authentication_error_not_retried(self, provider: Any, _no_real_tokenizer_or_sleep: MagicMock) -> None:
        provider.client.messages.create.side_effect = _api_error(AuthenticationError, 401)

        with pytest.raises(AuthenticationError):
            provider.assess_job_raw(CV_TEXT, JOB_TEXT)

        assert provider.client.messages.create.call_count == 1
        _no_real_tokenizer_or_sleep.assert_not_called()

    def test_client_error_not_retried(self, provider: Any, _no_real_tokenizer_or_sleep: MagicMock) -> None:
        provider.client.messages.create.side_effect = _api_error(APIStatusError, 400)

        with pytest.raises(APIStatusError):
            provider.assess_job_raw(CV_TEXT, JOB_TEXT)

        assert provider.client.messages.create.call_count == 1
        _no_real_tokenizer_or_sleep.assert_not_called()


class TestAssessJobRawResponseParsing:
    @pytest.mark.parametrize(
        "wrapped",
        [
            f"```json\n{ASSESSMENT_JSON}\n```",
            f"```\n{ASSESSMENT_JSON}\n```",
        ],
    )
    def test_strips_markdown_fences(self, provider: Any, wrapped: str) -> None:
        provider.client.messages.create.return_value = _message(wrapped)

        result = provider.assess_job_raw(CV_TEXT, JOB_TEXT)

        assert result["assessment"] == ASSESSMENT

    def test_invalid_json_raises_without_retry(self, provider: Any) -> None:
        provider.client.messages.create.return_value = _message("not json")

        with pytest.raises(json.JSONDecodeError):
            provider.assess_job_raw(CV_TEXT, JOB_TEXT)

        assert provider.client.messages.create.call_count == 1

    def test_empty_content_raises_value_error(self, provider: Any) -> None:
        provider.client.messages.create.return_value = SimpleNamespace(
            content=[],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        )

        with pytest.raises(ValueError, match="no text content"):
            provider.assess_job_raw(CV_TEXT, JOB_TEXT)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_python(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_provider_imports_in_fresh_interpreter() -> None:
    result = _run_python("import src.llm.provider")
    assert result.returncode == 0, result.stderr


def test_provider_then_assessment_import_order_has_no_cycle() -> None:
    # Simulates the C3 import order: provider loaded first, then the assessment package
    result = _run_python("import src.llm.provider; import src.assessment; import src.assessment.assessor")
    assert result.returncode == 0, result.stderr
