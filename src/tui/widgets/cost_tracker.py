"""Cost tracking widget displaying tokens and USD."""

from textual.widgets import Static

from src.tui.models.state import StateManager
from src.tui.utils.formatters import format_cost, format_tokens


class CostTracker(Static):
    """Real-time cost display for tokens and USD."""

    def __init__(self, state: StateManager, phase: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = state
        self.phase = phase

    def render(self) -> str:
        """Render cost tracking info."""
        metrics = self.state.phase_metrics[self.phase]

        tokens_str = format_tokens(metrics.total_tokens)
        cost_str = format_cost(metrics.total_cost_usd)

        return f"💰 {tokens_str} tokens | {cost_str}"
