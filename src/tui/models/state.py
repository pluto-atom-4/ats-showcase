"""Centralized state management for TUI dashboard.

⚠️ THREAD SAFETY: StateManager is NOT thread-safe. Use @work(exclusive=True)
when mutating StateManager from async tasks to prevent race conditions.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class PhaseStatus(str, Enum):
    """Phase lifecycle stages."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class PhaseMetrics:
    """Metrics for a single phase."""

    total_items: int = 0
    processed_items: int = 0
    failed_items: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_tokens: int = 0
    total_cost_usd: float = 0.0

    @property
    def progress_percent(self) -> float:
        """Percentage progress (0-100)."""
        if self.total_items == 0:
            return 0.0
        return (self.processed_items / self.total_items) * 100

    @property
    def elapsed_seconds(self) -> float:
        """Seconds elapsed in phase."""
        if self.start_time is None:
            return 0.0
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

    @property
    def items_per_second(self) -> float:
        """Throughput: items/sec."""
        elapsed = self.elapsed_seconds
        if elapsed == 0:
            return 0.0
        return self.processed_items / elapsed

    @property
    def eta_seconds(self) -> float:
        """Estimated seconds to completion."""
        remaining = self.total_items - self.processed_items
        if self.items_per_second == 0:
            return 0.0
        return remaining / self.items_per_second


class StateManager:
    """
    Centralized state for TUI.

    Tracks progress across all workflow phases (crawl, preprocess, assess, export),
    accumulates metrics (tokens, cost), and maintains job data.

    Usage:
        state = StateManager()
        state.start_phase("crawl", total_items=42)
        state.increment_phase_progress("crawl", tokens=150, cost=0.0005)
        state.complete_phase("crawl")
    """

    def __init__(self) -> None:
        self.phase_status: Dict[str, PhaseStatus] = {
            "crawl": PhaseStatus.IDLE,
            "preprocess": PhaseStatus.IDLE,
            "assess": PhaseStatus.IDLE,
            "export": PhaseStatus.IDLE,
        }
        self.phase_metrics: Dict[str, PhaseMetrics] = {
            phase: PhaseMetrics() for phase in self.phase_status
        }
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.top_matches: List[Dict[str, Any]] = []
        self.current_errors: List[str] = []
        self.paused = False

    def start_phase(self, phase: str, total_items: int) -> None:
        """Mark phase as running, set total item count."""
        self.phase_status[phase] = PhaseStatus.RUNNING
        self.phase_metrics[phase] = PhaseMetrics(total_items=total_items)
        self.phase_metrics[phase].start_time = datetime.now()

    def increment_phase_progress(
        self,
        phase: str,
        tokens: int = 0,
        cost: float = 0.0,
        error: Optional[str] = None,
    ) -> None:
        """Record successful processing of one item."""
        metrics = self.phase_metrics[phase]
        metrics.processed_items += 1
        metrics.total_tokens += tokens
        metrics.total_cost_usd += cost

        if error:
            metrics.failed_items += 1
            self.current_errors.append(error)

    def complete_phase(self, phase: str) -> None:
        """Mark phase as complete."""
        metrics = self.phase_metrics[phase]
        metrics.end_time = datetime.now()
        self.phase_status[phase] = PhaseStatus.COMPLETED

    def error_phase(self, phase: str, error: str) -> None:
        """Mark phase as failed with error."""
        metrics = self.phase_metrics[phase]
        metrics.end_time = datetime.now()
        self.phase_status[phase] = PhaseStatus.ERROR
        self.current_errors.append(error)

    def add_job(self, job_id: str, title: str, company: str, **kwargs: Any) -> None:
        """Register a job being processed."""
        self.jobs[job_id] = {
            "id": job_id,
            "title": title,
            "company": company,
            "status": "pending",
            **kwargs,
        }

    def update_job(self, job_id: str, **updates: Any) -> None:
        """Update job data."""
        if job_id in self.jobs:
            self.jobs[job_id].update(updates)

    def update_top_matches(self, matches: List[Dict[str, Any]]) -> None:
        """Update top 5 jobs by overall_score."""
        self.top_matches = sorted(
            matches,
            key=lambda x: x.get("overall_score", 0),
            reverse=True,
        )[:5]

    @property
    def total_tokens_used(self) -> int:
        """Sum tokens across all phases."""
        return sum(m.total_tokens for m in self.phase_metrics.values())

    @property
    def total_cost_usd(self) -> float:
        """Sum cost across all phases."""
        return sum(m.total_cost_usd for m in self.phase_metrics.values())
