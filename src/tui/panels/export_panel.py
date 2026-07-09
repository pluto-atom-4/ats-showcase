"""Panel for export phase display."""

from src.tui.models.state import StateManager
from src.tui.panels.base import BasePanelWidget
from src.tui.utils.formatters import format_progress_bar


class ExportPanel(BasePanelWidget):
    """Displays export phase progress."""

    def __init__(self, state: StateManager, **kwargs):
        super().__init__(state, phase="export", **kwargs)

    def render(self) -> str:
        """Render export panel content."""
        metrics = self.state.phase_metrics["export"]

        lines = [
            self.render_phase_header(),
        ]

        if metrics.total_items > 0:
            bar = format_progress_bar(metrics.progress_percent, width=50)
            lines.append(bar)

        lines.append(self.render_phase_metrics())

        # Show export-specific info
        lines.append(f"Reports generated: {metrics.processed_items}")

        return "\n".join(lines)
