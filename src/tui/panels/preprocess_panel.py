"""Panel for preprocess phase display."""

from src.tui.models.state import StateManager
from src.tui.panels.base import BasePanelWidget
from src.tui.utils.formatters import format_progress_bar


class PreprocessPanel(BasePanelWidget):
    """Displays preprocess phase progress."""

    def __init__(self, state: StateManager, **kwargs):
        super().__init__(state, phase="preprocess", **kwargs)

    def render(self) -> str:
        """Render preprocess panel content."""
        metrics = self.state.phase_metrics["preprocess"]

        lines = [
            self.render_phase_header(),
        ]

        if metrics.total_items > 0:
            bar = format_progress_bar(metrics.progress_percent, width=50)
            lines.append(bar)

        lines.append(self.render_phase_metrics())

        # Show preprocessing-specific stats
        if metrics.processed_items > 0:
            avg_tokens = metrics.total_tokens / metrics.processed_items
            lines.append(f"Avg tokens/job: {avg_tokens:.0f}")

        return "\n".join(lines)
