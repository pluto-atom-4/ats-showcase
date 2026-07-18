"""
Compare LLM model performance for assessment task.

Tests Haiku 4.5 vs Sonnet 5 vs Opus 4.8 on sample jobs.
"""

import json
import logging
from typing import Dict, List

import pytest

logger = logging.getLogger(__name__)


class LLMComparator:
    """Compare different Claude models on assessment task."""

    # Model configs: (model_id, input_price_per_1m, output_price_per_1m)
    MODELS = {
        "haiku": ("claude-haiku-4-5-20251001", 0.80, 4.0),
        "sonnet": ("claude-sonnet-5", 3.0, 15.0),
        "opus": ("claude-opus-4-8", 15.0, 75.0),
    }

    def __init__(self, api_key: str):
        """Initialize with API key."""
        import anthropic

        self.client = anthropic.Anthropic(api_key=api_key)
        self.results = {}

    def assess_with_model(
        self, model_id: str, cv_text: str, job_text: str
    ) -> Dict:
        """Run assessment with specific model."""
        prompt = self._build_prompt(cv_text, job_text)

        response = self.client.messages.create(
            model=model_id,
            max_tokens=1024,
            system="You are an expert recruiter. Respond with ONLY valid JSON.",
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse response
        try:
            assessment = json.loads(response.content[0].text)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON from {model_id}")
            return {}

        return {
            "model": model_id,
            "overall_score": assessment.get("overall_score", 0),
            "tech_score": assessment.get("tech_score", 0),
            "seniority_score": assessment.get("seniority_score", 0),
            "location_score": assessment.get("location_score", 0),
            "summary": assessment.get("summary", ""),
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }

    def compare_models(self, cv_text: str, job_text: str) -> Dict:
        """Run assessment on all models, return comparison."""
        results = {}

        for model_name, (model_id, _, _) in self.MODELS.items():
            logger.info(f"Testing {model_name} ({model_id})...")
            result = self.assess_with_model(model_id, cv_text, job_text)
            results[model_name] = result

        # Calculate variance
        scores = [r["overall_score"] for r in results.values()]
        variance = max(scores) - min(scores) if scores else 0

        return {
            "results": results,
            "variance": variance,
            "recommendation": self._get_recommendation(variance),
        }

    def _build_prompt(self, cv_text: str, job_text: str) -> str:
        """Build assessment prompt."""
        return f"""Assess how well this CV matches the job description.

CV:
{cv_text}

Job Description:
{job_text}

Respond with JSON:
{{
  "overall_score": <0-100>,
  "tech_score": <0-100>,
  "seniority_score": <0-100>,
  "location_score": <0-100>,
  "summary": "<brief summary>",
  "recommendations": [<list of strengths/gaps>]
}}"""

    def _get_recommendation(self, variance: int) -> str:
        """Get model recommendation based on variance."""
        if variance <= 5:
            return "✅ Use Haiku (95% cost savings)"
        elif variance <= 10:
            return "⚠️  Use Sonnet (80% cost savings)"
        else:
            return "❌ Keep Opus (best accuracy)"


# Test samples
SAMPLE_CV = """
John Smith
Senior Python Developer

Skills: Python, Django, FastAPI, PostgreSQL, Docker, AWS
Experience: 8 years backend development, 2 years team lead
Location: San Francisco, CA
"""

SAMPLE_JOB = """
Senior Python Developer - Remote

We're hiring a Senior Python Developer to lead backend development.

Requirements:
- 5+ years Python development
- Experience with FastAPI or Django
- PostgreSQL knowledge
- Team lead/mentoring experience
- Comfortable with remote-first culture

Nice to have:
- AWS or cloud platform experience
- Docker/Kubernetes
- Open source contributions
"""


@pytest.mark.integration
def test_model_comparison(tmp_path):
    """Run model comparison and generate report."""
    import os

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    comparator = LLMComparator(api_key)
    result = comparator.compare_models(SAMPLE_CV, SAMPLE_JOB)

    # Save results
    report_path = tmp_path / "model_comparison.json"
    with open(report_path, "w") as f:
        json.dump(result, f, indent=2)

    logger.info(f"\n\n{'='*60}")
    logger.info("MODEL COMPARISON RESULTS")
    logger.info("="*60)

    for model, scores in result["results"].items():
        logger.info(f"\n{model.upper()}:")
        logger.info(
            f"  Overall: {scores['overall_score']} | "
            f"Tech: {scores['tech_score']} | "
            f"Seniority: {scores['seniority_score']} | "
            f"Location: {scores['location_score']}"
        )
        logger.info(f"  Tokens: {scores['input_tokens']} in, {scores['output_tokens']} out")
        logger.info(f"  Summary: {scores['summary'][:80]}...")

    logger.info(f"\nVariance (score range): {result['variance']} points")
    logger.info(f"Recommendation: {result['recommendation']}\n")

    return result


if __name__ == "__main__":
    import sys

    # Run manually: python -m tests.test_llm_comparison
    pytest.main([__file__, "-v", "-s"])
