"""Job table widget for displaying assessment results."""

from typing import Any, Dict, Optional

from textual.widgets import DataTable

from src.tui.models.state import StateManager
from src.tui.utils.formatters import truncate


class JobTable(DataTable):
    """Sortable table of jobs with assessment scores.

    Features:
    - Display job title, company, scores
    - Press Enter to expand/collapse details
    - Track expanded row for detail panel integration
    """

    def __init__(self, state: StateManager, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = state
        self.expanded_job_id: Optional[str] = None
        self.job_rows: Dict[str, Dict[str, Any]] = {}  # Map row_key to job data

    def on_mount(self) -> None:
        """Setup table columns."""
        self.add_columns(
            "Title",
            "Company",
            "Overall",
            "Tech",
            "Seniority",
            "Location",
        )

    def update_rows(self, jobs: list) -> None:
        """Populate table with job data."""
        self.clear()
        self.job_rows.clear()

        for job in jobs:
            title = truncate(job.get("title", ""), max_len=35)
            company = truncate(job.get("company", ""), max_len=20)
            overall = f"{job.get('overall_score', 0):.0f}"
            tech = f"{job.get('tech_score', 0):.0f}"
            seniority = f"{job.get('seniority_score', 0):.0f}"
            location = truncate(job.get("location", ""), max_len=15)

            row_key = self.add_row(title, company, overall, tech, seniority, location)
            self.job_rows[row_key] = job

    def get_expanded_job(self) -> Optional[Dict[str, Any]]:
        """Get currently expanded job data, or None."""
        if self.expanded_job_id is None:
            return None
        return self.state.jobs.get(self.expanded_job_id)

    def get_selected_job(self) -> Optional[Dict[str, Any]]:
        """Get job data for currently selected row."""
        if self.cursor_row >= len(self.job_rows):
            return None

        # Get row key from current cursor position
        row_keys = list(self.job_rows.keys())
        if self.cursor_row < len(row_keys):
            return self.job_rows[row_keys[self.cursor_row]]
        return None

    def toggle_expand_current(self) -> bool:
        """Toggle expansion of currently selected job.

        Returns True if now expanded, False if collapsed.
        """
        job = self.get_selected_job()
        if not job:
            return False

        job_id = job.get("id")
        if self.expanded_job_id == job_id:
            self.expanded_job_id = None
            return False
        else:
            self.expanded_job_id = job_id
            return True
