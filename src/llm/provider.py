"""Claude LLM provider for job assessments."""

import functools
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Union

from src.config.models import (
    DEFAULT_MODEL,
    get_model_display_name,
    get_model_pricing,
    resolve_model_alias,
    validate_model,
)
from src.models.job import Assessment
from src.tokenization.counter import TokenCounter

logger = logging.getLogger(__name__)

_RAW_MAX_OUTPUT_TOKENS = 500


@functools.cache
def _get_token_counter() -> TokenCounter:
    # Lazy: loading the tiktoken encoding is slow and only the raw assess path needs it.
    return TokenCounter()


class AssessmentResult:
    """Result from job assessment."""

    def __init__(
        self,
        job_id: str,
        overall_score: float,
        tech_score: float,
        seniority_score: float,
        location_score: float,
        recommendations: List[str],
        summary: str,
        tokens_used: int,
        actual_cost: float,
    ):
        """Initialize assessment result."""
        self.job_id = job_id
        self.overall_score = overall_score
        self.tech_score = tech_score
        self.seniority_score = seniority_score
        self.location_score = location_score
        self.recommendations = recommendations
        self.summary = summary
        self.tokens_used = tokens_used
        self.actual_cost = actual_cost

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "job_id": self.job_id,
            "overall_score": self.overall_score,
            "tech_score": self.tech_score,
            "seniority_score": self.seniority_score,
            "location_score": self.location_score,
            "recommendations": self.recommendations,
            "summary": self.summary,
            "tokens_used": self.tokens_used,
            "actual_cost": self.actual_cost,
        }

    def to_assessment_model(self) -> Assessment:
        """Convert to Pydantic Assessment model."""
        return Assessment(
            job_id=self.job_id,
            overall_score=self.overall_score,
            tech_score=self.tech_score,
            seniority_score=self.seniority_score,
            location_score=self.location_score,
            recommendations=self.recommendations,
            summary=self.summary,
            tokens_used=self.tokens_used,
            actual_cost=self.actual_cost,
        )


class LLMProvider:
    """Claude LLM provider for CV-to-job assessment."""

    def __init__(self, api_key: Optional[str] = None, model_id: Optional[str] = None):
        """
        Initialize LLM provider.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model_id: Claude model ID (defaults to DEFAULT_MODEL from config)
        """
        if model_id:
            validate_model(model_id)
            self.model = resolve_model_alias(model_id)
        else:
            self.model = DEFAULT_MODEL

        self.input_price_per_1m, self.output_price_per_1m = get_model_pricing(self.model)

        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            error_msg = (
                "ANTHROPIC_API_KEY not found.\n"
                "  • Set ANTHROPIC_API_KEY in .env file (recommended)\n"
                "  • Or export ANTHROPIC_API_KEY in your shell\n"
                "  • Or pass api_key parameter to LLMProvider()"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        try:
            import anthropic

            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError as err:
            raise ImportError("anthropic package not installed. Run: pip install anthropic") from err

        model_display = get_model_display_name(self.model)
        logger.info(
            f"Initialized LLMProvider with {model_display} ({self.model}) - "
            f"${self.input_price_per_1m:.2f}/${self.output_price_per_1m:.2f} per 1M tokens"
        )

    def assess_job(
        self,
        job_id: str,
        job_chunks: List[str],
        cv_text: str,
    ) -> AssessmentResult:
        """
        Assess CV fit for a job.

        Args:
            job_id: Job posting ID
            job_chunks: Preprocessed job chunks from Phase 2
            cv_text: User's CV as text

        Returns:
            AssessmentResult with scores and recommendations

        Raises:
            ValueError: If assessment fails after retries
            RuntimeError: If API communication fails
        """
        import anthropic

        job_text = "\n".join(job_chunks)
        prompt = self._build_assessment_prompt(cv_text, job_text)

        for attempt in range(3):
            try:
                logger.debug(f"Assessing job {job_id} (attempt {attempt + 1}/3)")
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    system="You are an expert recruiter evaluating job fit. "
                    "Respond with ONLY valid JSON, no extra text.",
                    messages=[{"role": "user", "content": prompt}],
                )

                response_text = self._extract_response_text(response)
                response_text = self._clean_json_response(response_text)
                data = self._parse_assessment_response(
                    response_text,
                    response.usage.input_tokens,
                    response.usage.output_tokens,
                )

                result = self._build_assessment_result(job_id, data, response)
                logger.info(
                    f"Assessed job {job_id}: overall={result.overall_score}, "
                    f"tokens={result.tokens_used}, cost=${result.actual_cost:.6f}"
                )
                return result

            except anthropic.RateLimitError as e:
                should_retry = self._handle_rate_limit_error(attempt, job_id)
                if not should_retry:
                    raise RuntimeError(f"Rate limited after 3 attempts for job {job_id}") from e

            except anthropic.APIConnectionError as e:
                should_retry = self._handle_connection_error(attempt, job_id)
                if not should_retry:
                    raise RuntimeError(f"API connection failed for job {job_id}") from e

            except (json.JSONDecodeError, KeyError, ValueError):
                resp = response if "response" in locals() else None
                result_or_retry = self._handle_parse_error(attempt, job_id, resp)
                if isinstance(result_or_retry, AssessmentResult):
                    return result_or_retry

        raise ValueError(f"Failed to assess job {job_id} after 3 attempts")

    def assess_job_raw(
        self,
        cv_text: str,
        job_description: str,
        max_retries: int = 3,
        use_examples: bool = False,
    ) -> Dict[str, Any]:
        """Assess CV fit for a job, returning the parsed assessment with estimated and actual token costs."""
        # Lazy: src.assessment imports assessor, which will import this module once C3 lands.
        from src.assessment.prompt_builder import PromptBuilder

        if use_examples:
            prompt = PromptBuilder.build_prompt_with_examples(cv_text, job_description)
        else:
            prompt = PromptBuilder.build_simple_prompt(cv_text, job_description)

        # Estimate before the call: the actual output length is unknown until the response arrives.
        estimated_input = _get_token_counter().count_tokens(prompt)
        estimated_output = _RAW_MAX_OUTPUT_TOKENS
        estimated_cost = self._cost_usd(estimated_input, estimated_output)
        logger.info(f"Assessment estimate: {estimated_input} input tokens, ${estimated_cost:.6f}")

        message, elapsed_ms, attempt = self._call_api_with_retries(prompt, max_retries)

        response_text = self._clean_json_response(self._extract_response_text(message))
        if not response_text:
            raise ValueError("Unexpected response format: no text content")
        try:
            assessment: Dict[str, Any] = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse assessment JSON: {e}\nResponse: {response_text}")
            raise

        actual_input = message.usage.input_tokens
        actual_output = message.usage.output_tokens
        actual_cost = self._cost_usd(actual_input, actual_output)
        logger.info(
            f"Assessment complete: score={assessment.get('overall_score', '?')}, "
            f"actual tokens={actual_input + actual_output}, cost=${actual_cost:.6f}"
        )

        return {
            "assessment": assessment,
            "cost_tracking": {
                "estimated_input": estimated_input,
                "estimated_output": estimated_output,
                "estimated_cost_usd": estimated_cost,
                "actual_input": actual_input,
                "actual_output": actual_output,
                "actual_cost_usd": actual_cost,
            },
            "metadata": {
                "model": self.model,
                "api_call_time_ms": elapsed_ms,
                "attempt": attempt,
            },
        }

    def _cost_usd(self, input_tokens: int, output_tokens: int) -> float:
        return (input_tokens / 1_000_000) * self.input_price_per_1m + (
            output_tokens / 1_000_000
        ) * self.output_price_per_1m

    def _call_api_with_retries(self, prompt: str, max_retries: int) -> tuple[Any, int, int]:
        import anthropic

        for attempt in range(max_retries):
            try:
                start_time = time.time()
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=_RAW_MAX_OUTPUT_TOKENS,
                    messages=[{"role": "user", "content": prompt}],
                )
                elapsed_ms = int((time.time() - start_time) * 1000)
                return message, elapsed_ms, attempt + 1

            except anthropic.AuthenticationError as e:
                logger.error(f"Authentication failed: {e}")
                raise

            except anthropic.APIStatusError as e:
                retryable = isinstance(e, anthropic.RateLimitError) or e.status_code in (500, 502, 503)
                if not retryable or attempt == max_retries - 1:
                    logger.error(f"API error {e.status_code} on attempt {attempt + 1}/{max_retries}: {e}")
                    raise
                backoff_seconds = 2**attempt
                logger.warning(
                    f"API error {e.status_code} (attempt {attempt + 1}/{max_retries}). Retrying in {backoff_seconds}s"
                )
                time.sleep(backoff_seconds)

        raise RuntimeError("Unexpected: max_retries loop exhausted")

    def _extract_response_text(self, response: Any) -> str:
        """
        Extract text from response content blocks.

        Args:
            response: API response object

        Returns:
            Extracted response text
        """
        for block in response.content:
            if hasattr(block, "text"):
                text_value = getattr(block, "text", "")
                return str(text_value).strip()
        return ""

    def _clean_json_response(self, text: str) -> str:
        """
        Clean JSON response by removing markdown code block wrappers.

        Args:
            text: Raw response text

        Returns:
            Clean JSON string
        """
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    def _parse_assessment_response(self, response_text: str, input_tokens: int, output_tokens: int) -> Dict[str, Any]:
        """
        Parse and validate JSON assessment response.

        Args:
            response_text: Raw response text
            input_tokens: Input token count
            output_tokens: Output token count

        Returns:
            Parsed data dictionary

        Raises:
            json.JSONDecodeError: If JSON is invalid
            ValueError: If required fields are missing
        """
        data: Dict[str, Any] = json.loads(response_text)

        required_fields = [
            "overall_score",
            "tech_score",
            "seniority_score",
            "location_score",
        ]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        return data

    def _build_assessment_result(self, job_id: str, data: dict[str, Any], response: Any) -> AssessmentResult:
        """
        Build AssessmentResult from parsed data.

        Args:
            job_id: Job ID
            data: Parsed assessment data
            response: API response object (for token counts)

        Returns:
            AssessmentResult object
        """
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        total_tokens = input_tokens + output_tokens

        actual_cost = (input_tokens / 1_000_000) * self.input_price_per_1m + (
            output_tokens / 1_000_000
        ) * self.output_price_per_1m

        return AssessmentResult(
            job_id=job_id,
            overall_score=float(data.get("overall_score", 50)),
            tech_score=float(data.get("tech_score", 50)),
            seniority_score=float(data.get("seniority_score", 50)),
            location_score=float(data.get("location_score", 50)),
            recommendations=data.get("recommendations", []),
            summary=data.get("summary", "Assessment completed."),
            tokens_used=total_tokens,
            actual_cost=actual_cost,
        )

    def _handle_rate_limit_error(self, attempt: int, job_id: str) -> bool:
        """
        Handle rate limit error with exponential backoff.

        Args:
            attempt: Current attempt number (0-2)
            job_id: Job ID for logging

        Returns:
            True if should retry, False if final attempt
        """
        wait_time = 2**attempt
        if attempt < 2:
            logger.warning(f"Rate limited on job {job_id}, waiting {wait_time}s before retry")
            time.sleep(wait_time)
            return True
        else:
            logger.error(f"Rate limited on job {job_id} after 3 attempts")
            return False

    def _handle_connection_error(self, attempt: int, job_id: str) -> bool:
        """
        Handle API connection error.

        Args:
            attempt: Current attempt number (0-2)
            job_id: Job ID for logging

        Returns:
            True if should retry, False if final attempt
        """
        if attempt < 2:
            logger.warning(f"API connection error for job {job_id}, retrying...")
            time.sleep(1)
            return True
        else:
            logger.error(f"API connection failed for job {job_id}")
            return False

    def _handle_parse_error(self, attempt: int, job_id: str, response: Optional[Any]) -> Union[AssessmentResult, bool]:
        """
        Handle JSON parsing error.

        Args:
            attempt: Current attempt number (0-2)
            job_id: Job ID for logging
            response: API response object (if available)

        Returns:
            AssessmentResult on final attempt, True to retry otherwise
        """
        if attempt < 2:
            logger.warning(f"Failed to parse response for job {job_id}, retrying with fallback...")
            return True
        else:
            logger.error(f"Failed to parse assessment response for job {job_id}")
            if response:
                total_tokens = response.usage.input_tokens + response.usage.output_tokens
            else:
                total_tokens = 0

            return AssessmentResult(
                job_id=job_id,
                overall_score=50,
                tech_score=50,
                seniority_score=50,
                location_score=50,
                recommendations=["Unable to fully assess. Please review job details manually."],
                summary="Assessment parsing failed. Scores are defaults.",
                tokens_used=total_tokens,
                actual_cost=0.0,
            )

    def _build_assessment_prompt(self, cv_text: str, job_text: str) -> str:
        """
        Build assessment prompt from CV and job text.

        Args:
            cv_text: User's CV
            job_text: Job description

        Returns:
            Assessment prompt
        """
        return f"""Evaluate the candidate's CV fit for this job opening.

CANDIDATE CV:
{cv_text}

JOB POSTING:
{job_text}

Assess on these dimensions (0-100 scale):
1. Tech Skills Match: Do they have required technologies?
2. Seniority Level: Years of experience vs. role expectations?
3. Location Fit: Remote/on-site/hybrid alignment?
4. Overall Score: Weighted fit (40% tech, 30% seniority, 30% location)

Provide recommendations for gaps.

Respond with ONLY this JSON (no markdown, no extra text):
{{
  "tech_score": <0-100>,
  "seniority_score": <0-100>,
  "location_score": <0-100>,
  "overall_score": <0-100>,
  "recommendations": ["gap1", "gap2"],
  "summary": "<2-3 sentence assessment>"
}}"""
