"""
Compare LLM model performance for assessment task.

Tests Haiku 4.5 vs Sonnet 5 vs Opus 4.8 on sample jobs.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

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
        self, model_id: str, cv_text: str, job_chunks: list
    ) -> Optional[Dict]:
        """Run assessment with specific model.

        Args:
            model_id: Claude model ID
            cv_text: CV text
            job_chunks: List of job description chunks (same format as assess command)
        """
        # Join chunks same way as provider.py does
        job_text = "\n".join(job_chunks)
        prompt = self._build_prompt(cv_text, job_text)

        try:
            response = self.client.messages.create(
                model=model_id,
                max_tokens=1024,
                system="You are an expert recruiter. Respond with ONLY valid JSON.",
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse response
            try:
                assessment = json.loads(response.content[0].text)
            except (json.JSONDecodeError, IndexError) as e:
                logger.error(f"Failed to parse JSON from {model_id}: {e}")
                logger.error(f"Response text: {response.content[0].text if response.content else 'empty'}")
                return None

            # Validate required keys
            required_keys = {"overall_score", "tech_score", "seniority_score", "location_score"}
            if not all(k in assessment for k in required_keys):
                logger.error(f"Missing keys in {model_id} response: {set(assessment.keys())}")
                return None

            return {
                "model": model_id,
                "overall_score": float(assessment.get("overall_score", 0)),
                "tech_score": float(assessment.get("tech_score", 0)),
                "seniority_score": float(assessment.get("seniority_score", 0)),
                "location_score": float(assessment.get("location_score", 0)),
                "summary": assessment.get("summary", ""),
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
        except Exception as e:
            logger.error(f"Error assessing with {model_id}: {e}")
            return None

    def compare_models(self, cv_text: str, job_chunks: list) -> Dict:
        """Run assessment on all models, return comparison.

        Args:
            cv_text: CV text
            job_chunks: List of job description chunks from preprocessed_jobs.json
        """
        results = {}

        for model_name, (model_id, _, _) in self.MODELS.items():
            logger.info(f"Testing {model_name} ({model_id})...")
            result = self.assess_with_model(model_id, cv_text, job_chunks)
            if result:
                results[model_name] = result
            else:
                results[model_name] = None

        # Calculate variance from valid results
        valid_scores = [
            r["overall_score"]
            for r in results.values()
            if r is not None and "overall_score" in r
        ]

        if not valid_scores:
            logger.error("No valid results from any model")
            variance = float('inf')
            recommendation = "❌ All models failed"
        else:
            variance = max(valid_scores) - min(valid_scores)
            recommendation = self._get_recommendation(variance)

        return {
            "results": results,
            "variance": variance,
            "recommendation": recommendation,
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


def load_cv_text() -> str:
    """Load CV from data/cv.json and convert to text."""
    cv_path = Path("data/cv.json")
    if not cv_path.exists():
        raise FileNotFoundError(f"CV file not found: {cv_path}")

    with open(cv_path) as f:
        cv_data = json.load(f)

    # Extract text from CV JSON (jRES format)
    lines = []
    basics = cv_data.get("basics", {})
    lines.append(f"{basics.get('name', 'Unknown')}")
    lines.append(f"{basics.get('label', '')}")
    if basics.get("summary"):
        lines.append(f"\n{basics['summary']}")

    # Add work experience
    for job in cv_data.get("work", []):
        lines.append(f"\n{job.get('name', '')}: {job.get('position', '')}")
        if job.get("summary"):
            lines.append(job["summary"])
        if job.get("technologies"):
            lines.append(f"Tech: {', '.join(job['technologies'])}")

    # Add skills
    if cv_data.get("skills"):
        lines.append("\nSkills:")
        for skill in cv_data["skills"]:
            lines.append(f"- {skill.get('name', '')}: {', '.join(skill.get('keywords', []))}")

    return "\n".join(lines)


def load_first_job_chunks() -> list:
    """Load first job chunks from data/extracted_jobs/preprocessed_jobs.json.

    Returns chunks list (same format used by assess command).
    """
    job_path = Path("data/extracted_jobs/preprocessed_jobs.json")
    if not job_path.exists():
        raise FileNotFoundError(f"Jobs file not found: {job_path}")

    with open(job_path) as f:
        jobs = json.load(f)

    if not jobs or not isinstance(jobs, list):
        raise ValueError("No jobs found in preprocessed_jobs.json")

    job = jobs[0]
    # Use chunks (same as assess command: preprocessed.get("chunks", [clean_text]))
    chunks = job.get("chunks")

    if not chunks:
        raise ValueError("First job has no chunks")

    return chunks


@pytest.mark.integration
def test_model_comparison(tmp_path):
    """Run model comparison on real CV + job data."""
    import os

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    # Load real data
    logger.info("Loading CV and job chunks...")
    try:
        cv_text = load_cv_text()
        job_chunks = load_first_job_chunks()
    except FileNotFoundError as e:
        pytest.skip(f"Data files not found: {e}")
        return

    logger.info(f"CV length: {len(cv_text)} chars")
    logger.info(f"Job chunks: {len(job_chunks)} chunks, total {sum(len(c) for c in job_chunks)} chars")

    comparator = LLMComparator(api_key)
    result = comparator.compare_models(cv_text, job_chunks)

    # Save results
    report_path = tmp_path / "model_comparison.json"
    with open(report_path, "w") as f:
        json.dump(result, f, indent=2, default=str)

    logger.info(f"\n\n{'='*70}")
    logger.info("MODEL COMPARISON RESULTS")
    logger.info("="*70)

    for model, scores in result["results"].items():
        if scores is None:
            logger.error(f"\n{model.upper()}: FAILED")
            continue

        logger.info(f"\n{model.upper()}:")
        logger.info(
            f"  Overall: {scores['overall_score']} | "
            f"Tech: {scores['tech_score']} | "
            f"Seniority: {scores['seniority_score']} | "
            f"Location: {scores['location_score']}"
        )
        logger.info(f"  Tokens: {scores['input_tokens']} in, {scores['output_tokens']} out")
        logger.info(f"  Summary: {scores['summary'][:80]}...")

    logger.info(f"\nVariance (score range): {result['variance']:.1f} points")
    logger.info(f"Recommendation: {result['recommendation']}")
    logger.info(f"Report saved: {report_path}\n")

    return result


if __name__ == "__main__":
    import sys

    # Run manually: python -m tests.test_llm_comparison
    pytest.main([__file__, "-v", "-s"])
