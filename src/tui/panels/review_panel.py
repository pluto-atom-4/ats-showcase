"""Review phase panel for TUI - shows job validation progress."""

from textual.widgets import Static

from src.tui.models.state import StateManager


class ReviewPanel(Static):
    """Displays review phase progress and statistics."""

    DEFAULT_CSS = """
    ReviewPanel {
        border: solid $primary;
        padding: 1;
        height: auto;
    }

    ReviewPanel > .review-header {
        height: auto;
        border-bottom: solid $accent;
    }

    ReviewPanel > .review-stats {
        height: auto;
        margin-top: 1;
    }
    """

    def __init__(self, state: StateManager, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = state

    def render(self) -> str:
        """Render review panel with current progress."""
        metrics = self.state.phase_metrics["review"]
        status = self.state.phase_status["review"]

        lines = [
            f"🔍 REVIEW PHASE | Status: {status.value.upper()}",
            "",
        ]

        if metrics.total_items == 0:
            lines.append("No jobs to review")
        else:
            progress_pct = metrics.progress_percent
            bar_width = 40
            filled = int((progress_pct / 100) * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)

            lines.append(f"Progress: {bar} {progress_pct:.0f}%")
            lines.append(
                f"({metrics.processed_items}/{metrics.total_items} reviewed)"
            )

            if metrics.items_per_second > 0:
                eta = metrics.eta_seconds
                lines.append(f"ETA: {eta:.0f}s | Speed: {metrics.items_per_second:.1f} jobs/s")

        return "\n".join(lines)
