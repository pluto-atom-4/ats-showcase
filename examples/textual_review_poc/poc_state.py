"""Minimal state tracker for PoC (no threading, just decisions)."""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class JobDecision:
    """Single job decision."""

    job_id: str
    title: str
    company: str
    decision: Optional[str] = None  # "confirm" | "reject" | "skip" | None


class PoCStateManager:
    """Track job review decisions (minimal variant for proof)."""

    def __init__(self):
        self.jobs: Dict[str, JobDecision] = {}
        self.current_idx: int = 0

    def add_job(self, job_id: str, title: str, company: str) -> None:
        """Add mock job."""
        self.jobs[job_id] = JobDecision(
            job_id=job_id, title=title, company=company, decision=None
        )

    def record_decision(self, job_id: str, decision: Optional[str]) -> None:
        """Save decision for job."""
        if job_id in self.jobs:
            self.jobs[job_id].decision = decision

    def summary(self) -> str:
        """Print summary of decisions."""
        confirmed = sum(1 for j in self.jobs.values() if j.decision == "confirm")
        rejected = sum(1 for j in self.jobs.values() if j.decision == "reject")
        skipped = sum(1 for j in self.jobs.values() if j.decision == "skip")
        pending = sum(1 for j in self.jobs.values() if j.decision is None)

        return (
            f"📊 Review Summary\n"
            f"  Confirmed: {confirmed}\n"
            f"  Rejected: {rejected}\n"
            f"  Skipped: {skipped}\n"
            f"  Pending: {pending}\n"
            f"\n"
            f"Details:\n"
        ) + "\n".join(
            f"  {j.job_id}: {j.title} ({j.company}) → {j.decision or 'no decision'}"
            for j in self.jobs.values()
        )
