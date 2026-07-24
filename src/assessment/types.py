"""Type definitions for assessment module."""

from typing import Any, Dict, TypedDict


class EntityScore(TypedDict):
    """Entity-based scoring results."""

    skill_match: float
    tech_match: float
    requirements_match: float
    overall_entity_score: float


class CostTracking(TypedDict):
    """Cost tracking for API calls."""

    estimated_input: int
    estimated_output: int
    estimated_cost_usd: float
    actual_input: int
    actual_output: int
    actual_cost_usd: float


class AssessmentMetadata(TypedDict):
    """Metadata about assessment execution."""

    model: str
    api_call_time_ms: int
    attempt: int


class AssessmentResult(TypedDict):
    """Complete assessment with entity scoring and metrics."""

    assessment: Dict[str, Any]
    entity_score: EntityScore
    cost_tracking: CostTracking
    token_savings_percent: float
    metadata: AssessmentMetadata
