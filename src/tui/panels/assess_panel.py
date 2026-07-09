"""Panel for assess phase display with top matches."""

from src.tui.models.state import StateManager
from src.tui.panels.base import BasePanelWidget
from src.tui.utils.formatters import format_progress_bar, truncate


class AssessPanel(BasePanelWidget):
    """Displays assessment phase progress and top 5 job matches."""

    def __init__(self, state: StateManager, **kwargs):
        super().__init__(state, phase="assess", **kwargs)

    def render(self) -> str:
        """Render assess panel with top matches table."""
        metrics = self.state.phase_metrics["assess"]

        lines = [
            self.render_phase_header(),
        ]

        if metrics.total_items > 0:
            bar = format_progress_bar(metrics.progress_percent, width=50)
            lines.append(bar)

        lines.append(self.render_phase_metrics())

        # Show top 5 matches as a simple table
        if self.state.top_matches:
            lines.append("\n🏆 Top Matches:")
            lines.append(
                "  {:<40} | {:>6} | {:>6}".format("Job Title", "Score", "Tech")
            )
            lines.append("  " + "-" * 58)

            for match in self.state.top_matches:
                title = truncate(match.get("title", "Unknown"), max_len=40)
                score = match.get("overall_score", 0)
                tech = match.get("tech_score", 0)
                lines.append(f"  {title:<40} | {score:>6.0f} | {tech:>6.0f}")

        return "\n".join(lines)
