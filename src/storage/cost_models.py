"""Data models for cost analysis and comparison reporting."""

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class ReprocessingMetrics:
    """Metrics for a single re-preprocessing run."""

    job_id: str
    preprocessing_version_before: str
    preprocessing_version_after: str
    tokens_before: int
    tokens_after: int
    estimated_cost_before: float
    estimated_cost_after: float
    timestamp: Optional[str] = None

    @property
    def tokens_saved(self) -> int:
        """Calculate tokens saved by re-preprocessing."""
        return self.tokens_before - self.tokens_after

    @property
    def cost_saved_usd(self) -> float:
        """Calculate USD cost saved by re-preprocessing."""
        return self.estimated_cost_before - self.estimated_cost_after

    @property
    def token_reduction_percent(self) -> float:
        """Calculate token reduction as percentage."""
        if self.tokens_before == 0:
            return 0.0
        return ((self.tokens_before - self.tokens_after) / self.tokens_before) * 100


@dataclass
class CostComparisonReport:
    """Comprehensive cost analysis report for v1.0 vs v2.0 preprocessing."""

    total_jobs_v1_0: int = 0
    total_jobs_v2_0: int = 0
    total_tokens_v1_0: int = 0
    total_tokens_v2_0: int = 0
    estimated_savings_usd: float = 0.0
    avg_tokens_per_job_v1_0: float = 0.0
    avg_tokens_per_job_v2_0: float = 0.0
    jobs_already_migrated: int = 0
    jobs_pending_migration: int = 0
    reprocessing_runs: List[ReprocessingMetrics] = field(default_factory=list)
    total_reprocessing_cost_saved: float = 0.0
    total_reprocessing_tokens_saved: int = 0

    @property
    def avg_token_reduction_percent(self) -> float:
        """Calculate average token reduction percentage across all re-preprocessing runs."""
        if not self.reprocessing_runs:
            return 0.0
        if self.total_tokens_v1_0 == 0:
            return 0.0
        return (
            (self.total_reprocessing_tokens_saved / self.total_tokens_v1_0) * 100 if self.total_tokens_v1_0 > 0 else 0.0
        )

    @property
    def migration_progress_percent(self) -> float:
        """Calculate migration progress as percentage."""
        total = self.total_jobs_v1_0 + self.total_jobs_v2_0
        if total == 0:
            return 0.0
        return (self.total_jobs_v2_0 / total) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary for serialization."""
        return {
            "total_jobs_v1_0": self.total_jobs_v1_0,
            "total_jobs_v2_0": self.total_jobs_v2_0,
            "total_tokens_v1_0": self.total_tokens_v1_0,
            "total_tokens_v2_0": self.total_tokens_v2_0,
            "estimated_savings_usd": round(self.estimated_savings_usd, 6),
            "avg_tokens_per_job_v1_0": round(self.avg_tokens_per_job_v1_0, 2),
            "avg_tokens_per_job_v2_0": round(self.avg_tokens_per_job_v2_0, 2),
            "jobs_already_migrated": self.jobs_already_migrated,
            "jobs_pending_migration": self.jobs_pending_migration,
            "total_reprocessing_cost_saved": round(self.total_reprocessing_cost_saved, 6),
            "total_reprocessing_tokens_saved": self.total_reprocessing_tokens_saved,
            "avg_token_reduction_percent": round(self.avg_token_reduction_percent, 2),
            "migration_progress_percent": round(self.migration_progress_percent, 2),
            "reprocessing_runs": len(self.reprocessing_runs),
        }


@dataclass
class QualityImpactMetrics:
    """Metrics for a single quality impact comparison."""

    job_id: str
    preprocessing_version_before: str
    preprocessing_version_after: str
    previous_assessment_score: int
    new_assessment_score: int
    timestamp: Optional[str] = None

    @property
    def score_delta(self) -> int:
        """Calculate score change (new - old)."""
        return self.new_assessment_score - self.previous_assessment_score

    @property
    def is_regression(self) -> bool:
        """Determine if score declined (regression risk)."""
        return self.score_delta < 0

    @property
    def is_improvement(self) -> bool:
        """Determine if score improved."""
        return self.score_delta > 0


@dataclass
class QualityComparisonReport:
    """Comprehensive quality impact analysis for re-preprocessed jobs."""

    total_comparisons: int = 0
    avg_score_before: float = 0.0
    avg_score_after: float = 0.0
    score_improved: int = 0
    score_declined: int = 0
    score_unchanged: int = 0
    max_score_improvement: int = 0
    max_score_decline: int = 0
    regression_risk_jobs: List[str] = field(default_factory=list)
    quality_metrics: List[QualityImpactMetrics] = field(default_factory=list)

    @property
    def regression_risk_percent(self) -> float:
        """Calculate percentage of re-processed jobs with score decline."""
        if self.total_comparisons == 0:
            return 0.0
        return (self.score_declined / self.total_comparisons) * 100

    @property
    def improvement_rate(self) -> float:
        """Calculate percentage of re-processed jobs with score improvement."""
        if self.total_comparisons == 0:
            return 0.0
        return (self.score_improved / self.total_comparisons) * 100

    @property
    def avg_score_delta(self) -> float:
        """Calculate average score delta."""
        if self.total_comparisons == 0:
            return 0.0
        return sum(m.score_delta for m in self.quality_metrics) / self.total_comparisons

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary for serialization."""
        return {
            "total_comparisons": self.total_comparisons,
            "avg_score_before": round(self.avg_score_before, 2),
            "avg_score_after": round(self.avg_score_after, 2),
            "score_improved": self.score_improved,
            "score_declined": self.score_declined,
            "score_unchanged": self.score_unchanged,
            "max_score_improvement": self.max_score_improvement,
            "max_score_decline": self.max_score_decline,
            "regression_risk_percent": round(self.regression_risk_percent, 2),
            "improvement_rate": round(self.improvement_rate, 2),
            "avg_score_delta": round(self.avg_score_delta, 2),
            "regression_risk_jobs_count": len(self.regression_risk_jobs),
            "regression_risk_jobs": self.regression_risk_jobs[:20],
        }
