"""End-to-end job assessment with entity-based scoring and token tracking."""

import logging
from typing import List, Tuple

from src.assessment.data_reshaper import DataReshaper
from src.assessment.llm_integration import LLMProvider
from src.assessment.types import AssessmentResult, EntityScore
from src.tokenization.counter import TokenCounter
from src.tokenization.preprocessor import Preprocessor

logger = logging.getLogger(__name__)

_token_counter = TokenCounter()


class Assessor:
    """Assess job-CV fit with entity-based scoring and token savings measurement."""

    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20241022",
        use_examples: bool = False,
    ):
        """Initialize assessor with LLM provider and preprocessors.

        Args:
            model: Claude model to use (default: Sonnet 3.5)
            use_examples: Include few-shot examples in prompt (better accuracy, more tokens)
        """
        self.llm_provider = LLMProvider(model=model)
        self.preprocessor = Preprocessor()
        self.data_reshaper = DataReshaper()
        self.use_examples = use_examples
        self.model = model
        logger.info(f"Assessor initialized: model={model}, examples={use_examples}")

    def assess_job(
        self,
        cv_text: str,
        job_description: str,
    ) -> AssessmentResult:
        """Assess job-CV fit with entity scoring and token metrics.

        Full workflow:
        1. Extract entities from CV and job description
        2. Compute entity-based match scores
        3. Chunk job description for semantic relevance
        4. Call LLM with prepared prompt
        5. Measure token savings vs baseline
        6. Return consolidated assessment

        Args:
            cv_text: CV text
            job_description: Job description text

        Returns:
            AssessmentResult with assessment, entity_score, cost tracking, token savings

        Raises:
            ValueError: If CV or job description empty
            anthropic.AuthenticationError: Invalid API key
            anthropic.RateLimitError: Rate limited after retries
        """
        if not cv_text or not cv_text.strip():
            raise ValueError("CV text cannot be empty")
        if not job_description or not job_description.strip():
            raise ValueError("Job description cannot be empty")

        # Extract entities
        cv_skills, cv_tech, cv_reqs = self.preprocessor.extract_entities(cv_text)
        job_skills, job_tech, job_reqs = self.preprocessor.extract_entities(
            job_description
        )

        logger.debug(
            f"CV entities: {len(cv_skills)} skills, {len(cv_tech)} tech, {len(cv_reqs)} reqs"
        )
        logger.debug(
            f"Job entities: {len(job_skills)} skills, {len(job_tech)} tech, "
            f"{len(job_reqs)} reqs"
        )

        # Compute entity-based scoring
        entity_score = self._compute_entity_score(
            (cv_skills, cv_tech, cv_reqs), (job_skills, job_tech, job_reqs)
        )

        # Prepare semantic chunks
        chunks = self.data_reshaper.chunk_by_sentences(job_description)
        logger.debug(f"Created {len(chunks)} semantic chunks")

        # Estimate baseline (raw text without chunks)
        baseline_tokens = self._estimate_baseline_tokens(cv_text, job_description)
        logger.debug(f"Baseline tokens (raw): {baseline_tokens}")

        # Call LLM
        llm_result = self.llm_provider.assess_job(
            cv_text, job_description, use_examples=self.use_examples
        )

        # Measure token savings
        actual_input = llm_result["cost_tracking"]["actual_input"]
        savings_percent = (
            (1.0 - (actual_input / baseline_tokens)) * 100
            if baseline_tokens > 0
            else 0.0
        )

        logger.info(
            f"Assessment complete: entity_score={entity_score['overall_entity_score']:.1f}, "
            f"baseline={baseline_tokens}t, actual={actual_input}t, "
            f"savings={savings_percent:.1f}%"
        )

        # Consolidate result
        return {
            "assessment": llm_result["assessment"],
            "entity_score": entity_score,
            "cost_tracking": llm_result["cost_tracking"],
            "token_savings_percent": savings_percent,
            "metadata": llm_result["metadata"],
        }

    def _compute_entity_score(
        self,
        cv_entities: Tuple[List[str], List[str], List[str]],
        job_entities: Tuple[List[str], List[str], List[str]],
    ) -> EntityScore:
        """Compute entity-based match scores.

        Measures overlap between CV and job entities across 3 dimensions:
        - Skill match: how many CV skills are in job requirements
        - Tech match: how many CV tech stack items match job tech
        - Requirements match: how many CV entities cover job requirements

        Args:
            cv_entities: Tuple of (CV skills, CV tech, CV requirements)
            job_entities: Tuple of (job skills, job tech, job requirements)

        Returns:
            EntityScore with skill_match, tech_match, requirements_match, overall
        """
        cv_skills, cv_tech, cv_reqs = cv_entities
        job_skills, job_tech, job_reqs = job_entities

        # Convert to lowercase sets for comparison
        cv_skills_lower = {s.lower() for s in cv_skills}
        cv_tech_lower = {t.lower() for t in cv_tech}
        cv_all_lower = cv_skills_lower | cv_tech_lower

        job_skills_lower = {s.lower() for s in job_skills}
        job_tech_lower = {t.lower() for t in job_tech}
        job_all_lower = job_skills_lower | job_tech_lower

        # Compute individual scores
        skill_match = (
            (len(cv_skills_lower & job_skills_lower) / len(job_skills_lower) * 100)
            if job_skills_lower
            else 100.0
        )

        tech_match = (
            (len(cv_tech_lower & job_tech_lower) / len(job_tech_lower) * 100)
            if job_tech_lower
            else 100.0
        )

        requirements_match = (
            (len(cv_all_lower & job_all_lower) / len(job_all_lower) * 100)
            if job_all_lower
            else 100.0
        )

        overall = (skill_match + tech_match + requirements_match) / 3.0

        return {
            "skill_match": min(100.0, skill_match),
            "tech_match": min(100.0, tech_match),
            "requirements_match": min(100.0, requirements_match),
            "overall_entity_score": min(100.0, overall),
        }

    def _estimate_baseline_tokens(self, cv_text: str, job_description: str) -> int:
        """Estimate tokens if raw (non-chunked) text were sent.

        Baseline = CV + job description without semantic chunking.
        Used to compute token_savings_percent.

        Args:
            cv_text: CV text
            job_description: Job description text

        Returns:
            Estimated tokens for raw text
        """
        full_text = f"{cv_text}\n{job_description}"
        return _token_counter.count_tokens(full_text)
