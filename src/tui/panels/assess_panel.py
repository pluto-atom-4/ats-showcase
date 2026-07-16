"""Panel for assess phase display with expandable job details."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from src.tui.dialogs.job_details import JobDetailsPanel
from src.tui.models.state import StateManager
from src.tui.panels.base import BasePanelWidget
from src.tui.utils.formatters import format_progress_bar
from src.tui.widgets.job_table import JobTable
from src.tui.widgets.search_input import FilterBar, SearchInput


class AssessPanel(BasePanelWidget):
    """Displays assessment phase progress with expandable job details.

    Features:
    - Progress bar and metrics
    - JobTable with all assessed jobs
    - Press Enter on row to expand full assessment details
    - JobDetailsPanel shows scores, reasoning, recommendations
    """

    CSS = """
    AssessPanel #search-filter-bar {
        height: 2;
        border: solid $accent;
        padding: 0;
    }

    AssessPanel #search-filter-bar > Input {
        margin: 0;
    }
    """

    def __init__(self, state: StateManager, **kwargs: object) -> None:
        super().__init__(state, phase="assess", **kwargs)
        self.job_table: JobTable | None = None
        self.details_panel: JobDetailsPanel | None = None

    def compose(self) -> ComposeResult:
        """Render assess panel with table and expandable details."""
        # Header with progress
        yield Static(id="assess-header")

        # Search and filter inputs
        with Vertical(id="search-filter-bar"):
            yield SearchInput(id="job-search")
            yield FilterBar(id="job-filter")

        # Job table
        self.job_table = JobTable(self.state, id="assess-table")
        yield self.job_table

        # Details panel (hidden by default, shown when row expanded)
        self.details_panel = JobDetailsPanel("", {})
        self.details_panel.styles.display = "none"
        yield self.details_panel

    def on_mount(self) -> None:
        """Subscribe to state changes."""
        super().on_mount()
        self._update_table()

    def _on_state_change(self, phase: str) -> None:
        """Handle state change and update table."""
        if phase == "assess":
            self._update_table()
            self.refresh()

    def _update_table(self) -> None:
        """Update job table with current jobs."""
        if self.job_table is None:
            return

        # Filter jobs that have been assessed (have overall_score)
        assessed_jobs = [
            job
            for job in self.state.jobs.values()
            if job.get("overall_score") is not None
        ]

        # Sort by score descending
        assessed_jobs.sort(
            key=lambda j: j.get("overall_score", 0), reverse=True
        )

        self.job_table.update_rows(assessed_jobs)

    def _update_details_panel(self) -> None:
        """Show/hide details panel based on expanded job."""
        if self.details_panel is None or self.job_table is None:
            return

        expanded_job = self.job_table.get_expanded_job()
        if expanded_job:
            job_id = expanded_job.get("id", "")
            self.details_panel = JobDetailsPanel(job_id, expanded_job)
            self.details_panel.styles.display = "block"
            self.refresh()
        else:
            if self.details_panel:
                self.details_panel.styles.display = "none"
            self.refresh()

    def action_toggle_expand(self) -> None:
        """Toggle expansion of currently selected job (Enter key)."""
        if self.job_table:
            self.job_table.toggle_expand_current()
            self._update_details_panel()

    def on_search_input_search_changed(self, message: SearchInput.SearchChanged) -> None:
        """Handle search input changes."""
        if self.job_table:
            self.job_table.filter_by_search(message.query)
            self.refresh()

    def on_filter_bar_filter_changed(self, message: FilterBar.FilterChanged) -> None:
        """Handle filter bar changes (status:confirmed, status:rejected, etc)."""
        if self.job_table:
            # Parse filter string (e.g., "status:confirmed")
            filter_str = message.filters.strip()
            if filter_str.startswith("status:"):
                status = filter_str.replace("status:", "").strip()
                self.job_table.filter_by_status(status if status else None)
            elif not filter_str:
                self.job_table.clear_filters()
            self.refresh()

    def render(self) -> str:
        """Render header section of assess panel."""
        metrics = self.state.phase_metrics["assess"]

        lines = [
            self.render_phase_header(),
        ]

        if metrics.total_items > 0:
            bar = format_progress_bar(metrics.progress_percent, width=50)
            lines.append(bar)

        lines.append(self.render_phase_metrics())
        lines.append("[b]Press [Enter] to expand job details[/b]")

        return "\n".join(lines)

    BINDINGS = [
        ("enter", "toggle_expand", "Expand"),
    ]
