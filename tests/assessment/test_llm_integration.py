"""Tests for LLMProvider Claude API integration."""

import json
from unittest.mock import MagicMock, patch

import pytest
from anthropic import APIStatusError, AuthenticationError, RateLimitError

from src.assessment.llm_integration import LLMProvider


class TestLLMProviderInit:
    """Test LLMProvider initialization."""

    def test_init_with_api_key(self) -> None:
        """Initialize with explicit API key."""
        provider = LLMProvider(api_key="sk-test-key-12345")
        assert provider.api_key == "sk-test-key-12345"
        assert provider.model == "claude-3-5-sonnet-20241022"

    def test_init_custom_model(self) -> None:
        """Initialize with custom model."""
        provider = LLMProvider(
            api_key="sk-test-key",
            model="claude-3-5-haiku-20241022"
        )
        assert provider.model == "claude-3-5-haiku-20241022"

    def test_init_missing_api_key(self) -> None:
        """Raises error if no API key provided or in env."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                LLMProvider(api_key=None)

    def test_init_from_env(self) -> None:
        """Reads API key from ANTHROPIC_API_KEY env var."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-env-key"}):
            provider = LLMProvider(api_key=None)
            assert provider.api_key == "sk-env-key"


class TestEstimateCost:
    """Test cost estimation."""

    def test_estimate_cost_simple_prompt(self) -> None:
        """Estimate cost for simple prompt."""
        provider = LLMProvider(api_key="sk-test")
        prompt = "Assess this CV: Python developer with 5 years experience"

        estimate = provider.estimate_cost(prompt)

        assert "input_tokens" in estimate
        assert "output_tokens" in estimate
        assert "total_cost_usd" in estimate
        assert estimate["input_tokens"] > 0
        assert estimate["output_tokens"] > 0
        assert estimate["total_cost_usd"] > 0

    def test_estimate_cost_respects_output_tokens(self) -> None:
        """Estimate uses provided output_tokens parameter."""
        provider = LLMProvider(api_key="sk-test")
        prompt = "Test prompt"

        estimate1 = provider.estimate_cost(prompt, max_output_tokens=100)
        estimate2 = provider.estimate_cost(prompt, max_output_tokens=500)

        # More output tokens should cost more
        assert estimate2["total_cost_usd"] > estimate1["total_cost_usd"]

    def test_estimate_cost_sonnet_pricing(self) -> None:
        """Estimate uses Sonnet pricing by default."""
        provider = LLMProvider(api_key="sk-test", model="claude-3-5-sonnet-20241022")
        prompt = "Test prompt" * 100

        estimate = provider.estimate_cost(prompt)

        # Sonnet: $0.003 input per 1M
        assert estimate["total_cost_usd"] > 0

    def test_estimate_cost_haiku_pricing(self) -> None:
        """Estimate uses Haiku pricing when specified."""
        provider = LLMProvider(api_key="sk-test", model="claude-3-5-haiku-20241022")
        prompt = "Test prompt" * 100

        estimate = provider.estimate_cost(prompt)

        # Haiku is cheaper than Sonnet
        assert estimate["total_cost_usd"] > 0

    def test_estimate_cost_empty_prompt(self) -> None:
        """Estimate handles empty prompt."""
        provider = LLMProvider(api_key="sk-test")
        estimate = provider.estimate_cost("")

        # Should still return valid structure
        assert "total_cost_usd" in estimate
        assert estimate["total_cost_usd"] >= 0

    def test_estimate_cost_long_prompt(self) -> None:
        """Estimate handles long prompt."""
        provider = LLMProvider(api_key="sk-test")
        prompt = "Test prompt " * 1000  # Very long

        estimate = provider.estimate_cost(prompt)

        assert estimate["input_tokens"] > 100
        assert estimate["total_cost_usd"] > 0


class TestAssessJobMocking:
    """Test assess_job with mocked Anthropic client."""

    @patch("src.assessment.llm_integration.anthropic.Anthropic")
    def test_assess_job_success(self, mock_anthropic_class) -> None:
        """Successful assessment returns expected structure."""
        # Mock the Anthropic client and response
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_message = MagicMock()
        response_json = (
            '{"overall_score": 75, "tech_match": 80, "seniority_match": 70, '
            '"location_match": "yes", "top_strengths": ["Python"], '
            '"gaps": ["Redis"], "reasoning": "Good fit"}'
        )
        mock_message.content = [MagicMock(text=response_json)]
        mock_message.usage.input_tokens = 600
        mock_message.usage.output_tokens = 150

        mock_client.messages.create.return_value = mock_message

        # Test
        provider = LLMProvider(api_key="sk-test")
        cv = "5 years Python, Django"
        job = "Senior Python developer needed"

        result = provider.assess_job(cv, job)

        assert "assessment" in result
        assert "cost_tracking" in result
        assert "metadata" in result
        assert result["assessment"]["overall_score"] == 75

    @patch("src.assessment.llm_integration.anthropic.Anthropic")
    def test_assess_job_cost_tracking(self, mock_anthropic_class) -> None:
        """Cost tracking includes estimated and actual."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text='{"overall_score": 75}')]
        mock_message.usage.input_tokens = 600
        mock_message.usage.output_tokens = 150

        mock_client.messages.create.return_value = mock_message

        provider = LLMProvider(api_key="sk-test")
        result = provider.assess_job("CV text", "Job text")

        cost = result["cost_tracking"]
        assert "estimated_input" in cost
        assert "estimated_output" in cost
        assert "estimated_cost_usd" in cost
        assert "actual_input" in cost
        assert "actual_output" in cost
        assert "actual_cost_usd" in cost

    @patch("src.assessment.llm_integration.anthropic.Anthropic")
    def test_assess_job_metadata(self, mock_anthropic_class) -> None:
        """Metadata includes model, call time, attempt."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text='{"overall_score": 75}')]
        mock_message.usage.input_tokens = 600
        mock_message.usage.output_tokens = 150

        mock_client.messages.create.return_value = mock_message

        provider = LLMProvider(api_key="sk-test")
        result = provider.assess_job("CV text", "Job text")

        metadata = result["metadata"]
        assert "model" in metadata
        assert "api_call_time_ms" in metadata
        assert "attempt" in metadata

    @patch("src.assessment.llm_integration.anthropic.Anthropic")
    def test_assess_job_uses_simple_prompt(self, mock_anthropic_class) -> None:
        """Simple prompt used by default (use_examples=False)."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text='{"overall_score": 75}')]
        mock_message.usage.input_tokens = 600
        mock_message.usage.output_tokens = 150

        mock_client.messages.create.return_value = mock_message

        provider = LLMProvider(api_key="sk-test")
        provider.assess_job("CV", "Job", use_examples=False)

        # Verify build_simple_prompt was used (check call count)
        mock_client.messages.create.assert_called_once()

    @patch("src.assessment.llm_integration.anthropic.Anthropic")
    def test_assess_job_uses_examples_prompt(self, mock_anthropic_class) -> None:
        """Examples prompt used when use_examples=True."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text='{"overall_score": 75}')]
        mock_message.usage.input_tokens = 600
        mock_message.usage.output_tokens = 150

        mock_client.messages.create.return_value = mock_message

        provider = LLMProvider(api_key="sk-test")
        provider.assess_job("CV", "Job", use_examples=True)

        # Verify the call was made
        mock_client.messages.create.assert_called_once()


class TestAssessJobErrors:
    """Test error handling in assess_job."""

    @patch("src.assessment.llm_integration.anthropic.Anthropic")
    def test_assess_job_auth_error(self, mock_anthropic_class) -> None:
        """Authentication error raises immediately."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        mock_client.messages.create.side_effect = AuthenticationError(
            "Invalid API key", response=MagicMock(), body={}
        )

        provider = LLMProvider(api_key="sk-bad")

        with pytest.raises(AuthenticationError):
            provider.assess_job("CV", "Job")

    @patch("src.assessment.llm_integration.anthropic.Anthropic")
    @patch("time.sleep")  # Mock sleep to speed up test
    def test_assess_job_rate_limit_retries(self, mock_sleep, mock_anthropic_class) -> None:
        """Rate limit error retries with backoff."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        # First 2 attempts fail with rate limit, 3rd succeeds
        rate_limit_error = RateLimitError("Rate limited", response=MagicMock(), body={})
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text='{"overall_score": 75}')]
        mock_message.usage.input_tokens = 600
        mock_message.usage.output_tokens = 150

        mock_client.messages.create.side_effect = [
            rate_limit_error,
            rate_limit_error,
            mock_message
        ]

        provider = LLMProvider(api_key="sk-test")
        result = provider.assess_job("CV", "Job", max_retries=3)

        # Should succeed on 3rd attempt
        assert result["assessment"]["overall_score"] == 75
        # Should have slept (2 times for first 2 retries)
        assert mock_sleep.call_count == 2

    @patch("src.assessment.llm_integration.anthropic.Anthropic")
    @patch("time.sleep")
    def test_assess_job_server_error_retries(self, mock_sleep, mock_anthropic_class) -> None:
        """500-503 server errors retry with backoff."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        # Create mock server error
        server_error = APIStatusError("Server error", response=MagicMock(status_code=503), body={})
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text='{"overall_score": 75}')]
        mock_message.usage.input_tokens = 600
        mock_message.usage.output_tokens = 150

        mock_client.messages.create.side_effect = [
            server_error,
            mock_message
        ]

        provider = LLMProvider(api_key="sk-test")
        result = provider.assess_job("CV", "Job", max_retries=2)

        assert result["assessment"]["overall_score"] == 75

    @patch("src.assessment.llm_integration.anthropic.Anthropic")
    def test_assess_job_client_error_no_retry(self, mock_anthropic_class) -> None:
        """4xx client errors don't retry."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        client_error = APIStatusError("Bad request", response=MagicMock(status_code=400), body={})
        mock_client.messages.create.side_effect = client_error

        provider = LLMProvider(api_key="sk-test")

        with pytest.raises(APIStatusError):
            provider.assess_job("CV", "Job", max_retries=3)

        # Should only try once (no retries for 4xx)
        assert mock_client.messages.create.call_count == 1

    @patch("src.assessment.llm_integration.anthropic.Anthropic")
    def test_assess_job_json_decode_error(self, mock_anthropic_class) -> None:
        """Invalid JSON response raises error."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text='{"invalid json')]  # Invalid JSON
        mock_message.usage.input_tokens = 600
        mock_message.usage.output_tokens = 150

        mock_client.messages.create.return_value = mock_message

        provider = LLMProvider(api_key="sk-test")

        with pytest.raises(json.JSONDecodeError):
            provider.assess_job("CV", "Job")

    @patch("src.assessment.llm_integration.anthropic.Anthropic")
    @patch("time.sleep")
    def test_assess_job_exhausts_retries(self, mock_sleep, mock_anthropic_class) -> None:
        """Exhausted retries raise error."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        rate_limit_error = RateLimitError("Rate limited", response=MagicMock(), body={})
        mock_client.messages.create.side_effect = rate_limit_error

        provider = LLMProvider(api_key="sk-test")

        with pytest.raises(RateLimitError):
            provider.assess_job("CV", "Job", max_retries=3)

        # All 3 attempts should have been made
        assert mock_client.messages.create.call_count == 3


class TestAssessJobEdgeCases:
    """Test edge cases."""

    @patch("src.assessment.llm_integration.anthropic.Anthropic")
    def test_assess_job_empty_cv(self, mock_anthropic_class) -> None:
        """Handles empty CV."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text='{"overall_score": 0}')]
        mock_message.usage.input_tokens = 100
        mock_message.usage.output_tokens = 50

        mock_client.messages.create.return_value = mock_message

        provider = LLMProvider(api_key="sk-test")
        result = provider.assess_job("", "Job text")

        assert "assessment" in result

    @patch("src.assessment.llm_integration.anthropic.Anthropic")
    def test_assess_job_empty_job(self, mock_anthropic_class) -> None:
        """Handles empty job."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text='{"overall_score": 0}')]
        mock_message.usage.input_tokens = 100
        mock_message.usage.output_tokens = 50

        mock_client.messages.create.return_value = mock_message

        provider = LLMProvider(api_key="sk-test")
        result = provider.assess_job("CV text", "")

        assert "assessment" in result

    @patch("src.assessment.llm_integration.anthropic.Anthropic")
    def test_assess_job_response_with_missing_fields(self, mock_anthropic_class) -> None:
        """Handles response with some missing assessment fields."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        # Minimal valid JSON
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text='{"overall_score": 50}')]
        mock_message.usage.input_tokens = 600
        mock_message.usage.output_tokens = 150

        mock_client.messages.create.return_value = mock_message

        provider = LLMProvider(api_key="sk-test")
        result = provider.assess_job("CV", "Job")

        # Should not crash, should return what we got
        assert result["assessment"]["overall_score"] == 50
