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
        from src.tui.utils.formatters import format_cost, format_tokens

        metrics = self.state.phase_metrics["export"]

        lines = [
            self.render_phase_header(),
        ]

        if metrics.total_items > 0:
            bar = format_progress_bar(metrics.progress_percent, width=50)
            lines.append(bar)

        lines.append(self.render_phase_metrics())

        # Show accumulated totals from all prior phases
        prior_phases = ["crawl", "preprocess", "assess"]
        prior_tokens = sum(
            self.state.phase_metrics[p].total_tokens for p in prior_phases
        )
        prior_cost = sum(
            self.state.phase_metrics[p].total_cost_usd for p in prior_phases
        )

        if prior_tokens > 0 or prior_cost > 0:
            lines.append("")
            lines.append("Accumulated (from prior phases):")
            lines.append(
                f"  Tokens: {format_tokens(prior_tokens)} | Cost: {format_cost(prior_cost)}"
            )

        # Show export-specific info
        lines.append(f"Reports generated: {metrics.processed_items}")

        return "\n".join(lines)
