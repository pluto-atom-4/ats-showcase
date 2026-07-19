# TUI Architecture (StateManager & Dashboard)

Textual-based TUI for ATS Playground workflow. Replaces verbose CLI output with interactive dashboard.

**Tech Stack:** Textual 0.42+, Rich 13.0+, Pydantic 2.5+

---

## StateManager: Source-of-Truth

Centralized state for entire workflow.

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class PhaseStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"

@dataclass
class PhaseMetrics:
    total_items: int = 0
    processed_items: int = 0
    failed_items: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_tokens: int = 0
    total_cost_usd: float = 0.0

    @property
    def progress_percent(self) -> float:
        return (self.processed_items / self.total_items * 100) if self.total_items else 0.0

    @property
    def eta_seconds(self) -> float:
        if not self.items_per_second: return 0.0
        return (self.total_items - self.processed_items) / self.items_per_second

    @property
    def items_per_second(self) -> float:
        elapsed = (self.end_time or datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        return self.processed_items / elapsed if elapsed else 0.0

class StateManager:
    """Track phase status, metrics, job data, cost."""
    
    def __init__(self):
        self.phase_status: Dict[str, PhaseStatus] = {
            "crawl": PhaseStatus.IDLE,
            "preprocess": PhaseStatus.IDLE,
            "assess": PhaseStatus.IDLE,
            "export": PhaseStatus.IDLE,
        }
        self.phase_metrics: Dict[str, PhaseMetrics] = {
            phase: PhaseMetrics() for phase in self.phase_status
        }
        self.jobs: Dict[str, dict] = {}
        self.top_matches: List[dict] = []
        self.current_errors: List[str] = []
        self.paused = False

    def start_phase(self, phase: str, total_items: int) -> None:
        self.phase_status[phase] = PhaseStatus.RUNNING
        self.phase_metrics[phase] = PhaseMetrics(total_items=total_items)
        self.phase_metrics[phase].start_time = datetime.now()

    def increment_phase_progress(self, phase: str, tokens: int = 0, cost: float = 0.0) -> None:
        metrics = self.phase_metrics[phase]
        metrics.processed_items += 1
        metrics.total_tokens += tokens
        metrics.total_cost_usd += cost

    def complete_phase(self, phase: str) -> None:
        metrics = self.phase_metrics[phase]
        metrics.end_time = datetime.now()
        self.phase_status[phase] = PhaseStatus.COMPLETED

    @property
    def total_cost_usd(self) -> float:
        return sum(m.total_cost_usd for m in self.phase_metrics.values())
```

**⚠️ THREAD SAFETY:** StateManager not thread-safe. Use `@work(exclusive=True)` to prevent race conditions.

---

## Dashboard Layout

Main Textual App orchestrating panels and state.

```python
from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Vertical

class ATPDashboard(Screen):
    """
    Main TUI Dashboard.

    Layout:
    ┌──────────────────────────────┐
    │ Header (status, total cost)   │
    ├──────────────────────────────┤
    │ Phase Indicator               │
    ├──────────────────────────────┤
    │ Active Panel (crawl|prep|...) │
    │ - Progress bar + metrics      │
    │ - Job list / job details      │
    │ - Cost tracker                │
    ├──────────────────────────────┤
    │ Footer [p]ause [q]uit         │
    └──────────────────────────────┘
    """

    def __init__(self, state: StateManager):
        super().__init__()
        self.state = state
        self.current_phase = "crawl"

    def compose(self) -> ComposeResult:
        yield HeaderPanel(self.state, id="header")
        yield PhaseIndicator(self.state, id="phase-indicator")
        with Vertical(id="content"):
            yield CrawlPanel(self.state, id="crawl-panel")
            yield PreprocessPanel(self.state, id="preprocess-panel", visible=False)
            yield AssessPanel(self.state, id="assess-panel", visible=False)
            yield ExportPanel(self.state, id="export-panel", visible=False)

    @work(exclusive=True)
    async def run_workflow(self) -> None:
        """Run phases asynchronously, updating state."""
        try:
            await self._phase_crawl()
            await self._phase_preprocess()
            await self._phase_assess()
            await self._phase_export()
        except Exception as e:
            self.state.error_phase("export", str(e))

    def action_pause_resume(self) -> None:
        self.state.paused = not self.state.paused

    BINDINGS = [
        ("p", "pause_resume", "Pause/Resume"),
        ("q", "quit_workflow", "Quit"),
    ]
```

---

## Panel Pattern (Base Class)

All phase panels inherit from BasePanelWidget.

```python
from textual.containers import Container

class BasePanelWidget(Container):
    """Base for phase-specific panels (crawl, preprocess, assess, export)."""

    DEFAULT_CSS = """
    BasePanelWidget {
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }
    """

    def __init__(self, state: StateManager, phase: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = state
        self.phase = phase

    def on_mount(self) -> None:
        self.set_interval(0.5, self._update_display)

    def _update_display(self) -> None:
        """Refresh display from state every 500ms."""
        metrics = self.state.phase_metrics[self.phase]
        status = self.state.phase_status[self.phase]
        # Update widgets based on metrics
```

**Update Frequency:** 0.5s (2 Hz), not 60 FPS. Prevents flicker.

---

## Integration with CLI

Detect TUI vs text mode:

```python
import sys

@app.command()
async def all(cv: str, config: str, tui: Optional[bool] = None) -> None:
    """Run full workflow."""
    if tui is None:
        tui = sys.stdout.isatty() and sys.stdin.isatty()  # Auto-detect

    if tui:
        state = StateManager()
        app = ATPDashboard(state)
        app.run()
    else:
        # Existing text-based workflow
        pass
```

**Auto-detection:** TTY + stdin/stdout → TUI; otherwise text mode.

---

## Related

- **Widgets:** See `tui/widgets.md` (ProgressBar, JobTable, CostTracker)
- **Patterns:** See `tui/patterns.md` (Textual, async, testing, error handling)
- **Full Reference:** Original `tui.md` (this file is condensed)

---

**Last Updated:** 2026-07-19  
**Status:** Core concepts documented; full implementation in reference file
