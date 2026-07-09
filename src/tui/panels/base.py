"""Base panel widget for TUI phases."""

from textual.containers import Container

from src.tui.models.state import PhaseStatus, StateManager


class BasePanelWidget(Container):
    """Base class for workflow phase panels.

    Each panel displays phase progress with:
    - Header: title + status
    - Content: phase-specific metrics
    - Footer: cost summary
    """

    DEFAULT_CSS = """
    BasePanelWidget {
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }
    """

    def __init__(
        self,
        state: StateManager,
        *args,
        phase: str = "unknown",
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.state = state
        self.phase = phase

    def get_phase_title(self) -> str:
        """Get phase display title."""
        titles = {
            "crawl": "🕷️  CRAWL",
            "preprocess": "📄 PREPROCESS",
            "assess": "🎯 ASSESS",
            "export": "📊 EXPORT",
        }
        return titles.get(self.phase, self.phase.upper())

    def get_status_emoji(self) -> str:
        """Get emoji for phase status."""
        status = self.state.phase_status[self.phase]
        emojis = {
            PhaseStatus.IDLE: "⚪",
            PhaseStatus.RUNNING: "⏳",
            PhaseStatus.PAUSED: "⏸️",
            PhaseStatus.COMPLETED: "✓",
            PhaseStatus.ERROR: "❌",
        }
        return emojis.get(status, "?")

    def render_phase_header(self) -> str:
        """Render standard phase header."""
        status = self.state.phase_status[self.phase]
        metrics = self.state.phase_metrics[self.phase]

        header = (
            f"{self.get_status_emoji()} {self.get_phase_title()} "
            f"| {status.value.upper()}"
        )

        if metrics.total_items > 0:
            header += f" | {metrics.processed_items}/{metrics.total_items}"

        return header

    def render_phase_metrics(self) -> str:
        """Render standard metrics line."""
        metrics = self.state.phase_metrics[self.phase]
        from src.tui.utils.formatters import format_cost, format_tokens

        line = f"Tokens: {format_tokens(metrics.total_tokens)} | Cost: {format_cost(metrics.total_cost_usd)}"

        if metrics.progress_percent > 0 and metrics.progress_percent < 100:
            from src.tui.utils.formatters import format_eta, format_speed

            if metrics.items_per_second > 0:
                line += f" | Speed: {format_speed(metrics.items_per_second)}"
                line += f" | ETA: {format_eta(metrics.eta_seconds)}"

        return line
