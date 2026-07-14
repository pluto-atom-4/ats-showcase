"""Phase indicator widget showing status of all workflow phases."""

from textual.widgets import Static

from src.tui.models.state import PhaseStatus, StateManager


class PhaseIndicator(Static):
    """Displays status of all 4 workflow phases."""

    def __init__(self, state: StateManager, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = state

    def on_mount(self) -> None:
        """Subscribe to state changes and set refresh interval."""
        self.state.subscribe(self._on_state_change)
        self.set_interval(0.5, self.refresh)

    def _on_state_change(self, phase: str) -> None:
        """Handle state change notification."""
        self.refresh()

    def get_phase_indicator(self, phase: str) -> str:
        """Get status indicator for one phase."""
        status = self.state.phase_status[phase]
        emoji = {
            PhaseStatus.IDLE: "⚪",
            PhaseStatus.RUNNING: "⏳",
            PhaseStatus.PAUSED: "⏸️",
            PhaseStatus.COMPLETED: "✓",
            PhaseStatus.ERROR: "❌",
        }.get(status, "?")

        label = phase.capitalize()
        return f"{emoji} {label}"

    def render(self) -> str:
        """Render all phase statuses in a row."""
        indicators = [
            self.get_phase_indicator("crawl"),
            self.get_phase_indicator("preprocess"),
            self.get_phase_indicator("assess"),
            self.get_phase_indicator("export"),
        ]
        return "  |  ".join(indicators)
