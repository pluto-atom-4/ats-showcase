"""Data structures for integrity checking and reporting."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class IntegrityIssue:
    """Single integrity anomaly detected during checks."""

    issue_type: str  # 'orphaned_assessment', 'invalid_score', 'malformed_json', etc.
    severity: str  # 'error', 'warning', 'info'
    table: str  # 'assessments', 'preprocessed_jobs', 'cost_tracking', etc.
    record_id: str  # job_id, assessment_id, or primary key
    details: str  # Error message or anomaly description
    suggested_action: str  # 'Delete orphaned record', 'Set recommendations to NULL', etc.


@dataclass
class IntegrityReport:
    """Aggregated results from a full integrity check."""

    timestamp: datetime
    total_checks: int
    issues_found: List[IntegrityIssue] = field(default_factory=list)
    summary_by_type: Dict[str, int] = field(default_factory=dict)
    total_records_affected: int = 0
    export_path: Optional[str] = None
    purge_recommendations: List[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        """Count of issues with severity='error'."""
        return sum(1 for issue in self.issues_found if issue.severity == "error")

    @property
    def warning_count(self) -> int:
        """Count of issues with severity='warning'."""
        return sum(1 for issue in self.issues_found if issue.severity == "warning")

    @property
    def info_count(self) -> int:
        """Count of issues with severity='info'."""
        return sum(1 for issue in self.issues_found if issue.severity == "info")
