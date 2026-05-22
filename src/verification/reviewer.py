"""Interactive CLI for user verification of extracted jobs."""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class JobReviewer:
    """Interactive CLI for reviewing and confirming extracted jobs before LLM assessment."""

    def __init__(self):
        """Initialize job reviewer."""
        pass

    async def review_job(
        self,
        job: Dict[str, Any],
        preprocessed: Optional[Dict[str, Any]] = None,
        cost_estimate: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Interactively review a single job posting.

        Shows job details, token count, and cost estimate. Prompts user to:
        - Approve for LLM assessment
        - Edit/clarify details
        - Reject the job

        Args:
            job: Job posting dict
            preprocessed: Optional preprocessed job data
            cost_estimate: Optional cost estimate in USD

        Returns:
            Updated job dict with user decision
        """
        # TODO: Implement interactive review with Typer prompts
        logger.info(f"Reviewing job: {job.get('title')}")
        return job

    async def review_batch(
        self,
        jobs: List[Dict[str, Any]],
        preprocessed_map: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Review multiple jobs with batch actions.

        Args:
            jobs: List of job postings
            preprocessed_map: Optional map of job_id -> preprocessed data

        Returns:
            Dict of {approved: [...], rejected: [...], edited: [...]}
        """
        # TODO: Implement batch review with filtering/selection
        logger.info(f"Reviewing batch of {len(jobs)} jobs")
        return {"approved": [], "rejected": [], "edited": []}

    def show_cost_summary(self, total_jobs: int, total_tokens: int, total_cost: float) -> None:
        """
        Display cost summary before proceeding to LLM assessment.

        Args:
            total_jobs: Number of jobs to assess
            total_tokens: Total tokens to send to LLM
            total_cost: Total estimated cost in USD
        """
        # TODO: Implement cost summary display
        logger.info(f"Cost summary: {total_jobs} jobs, {total_tokens} tokens, ${total_cost:.2f}")
