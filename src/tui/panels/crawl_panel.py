"""Panel for crawl phase display."""

from src.tui.models.state import PhaseStatus, StateManager
from src.tui.panels.base import BasePanelWidget
from src.tui.utils.formatters import format_progress_bar


class CrawlPanel(BasePanelWidget):
    """Displays crawl phase progress."""

    def __init__(self, state: StateManager, **kwargs):
        super().__init__(state, phase="crawl", **kwargs)

    def render(self) -> str:
        """Render crawl panel content."""
        metrics = self.state.phase_metrics["crawl"]
        status = self.state.phase_status["crawl"]

        lines = [
            self.render_phase_header(),
        ]

        if status == PhaseStatus.RUNNING and metrics.processed_items == 0:
            lines.append("⏳ Initializing crawler...")
        elif metrics.total_items > 0:
            bar = format_progress_bar(metrics.progress_percent, width=50)
            lines.append(bar)

        lines.append(self.render_phase_metrics())

        if self.state.current_errors:
            lines.append("\n⚠️  Errors:")
            for error in self.state.current_errors[-3:]:  # Show last 3 errors
                lines.append(f"  • {error}")

        return "\n".join(lines)
