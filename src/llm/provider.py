"""Claude 3.5 Sonnet LLM provider for job assessments."""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from ..models.job import Assessment

logger = logging.getLogger(__name__)


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
    """Claude 3.5 Sonnet LLM provider for CV-to-job assessment."""

    # Pricing constants (Claude 3.5 Sonnet)
    INPUT_PRICE_PER_1M = 0.003
    OUTPUT_PRICE_PER_1M = 0.015
    MODEL = "claude-3-5-sonnet-20241022"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize LLM provider.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set and api_key not provided")

        try:
            import anthropic

            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError as err:
            raise ImportError(
                "anthropic package not installed. Run: pip install anthropic"
            ) from err

        logger.info(f"Initialized LLMProvider with model: {self.MODEL}")

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

        # Combine job chunks
        job_text = "\n".join(job_chunks)

        # Build assessment prompt
        prompt = self._build_assessment_prompt(cv_text, job_text)

        # Retry logic (max 3 attempts)
        for attempt in range(3):
            try:
                logger.debug(f"Assessing job {job_id} (attempt {attempt + 1}/3)")

                response = self.client.messages.create(
                    model=self.MODEL,
                    max_tokens=1024,
                    system="You are an expert recruiter evaluating job fit. "
                    "Respond with ONLY valid JSON, no extra text.",
                    messages=[{"role": "user", "content": prompt}],
                )

                # Extract token usage
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                total_tokens = input_tokens + output_tokens

                # Calculate actual cost
                actual_cost = (input_tokens / 1_000_000) * self.INPUT_PRICE_PER_1M + (
                    output_tokens / 1_000_000
                ) * self.OUTPUT_PRICE_PER_1M

                # Parse response - ensure we get a TextBlock
                response_text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        response_text = block.text.strip()
                        break

                # Clean up JSON if wrapped in markdown code blocks
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                response_text = response_text.strip()

                data = json.loads(response_text)

                # Build result
                result = AssessmentResult(
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

                logger.info(
                    f"Assessed job {job_id}: overall={result.overall_score}, "
                    f"tokens={total_tokens}, cost=${actual_cost:.6f}"
                )

                return result

            except anthropic.RateLimitError as e:
                wait_time = 2**attempt
                if attempt < 2:
                    logger.warning(
                        f"Rate limited on job {job_id}, waiting {wait_time}s before retry"
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"Rate limited on job {job_id} after 3 attempts")
                    raise RuntimeError(f"Rate limited after 3 attempts for job {job_id}") from e

            except anthropic.APIConnectionError as e:
                if attempt < 2:
                    logger.warning(f"API connection error for job {job_id}, retrying...")
                    time.sleep(1)
                else:
                    logger.error(f"API connection failed for job {job_id}")
                    raise RuntimeError(f"API connection failed for job {job_id}") from e

            except (json.JSONDecodeError, KeyError):
                if attempt < 2:
                    logger.warning(
                        f"Failed to parse response for job {job_id}, retrying with fallback..."
                    )
                    # Try with more explicit JSON prompt on retry
                    continue
                else:
                    logger.error(f"Failed to parse assessment response for job {job_id}")
                    # Return default assessment on parse failure
                    return AssessmentResult(
                        job_id=job_id,
                        overall_score=50,
                        tech_score=50,
                        seniority_score=50,
                        location_score=50,
                        recommendations=[
                            "Unable to fully assess. Please review job details manually."
                        ],
                        summary="Assessment parsing failed. Scores are defaults.",
                        tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                        actual_cost=0.0,
                    )

        raise ValueError(f"Failed to assess job {job_id} after 3 attempts")

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
