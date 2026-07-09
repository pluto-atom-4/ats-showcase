"""Custom progress bar widget with ETA."""

from textual.widgets import Static

from src.tui.models.state import StateManager
from src.tui.utils.formatters import (
    format_eta,
    format_progress_bar,
    format_speed,
)


class TUIProgressBar(Static):
    """Custom progress bar with ETA and throughput display."""

    def __init__(self, state: StateManager, phase: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = state
        self.phase = phase

    def render(self) -> str:
        """Render progress bar with metrics."""
        metrics = self.state.phase_metrics[self.phase]

        if metrics.total_items == 0:
            return f"{self.phase}: No items to process"

        bar = format_progress_bar(metrics.progress_percent, width=40)
        percent_str = f"{metrics.progress_percent:.0f}%"
        count_str = f"({metrics.processed_items}/{metrics.total_items})"

        line = f"{bar} {percent_str} {count_str}"

        if metrics.progress_percent > 0 and metrics.progress_percent < 100:
            if metrics.items_per_second > 0:
                speed = format_speed(metrics.items_per_second)
                eta = format_eta(metrics.eta_seconds)
                line += f" | {speed} | ETA: {eta}"

        return line
