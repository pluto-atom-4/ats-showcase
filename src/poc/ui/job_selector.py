"""TUI job selector application using Textual."""

import argparse
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Footer, Header, Input, SelectionList, Static

from src.poc.ui.exporter import export_jobs
from src.poc.ui.loader import Job, load_jobs

DEFAULT_OUTPUT_PATH = Path("data/work/selected.json")
DEFAULT_INPUT_DIR = Path("data/extracted_jobs")


def format_job_row(job: Job) -> str:
    """Format a job for display in SelectionList (posted_date | title | company | location | status).

    Args:
        job: Job to format.

    Returns:
        Formatted string with pipe-separated fields, column-aligned.
    """
    # Use fixed column widths for alignment
    posted_date = (job.get("posted_date") or "-")[:15].ljust(15)
    title = job["title"][:70].ljust(70)
    company = job["company"][:20].ljust(20)
    location = job["location"][:20].ljust(20)
    status = job["status"][:15].ljust(15)

    return f"{posted_date} | {title} | {company} | {location} | {status}"


class WarningBanner(Static):
    """Static widget to display loading warnings."""

    DEFAULT_CSS = """
    WarningBanner {
        width: 100%;
        height: auto;
        background: $warning;
        color: $text;
        border: solid $warning;
        content-align: left middle;
        padding: 0 1;
    }
    """

    def __init__(self, warnings: list[str]) -> None:
        """Initialize with warnings."""
        super().__init__()
        self.warnings = warnings

    def render(self) -> str:
        """Render warning messages."""
        if not self.warnings:
            return ""
        msg = f"⚠ {len(self.warnings)} warning(s): {'; '.join(self.warnings[:2])}"
        if len(self.warnings) > 2:
            msg += f" (+{len(self.warnings) - 2} more)"
        return msg


class JobSelectorApp(App):
    """Main TUI application for selecting jobs."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("c", "clear_selection", "Clear"),
        ("a", "select_all", "Select All"),
        ("e", "export_selected", "Export"),
    ]

    CSS = """
    Screen {
        layout: vertical;
    }

    Header {
        height: 1;
        background: $boost;
        color: $text;
    }

    #job_list {
        height: 1fr;
        border: solid $primary;
    }

    #filter_input {
        height: 3;
        border: solid $accent;
    }

    #status_bar {
        height: 1;
        background: $boost;
        color: $text;
    }

    Footer {
        height: auto;
    }
    """

    def __init__(
        self,
        jobs: list[Job] | None = None,
        warnings: list[str] | None = None,
        output_path: Path = DEFAULT_OUTPUT_PATH,
        input_dir: Path = DEFAULT_INPUT_DIR,
    ) -> None:
        """Initialize with jobs and output path.

        Args:
            jobs: Optional list of jobs (loaded from disk if not provided).
            warnings: Optional list of warnings from loading.
            output_path: Path where to save selected jobs.
            input_dir: Directory to load jobs from.
        """
        super().__init__()
        self.output_path = output_path
        self.input_dir = input_dir
        self.all_jobs = jobs or []
        self.all_warnings = warnings or []
        self.filter_text = ""

    def compose(self) -> ComposeResult:
        """Compose the UI widgets."""
        yield Header(show_clock=False)

        if self.all_warnings:
            yield WarningBanner(self.all_warnings)

        with Container(id="main_container"):
            yield Input(
                id="filter_input",
                placeholder="Type to filter jobs (title/company/location)...",
            )

            yield SelectionList[str](id="job_list")

            yield Static(id="status_bar", classes="status_bar")

        yield Footer()

    def on_mount(self) -> None:
        """Load jobs and populate selection list."""
        # Load jobs if not provided at init
        if not self.all_jobs:
            result = load_jobs(self.input_dir)
            self.all_jobs = result.jobs
            self.all_warnings = result.warnings

        # Initial population
        self._update_job_list()
        self._update_status_bar()

    def _update_job_list(self) -> None:
        """Populate job list based on current filter."""
        job_list = self.query_one("#job_list", SelectionList)
        job_list.clear_options()

        # Filter jobs
        filtered_jobs = self._get_filtered_jobs()

        # Add formatted job options
        for job in filtered_jobs:
            row_text = format_job_row(job)
            job_id = job["id"]
            # Add option with job ID as value
            job_list.add_option((row_text, job_id))

    def _get_filtered_jobs(self) -> list[Job]:
        """Get jobs matching current filter."""
        if not self.filter_text:
            return self.all_jobs

        filter_lower = self.filter_text.lower()
        return [
            job
            for job in self.all_jobs
            if any(filter_lower in field.lower() for field in [job["title"], job["company"], job["location"]])
        ]

    def _update_status_bar(self) -> None:
        """Update status bar with selection count."""
        job_list = self.query_one("#job_list", SelectionList)
        filtered = self._get_filtered_jobs()
        # Count selected items (values in the SelectionList)
        total_selected = len(job_list.selected)
        status_bar = self.query_one("#status_bar", Static)
        status_bar.update(
            f"Jobs: {len(filtered)} of {len(self.all_jobs)} | Selected: {total_selected} | "
            f"[a] Select All | [c] Clear | [e] Export | [q] Quit"
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle filter input changes."""
        self.filter_text = event.value
        self._update_job_list()
        self._update_status_bar()

    def on_selection_list_selected_changed(self, event: SelectionList.SelectedChanged) -> None:
        """Handle Space bar selection changes in SelectionList.

        This event fires when the user presses Space to toggle selection.

        Args:
            event: Selection change event from SelectionList.
        """
        # Update status bar to reflect the new selection state
        self._update_status_bar()

    def action_select_all(self) -> None:
        """Select all visible jobs."""
        job_list = self.query_one("#job_list", SelectionList)
        filtered = self._get_filtered_jobs()

        # Build set of job IDs in filtered view
        filtered_ids = {job["id"] for job in filtered}

        # Select all job IDs for jobs in the current filtered list
        for idx in range(job_list.option_count):
            # Get the job ID from the option value
            option = job_list.get_option_at_index(idx)
            job_id = option.value
            if job_id in filtered_ids:
                # Select if not already selected
                if job_id not in job_list.selected:
                    job_list.select(job_id)

        self._update_status_bar()

    def action_clear_selection(self) -> None:
        """Clear all selections."""
        job_list = self.query_one("#job_list", SelectionList)

        # Collect selected values (job IDs) to avoid modification during iteration
        selected_values = list(job_list.selected)

        # Deselect all
        for value in selected_values:
            job_list.deselect(value)

        self._update_status_bar()

    def action_export_selected(self) -> None:
        """Export selected jobs to JSON file.

        Reads selection state from the SelectionList widget (source of truth).
        Ensures 'description' field is present (defaults to null) for batch processing compatibility.
        """
        job_list = self.query_one("#job_list", SelectionList)

        # Get selected job IDs directly from widget
        # job_list.selected returns list of job_id values
        selected_job_ids = set(job_list.selected)

        # Filter to selected jobs
        selected_jobs = [j for j in self.all_jobs if j["id"] in selected_job_ids]

        if not selected_jobs:
            self.notify("No jobs selected to export.", title="Export", timeout=3)
            return

        # Ensure all jobs have 'description' field (required by batch_processor)
        # Default to null if not present
        for job in selected_jobs:
            if "description" not in job:
                job["description"] = None

        # Export
        try:
            export_jobs(selected_jobs, self.output_path)
            self.notify(
                f"Exported {len(selected_jobs)} jobs to {self.output_path}",
                title="Export Complete",
                timeout=5,
            )
        except Exception as e:
            self.notify(
                f"Export failed: {e}",
                title="Export Error",
                timeout=5,
            )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:] if None).

    Returns:
        Parsed arguments as Namespace.
    """
    parser = argparse.ArgumentParser(description="Interactive TUI job selector for extracted job listings.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Directory containing extracted job JSON files (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Output path for selected jobs JSON (default: {DEFAULT_OUTPUT_PATH})",
    )
    return parser.parse_args(argv)


def main() -> None:
    """Run the job selector TUI."""
    args = parse_args()

    # Validate input directory exists and is a directory
    if not args.input_dir.exists():
        print(f"Error: Input directory does not exist: {args.input_dir}", file=sys.stderr)
        sys.exit(1)

    if not args.input_dir.is_dir():
        print(f"Error: Input path is not a directory: {args.input_dir}", file=sys.stderr)
        sys.exit(1)

    # Warn if output path exists as directory (but don't fail)
    if args.output_path.exists() and args.output_path.is_dir():
        print(f"Warning: Output path is a directory, not a file: {args.output_path}", file=sys.stderr)

    app = JobSelectorApp(input_dir=args.input_dir, output_path=args.output_path)
    app.run()


if __name__ == "__main__":
    main()
