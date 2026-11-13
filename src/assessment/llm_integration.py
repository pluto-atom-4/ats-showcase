"""Claude API integration for job assessment with error handling and cost tracking."""

import json
import logging
import os
import time
from typing import Any, Dict, Optional

import anthropic
from anthropic.types import Message

from src.assessment.prompt_builder import PromptBuilder
from src.config.models import DEFAULT_MODEL, get_model_pricing
from src.tokenization.counter import TokenCounter

logger = logging.getLogger(__name__)

_token_counter = TokenCounter()


class LLMProvider:
    """Claude API client with rate limiting, retries, and cost tracking."""

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        """Initialize LLM provider.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Claude model to use (default: DEFAULT_MODEL)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.model = model
        self.client = anthropic.Anthropic(api_key=self.api_key)
        logger.info(f"LLMProvider initialized with model: {self.model}")

    def estimate_cost(self, prompt: str, max_output_tokens: int = 500) -> Dict[str, float]:
        """Estimate API call cost before making request.

        Args:
            prompt: Full prompt text
            max_output_tokens: Max output tokens (used for estimation)

        Returns:
            Dict with 'input_tokens', 'output_tokens', 'total_cost_usd'
        """
        input_tokens = _token_counter.count_tokens(prompt)
        # Upper bound: real output length is unknown before the call.
        output_tokens = max_output_tokens

        input_price, output_price = get_model_pricing(self.model)
        total_cost = (input_tokens / 1_000_000) * input_price + (output_tokens / 1_000_000) * output_price

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_cost_usd": total_cost,
        }

    def _call_api_with_retries(self, prompt: str, max_retries: int) -> tuple[Message, int]:
        """Call Claude API with retry logic.

        Args:
            prompt: Full prompt to send
            max_retries: Max retry attempts

        Returns:
            Tuple of (message response, elapsed_ms)

        Raises:
            anthropic.AuthenticationError: Invalid API key
            anthropic.RateLimitError: Rate limited after retries
            anthropic.APIStatusError: Other API errors after retries
        """
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=500,
                    messages=[{"role": "user", "content": prompt}],
                )
                elapsed_ms = int((time.time() - start_time) * 1000)
                return message, elapsed_ms

            except anthropic.AuthenticationError as e:
                logger.error(f"Authentication failed: {e}")
                raise

            except anthropic.RateLimitError as e:
                if attempt == max_retries - 1:
                    logger.error(f"Rate limited after {max_retries} attempts: {e}")
                    raise
                backoff_seconds = 2**attempt
                logger.warning(f"Rate limited (attempt {attempt + 1}/{max_retries}). Retrying in {backoff_seconds}s")
                time.sleep(backoff_seconds)

            except anthropic.APIStatusError as e:
                if e.status_code in (500, 502, 503):
                    if attempt == max_retries - 1:
                        logger.error(f"Server error {e.status_code} after {max_retries} attempts: {e}")
                        raise
                    backoff_seconds = 2**attempt
                    logger.warning(
                        f"Server error {e.status_code} (attempt {attempt + 1}/{max_retries}). "
                        f"Retrying in {backoff_seconds}s"
                    )
                    time.sleep(backoff_seconds)
                else:
                    logger.error(f"Client error {e.status_code}: {e}")
                    raise

        raise RuntimeError("Unexpected: max_retries loop exhausted")

    def assess_job(
        self,
        cv_text: str,
        job_description: str,
        max_retries: int = 3,
        use_examples: bool = False,
    ) -> Dict[str, Any]:
        """Assess job fit for CV with error handling and retries.

        Args:
            cv_text: CV text
            job_description: Job description text
            max_retries: Max retry attempts on transient errors
            use_examples: Include few-shot examples in prompt (more tokens, better accuracy)

        Returns:
            Dict with 'assessment', 'cost_tracking', 'metadata'

        Raises:
            anthropic.AuthenticationError: Invalid API key
            anthropic.RateLimitError: Rate limited after retries
            anthropic.APIStatusError: Other API errors after retries
        """
        if use_examples:
            prompt = PromptBuilder.build_prompt_with_examples(cv_text, job_description)
        else:
            prompt = PromptBuilder.build_simple_prompt(cv_text, job_description)

        estimate = self.estimate_cost(prompt)
        logger.info(f"Assessment estimate: {estimate['input_tokens']} input tokens, ${estimate['total_cost_usd']:.6f}")

        message, elapsed_ms = self._call_api_with_retries(prompt, max_retries)

        try:
            if not message.content or not hasattr(message.content[0], "text"):
                raise ValueError("Unexpected response format: no text content")

            response_text: str = message.content[0].text
            assessment = json.loads(response_text)

            actual_input = message.usage.input_tokens
            actual_output = message.usage.output_tokens
            input_price, output_price = get_model_pricing(self.model)
            actual_cost = (actual_input / 1_000_000) * input_price + (actual_output / 1_000_000) * output_price

            logger.info(
                f"Assessment complete: score={assessment.get('overall_score', '?')}, "
                f"actual tokens={actual_input + actual_output}, cost=${actual_cost:.6f}"
            )

            return {
                "assessment": assessment,
                "cost_tracking": {
                    "estimated_input": estimate["input_tokens"],
                    "estimated_output": estimate["output_tokens"],
                    "estimated_cost_usd": estimate["total_cost_usd"],
                    "actual_input": actual_input,
                    "actual_output": actual_output,
                    "actual_cost_usd": actual_cost,
                },
                "metadata": {
                    "model": self.model,
                    "api_call_time_ms": elapsed_ms,
                    "attempt": 1,
                },
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse assessment JSON: {e}\nResponse: {response_text}")
            raise
