"""Job table widget for displaying assessment results."""

from typing import Any, Dict, Optional

from textual.widgets import DataTable
from textual.widgets.data_table import RowKey

from src.tui.models.state import StateManager
from src.tui.utils.formatters import truncate


class JobTable(DataTable[str]):
    """Sortable table of jobs with assessment scores.

    Features:
    - Display job title, company, scores
    - Press Enter to expand/collapse details
    - Track expanded row for detail panel integration
    """

    def __init__(
        self, state: StateManager, *args: Any, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.state = state
        self.expanded_job_id: Optional[str] = None
        self.job_rows: Dict[RowKey, Dict[str, Any]] = {}
        self.all_jobs: list[Dict[str, Any]] = []
        self.search_query: str = ""
        self.status_filter: Optional[str] = None

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

    def update_rows(self, jobs: list[Dict[str, Any]]) -> None:
        """Populate table with job data."""
        self.all_jobs = jobs
        self._apply_filters()

    def _apply_filters(self) -> None:
        """Apply search and status filters, then render table."""
        filtered = self.all_jobs

        # Apply search filter
        if self.search_query:
            query_lower = self.search_query.lower()
            filtered = [
                j
                for j in filtered
                if query_lower in j.get("title", "").lower()
                or query_lower in j.get("company", "").lower()
                or query_lower in j.get("location", "").lower()
            ]

        # Apply status filter
        if self.status_filter:
            filtered = [j for j in filtered if j.get("status") == self.status_filter]

        # Clear and re-render table
        self.clear()
        self.job_rows.clear()

        for job in filtered:
            title = truncate(job.get("title", ""), max_len=35)
            company = truncate(job.get("company", ""), max_len=20)
            overall = f"{job.get('overall_score', 0):.0f}"
            tech = f"{job.get('tech_score', 0):.0f}"
            seniority = f"{job.get('seniority_score', 0):.0f}"
            location = truncate(job.get("location", ""), max_len=15)

            row_key = self.add_row(title, company, overall, tech, seniority, location)
            self.job_rows[row_key] = job

    def filter_by_search(self, query: str) -> None:
        """Filter jobs by search query (title/company/location)."""
        self.search_query = query
        self._apply_filters()

    def filter_by_status(self, status: Optional[str]) -> None:
        """Filter jobs by status (None to clear)."""
        self.status_filter = status
        self._apply_filters()

    def clear_filters(self) -> None:
        """Clear all filters and show all jobs."""
        self.search_query = ""
        self.status_filter = None
        self._apply_filters()

    def get_filtered_count(self) -> int:
        """Get count of currently displayed jobs."""
        return len(self.job_rows)

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
