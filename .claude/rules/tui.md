# TUI Implementation Rules

Detailed patterns for building Textual-based Text User Interface for ATS Playground workflow orchestration.

**Related**: See GitHub Issue #89 for context and rationale.
**Architecture**: See DESIGN.md § Semantic Design Tokens for StateManager, Panel, Widget, and Async Workflow roles.
**Constraints**: See DESIGN.md § Anti-Patterns & Boundaries for critical "never" behaviors (single-writer, no StateManager mutation from multiple tasks, no blocking main thread).

## Architecture Overview

The TUI replaces verbose CLI text output with an interactive dashboard that:
1. Shows real-time progress (crawl, preprocess, assess, export phases)
2. Tracks token count + cost accumulation live
3. Displays top job matches inline
4. Allows pause/resume/cancel operations
5. Provides interactive job approval/rejection

### Tech Stack

```
┌─────────────────────────┐
│   src/cli.py (Typer)    │ --tui flag routes to TUI
├─────────────────────────┤
│  src/tui/dashboard.py   │ Main Textual App (async-aware)
│    (Textual.App)        │
├─────────────────────────┤
│  State Management       │ StateManager tracks progress, errors
│  (src/tui/models/)      │
├─────────────────────────┤
│  UI Components          │ Panels, widgets, dialogs
│  (src/tui/panels/*,     │
│   src/tui/widgets/*)    │
└─────────────────────────┘
```

**Key Dependency Versions:**
```toml
textual = "^0.42.0"          # TUI framework (async-ready)
rich = "^13.0"               # Rich formatting (shipped with textual)
pydantic = "^2.5.0"          # State models
```

## Directory Structure

```
src/tui/
├── __init__.py
├── dashboard.py              # Main Textual App
├── keybindings.py           # Global keybinding handlers
├── models/
│   ├── __init__.py
│   ├── state.py             # StateManager class
│   ├── types.py             # Pydantic models (TUIJob, Phase, etc.)
│   └── events.py            # Custom event classes
├── panels/
│   ├── __init__.py
│   ├── base.py              # BasePanelWidget (shared behavior)
│   ├── header.py            # Header with title, progress summary
│   ├── crawl_panel.py       # Crawl phase panel
│   ├── preprocess_panel.py  # Preprocess phase panel
│   ├── assess_panel.py      # Assess phase panel + top matches
│   └── export_panel.py      # Export phase panel
├── widgets/
│   ├── __init__.py
│   ├── progress_bar.py      # Custom progress bar with ETA
│   ├── cost_tracker.py      # Running cost display (tokens, USD)
│   ├── job_table.py         # Sortable/searchable job list
│   ├── phase_indicator.py   # Status of each phase (running/done/error)
│   └── log_viewer.py        # Scrollable log display
├── dialogs/
│   ├── __init__.py
│   ├── job_review.py        # Inline job approval dialog
│   ├── config_wizard.py     # Interactive config setup
│   └── error_dialog.py      # Error details popup
└── utils/
    ├── __init__.py
    └── formatters.py        # Formatting helpers (tokens, USD, truncate, etc.)

tests/tui/
├── test_dashboard.py        # Dashboard initialization
├── test_state.py            # StateManager state transitions
├── test_panels.py           # Panel rendering
└── test_widgets.py          # Widget interactions
```

## Core Classes

### StateManager (src/tui/models/state.py)

Manages all TUI state: progress, job data, cost tracking.

```python
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Optional, Dict, List

class PhaseStatus(str, Enum):
    """Phase lifecycle stages."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"

@dataclass
class PhaseMetrics:
    """Metrics for a single phase."""
    total_items: int = 0
    processed_items: int = 0
    failed_items: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_tokens: int = 0
    total_cost_usd: float = 0.0

    @property
    def progress_percent(self) -> float:
        if self.total_items == 0:
            return 0.0
        return (self.processed_items / self.total_items) * 100

    @property
    def elapsed_seconds(self) -> float:
        """Seconds elapsed in phase."""
        if self.start_time is None:
            return 0.0
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

    @property
    def items_per_second(self) -> float:
        """Throughput: items/sec."""
        elapsed = self.elapsed_seconds
        if elapsed == 0:
            return 0.0
        return self.processed_items / elapsed

    @property
    def eta_seconds(self) -> float:
        """Estimated seconds to completion."""
        remaining = self.total_items - self.processed_items
        if self.items_per_second == 0:
            return 0.0
        return remaining / self.items_per_second

class StateManager:
    """
    Centralized state for TUI.

    Usage:
        state = StateManager()
        state.phase_status["crawl"] = PhaseStatus.RUNNING
        state.increment_phase_progress("crawl", tokens=150, cost=0.0005)

    ⚠️ THREAD SAFETY: StateManager is NOT thread-safe. Use @work(exclusive=True)
    to prevent race conditions when multiple async tasks access state.
    See DESIGN.md § Anti-Patterns for details.
    """

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
        self.jobs: Dict[str, dict] = {}  # job_id → TUIJob dict
        self.top_matches: List[dict] = []  # Top 5 assessed jobs
        self.current_errors: List[str] = []  # Recent errors
        self.paused = False

    def start_phase(self, phase: str, total_items: int) -> None:
        """Mark phase as running, set total item count."""
        self.phase_status[phase] = PhaseStatus.RUNNING
        self.phase_metrics[phase] = PhaseMetrics(total_items=total_items)
        self.phase_metrics[phase].start_time = datetime.now()

    def increment_phase_progress(
        self,
        phase: str,
        tokens: int = 0,
        cost: float = 0.0,
        error: Optional[str] = None
    ) -> None:
        """Record successful processing of one item."""
        metrics = self.phase_metrics[phase]
        metrics.processed_items += 1
        metrics.total_tokens += tokens
        metrics.total_cost_usd += cost

        if error:
            metrics.failed_items += 1
            self.current_errors.append(error)

    def complete_phase(self, phase: str) -> None:
        """Mark phase as complete."""
        metrics = self.phase_metrics[phase]
        metrics.end_time = datetime.now()
        self.phase_status[phase] = PhaseStatus.COMPLETED

    def error_phase(self, phase: str, error: str) -> None:
        """Mark phase as failed with error."""
        metrics = self.phase_metrics[phase]
        metrics.end_time = datetime.now()
        self.phase_status[phase] = PhaseStatus.ERROR
        self.current_errors.append(error)

    def add_job(self, job_id: str, title: str, company: str, **kwargs) -> None:
        """Register a job being processed."""
        self.jobs[job_id] = {
            "id": job_id,
            "title": title,
            "company": company,
            "status": "pending",
            **kwargs
        }

    def update_job(self, job_id: str, **updates) -> None:
        """Update job data."""
        if job_id in self.jobs:
            self.jobs[job_id].update(updates)

    def update_top_matches(self, matches: List[dict]) -> None:
        """Update top 5 jobs by overall_score."""
        self.top_matches = sorted(
            matches,
            key=lambda x: x.get("overall_score", 0),
            reverse=True
        )[:5]

    @property
    def total_tokens_used(self) -> int:
        """Sum tokens across all phases."""
        return sum(m.total_tokens for m in self.phase_metrics.values())

    @property
    def total_cost_usd(self) -> float:
        """Sum cost across all phases."""
        return sum(m.total_cost_usd for m in self.phase_metrics.values())
```

### Dashboard (src/tui/dashboard.py)

Main Textual App orchestrating panels and state.

```python
from textual.app import ComposeResult, on
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual import work
from asyncio import gather

from .models.state import StateManager, PhaseStatus
from .panels.header import HeaderPanel
from .panels.crawl_panel import CrawlPanel
from .panels.preprocess_panel import PreprocessPanel
from .panels.assess_panel import AssessPanel
from .panels.export_panel import ExportPanel
from .widgets.phase_indicator import PhaseIndicator

class ATPDashboard(Screen):
    """
    Main TUI Dashboard for ATS Playground workflow.

    Layout:
    ┌─────────────────────────────────────┐
    │  Header: Workflow Status, Total Cost │
    ├─────────────────────────────────────┤
    │ Phase Indicator (Crawl | Prep | ...) │
    ├─────────────────────────────────────┤
    │                                       │
    │  Active Panel (based on phase)        │
    │  - CrawlPanel                        │
    │  - PreprocessPanel                   │
    │  - AssessPanel                       │
    │  - ExportPanel                       │
    │                                       │
    ├─────────────────────────────────────┤
    │ Footer: [p]ause [r]esume [q]uit      │
    └─────────────────────────────────────┘
    """

    CSS = """
    Screen {
        layout: vertical;
    }

    #header {
        height: 3;
        border: solid $primary;
    }

    #phase-indicator {
        height: 1;
        background: $boost;
    }

    #content {
        border: solid $primary;
        height: 1fr;
    }

    #footer {
        height: 1;
        background: $boost;
    }
    """

    def __init__(self, state: StateManager):
        super().__init__()
        self.state = state
        self.current_phase = "crawl"

    def compose(self) -> ComposeResult:
        """Render dashboard layout."""
        yield HeaderPanel(self.state, id="header")
        yield PhaseIndicator(self.state, id="phase-indicator")

        with Vertical(id="content"):
            yield CrawlPanel(self.state, id="crawl-panel")
            yield PreprocessPanel(self.state, id="preprocess-panel", visible=False)
            yield AssessPanel(self.state, id="assess-panel", visible=False)
            yield ExportPanel(self.state, id="export-panel", visible=False)

        yield Container(id="footer")

    def on_mount(self) -> None:
        """Initialize workflow async tasks."""
        self.run_workflow()

    @work(exclusive=True)
    async def run_workflow(self) -> None:
        """
        Run complete workflow asynchronously.

        Updates UI via state changes, which trigger screen redraws.
        """
        try:
            await self._phase_crawl()
            await self._phase_preprocess()
            await self._phase_assess()
            await self._phase_export()
        except Exception as e:
            self.state.error_phase("export", str(e))
            self.notify(f"Workflow failed: {e}", severity="error")

    async def _phase_crawl(self) -> None:
        """Execute crawl phase asynchronously."""
        self._show_panel("crawl-panel")
        # Crawl logic here, updating state as jobs are processed
        # Example:
        # from browser.crawler import Crawler
        # crawler = Crawler(headless=True)
        # results = await crawler.crawl_multiple(companies)
        # for company, jobs in results.items():
        #     for job in jobs:
        #         self.state.add_job(job.id, job.title, job.company)
        #         self.state.increment_phase_progress("crawl", tokens=0)
        pass

    async def _phase_preprocess(self) -> None:
        """Execute preprocess phase."""
        self._show_panel("preprocess-panel")
        # Preprocessing logic with token tracking
        pass

    async def _phase_assess(self) -> None:
        """Execute assess phase."""
        self._show_panel("assess-panel")
        # Assessment logic with cost tracking
        pass

    async def _phase_export(self) -> None:
        """Execute export phase."""
        self._show_panel("export-panel")
        # Export logic
        pass

    def _show_panel(self, panel_id: str) -> None:
        """Show one panel, hide others."""
        for panel_name in ["crawl-panel", "preprocess-panel", "assess-panel", "export-panel"]:
            panel = self.query_one(f"#{panel_name}")
            panel.visible = (panel_name == panel_id)

    def action_pause_resume(self) -> None:
        """Toggle pause on workflow."""
        self.state.paused = not self.state.paused
        verb = "Paused" if self.state.paused else "Resumed"
        self.notify(f"{verb} workflow")

    def action_quit_workflow(self) -> None:
        """Exit dashboard, ask for confirmation if running."""
        if any(s == PhaseStatus.RUNNING for s in self.state.phase_status.values()):
            self.app.exit(message="Workflow still running, use [p] to pause first")
        else:
            self.app.exit()

    BINDINGS = [
        ("p", "pause_resume", "Pause/Resume"),
        ("q", "quit_workflow", "Quit"),
        ("l", "scroll_logs", "Logs"),
    ]
```

### BasePanelWidget (src/tui/panels/base.py)

Shared panel behavior.

```python
from textual.containers import Container
from textual.widgets import Static
from .models.state import StateManager, PhaseStatus

class BasePanelWidget(Container):
    """
    Base class for phase panels.

    Each panel:
    - Displays phase progress
    - Shows real-time metrics (tokens, cost, ETA)
    - Renders job list or phase summary
    """

    DEFAULT_CSS = """
    BasePanelWidget {
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }

    BasePanelWidget > .phase-header {
        height: 2;
        border-bottom: solid $accent;
    }

    BasePanelWidget > .phase-content {
        height: 1fr;
    }

    BasePanelWidget > .phase-footer {
        height: 1;
        border-top: solid $accent;
    }
    """

    def __init__(self, state: StateManager, phase: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = state
        self.phase = phase

    def render(self) -> str:
        """Override in subclasses to render phase-specific content."""
        status = self.state.phase_status[self.phase]
        metrics = self.state.phase_metrics[self.phase]

        lines = [
            f"Phase: {self.phase.upper()} | Status: {status.value}",
            f"Progress: {metrics.progress_percent:.0f}% | Tokens: {metrics.total_tokens} | "
            f"Cost: ${metrics.total_cost_usd:.6f}",
        ]

        if status == PhaseStatus.RUNNING and metrics.items_per_second > 0:
            eta = metrics.eta_seconds
            lines.append(f"ETA: {eta:.0f}s | Speed: {metrics.items_per_second:.1f} items/s")

        return "\n".join(lines)
```

### Specific Panels

#### CrawlPanel (src/tui/panels/crawl_panel.py)

```python
from textual.containers import Container, Horizontal
from textual.widgets import Static
from ..models.state import StateManager, PhaseStatus
from ..widgets.progress_bar import TUIProgressBar
from ..widgets.cost_tracker import CostTracker
from .base import BasePanelWidget

class CrawlPanel(BasePanelWidget):
    """
    Displays crawl phase progress.

    Shows:
    - Company count
    - Jobs extracted per company
    - Progress bar with ETA
    - Running cost
    - Errors (if any)
    """

    def __init__(self, state: StateManager, *args, **kwargs):
        super().__init__(state, phase="crawl", *args, **kwargs)

    def compose(self):
        """Layout: header, progress bar, job list, cost tracker, errors."""
        yield Static(id="crawl-header")
        yield TUIProgressBar(self.state, "crawl", id="crawl-progress")
        yield Static(id="crawl-jobs")  # Scrollable job list
        yield CostTracker(self.state, "crawl", id="crawl-cost")
        yield Static(id="crawl-errors")  # Error log

    def on_mount(self) -> None:
        """Bind to state updates."""
        self.set_interval(0.5, self._update_display)

    def _update_display(self) -> None:
        """Refresh display from state."""
        metrics = self.state.phase_metrics["crawl"]
        status = self.state.phase_status["crawl"]

        header = self.query_one("#crawl-header", Static)
        header.update(
            f"🕷️ CRAWL PHASE | {status.value.upper()}\n"
            f"Companies: {metrics.total_items} | "
            f"Jobs Extracted: {metrics.processed_items} | "
            f"Failed: {metrics.failed_items}"
        )
```

#### AssessPanel (src/tui/panels/assess_panel.py)

```python
from textual.widgets import Static, DataTable
from ..models.state import StateManager
from ..widgets.job_table import JobTable
from .base import BasePanelWidget

class AssessPanel(BasePanelWidget):
    """
    Displays assessment phase and top matches.

    Shows:
    - Assessment progress bar (current/total jobs)
    - Top 5 job matches (sortable by score)
    - Running token count + cost
    - Per-job assessment score
    """

    def __init__(self, state: StateManager, *args, **kwargs):
        super().__init__(state, phase="assess", *args, **kwargs)

    def compose(self):
        """Layout: header, progress, job table, cost tracker."""
        yield Static(id="assess-header")
        yield JobTable(self.state, id="assess-table")
        yield Static(id="assess-summary")

    def _update_table(self) -> None:
        """Refresh job table from top_matches."""
        table = self.query_one("#assess-table", JobTable)
        table.update_rows(self.state.top_matches)
```

## Widget Patterns

### ProgressBar (src/tui/widgets/progress_bar.py)

```python
from textual.widgets import ProgressBar
from ..models.state import StateManager, PhaseMetrics

class TUIProgressBar(ProgressBar):
    """
    Custom progress bar with ETA and throughput.

    Example output:
      Crawl: ████████░░░░░░░░░░░░ 45% (90/200 jobs)
      ETA: 2m 15s | Speed: 10.5 jobs/min
    """

    def __init__(self, state: StateManager, phase: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = state
        self.phase = phase

    def render(self) -> str:
        """Render progress bar with ETA."""
        metrics = self.state.phase_metrics[self.phase]

        if metrics.total_items == 0:
            return f"{self.phase}: No items to process"

        # Build progress bar
        bar_width = 40
        filled = int((metrics.progress_percent / 100) * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)

        eta_str = f"ETA: {metrics.eta_seconds / 60:.0f}m" if metrics.eta_seconds > 0 else "ETA: --"
        speed_str = f"Speed: {metrics.items_per_second:.1f}/s" if metrics.items_per_second > 0 else ""

        return (
            f"{self.phase.upper()}: {bar} {metrics.progress_percent:.0f}%\n"
            f"({metrics.processed_items}/{metrics.total_items}) | {eta_str} | {speed_str}"
        )
```

### JobTable (src/tui/widgets/job_table.py)

```python
from textual.widgets import DataTable
from textual.widgets.data_table import RowKey

class JobTable(DataTable):
    """
    Sortable, searchable table of jobs with assessment scores.

    Columns: Title | Company | Overall Score | Tech | Seniority | Location

    Keybindings:
      - Sort by clicking column header
      - [/] to search
      - [d] to see job details
      - [a] to approve/reject
    """

    def on_mount(self) -> None:
        """Setup table columns."""
        self.add_columns(
            "Title",
            "Company",
            "Overall",
            "Tech",
            "Seniority",
            "Location",
        )

    def update_rows(self, jobs: list) -> None:
        """Populate table with job data."""
        self.clear()
        for job in jobs:
            self.add_row(
                job.get("title", "")[:40],
                job.get("company", ""),
                f"{job.get('overall_score', 0):.0f}",
                f"{job.get('tech_score', 0):.0f}",
                f"{job.get('seniority_score', 0):.0f}",
                job.get("location", "")[:20],
            )
```

### CostTracker (src/tui/widgets/cost_tracker.py)

```python
from textual.widgets import Static

class CostTracker(Static):
    """
    Real-time cost display: tokens + USD.

    Example output:
      💰 Cost Tracking
      Tokens: 12,450 | Cost: $0.0373
      Estimate Rate: $0.003 per 1M tokens
    """

    def __init__(self, state, phase: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = state
        self.phase = phase

    def render(self) -> str:
        """Show token + cost totals for this phase."""
        metrics = self.state.phase_metrics[self.phase]
        return (
            f"💰 Cost Tracking ({self.phase})\n"
            f"Tokens: {metrics.total_tokens:,} | Cost: ${metrics.total_cost_usd:.6f}\n"
            f"Rate: $0.003 per 1M input tokens (Claude 3.5)"
        )
```

## Integration with CLI

Update `src/cli.py` to detect TUI vs text mode:

```python
import typer
from pathlib import Path
import os
import sys

@app.command()
def all(
    cv: str = typer.Option(..., help="Path to CV file (JSON)"),
    config: Optional[str] = typer.Option(None, help="Path to companies config (JSON)"),
    config_dir: Optional[str] = typer.Option(None, help="Directory with JSON config files"),
    headless: bool = typer.Option(True, help="Run browser in headless mode"),
    confirmed_only: bool = typer.Option(False, help="Skip unconfirmed jobs"),
    tui: bool = typer.Option(
        None,  # Auto-detect: True if TTY, False if piped
        help="Use TUI (auto-detected if not specified)"
    ),
) -> None:
    """Run full workflow: crawl → preprocess → review → assess → export."""

    # Auto-detect TUI if not specified
    if tui is None:
        tui = sys.stdout.isatty() and sys.stdin.isatty()

    if tui:
        # Use TUI
        from src.tui.dashboard import ATPDashboard
        from src.tui.models.state import StateManager

        state = StateManager()
        # Pass config/cv to state
        state.config_file = config or Path("config/companies.json")
        state.config_dir = Path(config_dir) if config_dir else None
        state.cv_file = Path(cv)
        state.headless = headless

        app = ATPDashboard(state)
        app.run()
    else:
        # Use existing text-based workflow
        # (existing implementation from lines 127-566)
        pass
```

## Testing Strategy

### Test Files

1. **test_state.py**: StateManager state transitions
   ```python
   def test_state_manager_progress():
       state = StateManager()
       state.start_phase("crawl", total_items=100)
       state.increment_phase_progress("crawl", tokens=150, cost=0.0005)
       assert state.phase_metrics["crawl"].processed_items == 1
       assert state.phase_metrics["crawl"].total_tokens == 150
   ```

2. **test_dashboard.py**: Dashboard rendering
   ```python
   async def test_dashboard_initialization():
       app = ATPDashboard(StateManager())
       async with app.run_test() as pilot:
           # Verify panels render
           assert app.query("#crawl-panel")
   ```

3. **test_widgets.py**: Individual widget updates
   ```python
   def test_progress_bar_render():
       state = StateManager()
       state.start_phase("crawl", total_items=100)
       pb = TUIProgressBar(state, "crawl")
       render = pb.render()
       assert "45%" not in render  # Not started yet

       for i in range(45):
           state.increment_phase_progress("crawl")
       render = pb.render()
       assert "45%" in render
   ```

## Error Handling

All phases should:
1. Catch exceptions in async tasks
2. Call `state.error_phase(phase, error_message)`
3. Trigger error dialog (shows error in modal)
4. Log full traceback to `logs/app.log`
5. Allow user to [r]etry or [q]uit

```python
async def _phase_assess(self) -> None:
    try:
        # ... assessment logic ...
    except Exception as e:
        logger.exception(f"Assessment phase failed: {e}")
        self.state.error_phase("assess", str(e))
        self.notify(f"Error: {e}", severity="error", timeout=10)
        # Optional: show ErrorDialog with full traceback
```

## Performance Considerations

1. **Redraw Frequency**: Update UI at ~2Hz (0.5s interval) to avoid flicker
   ```python
   self.set_interval(0.5, self._update_display)  # Not 60 FPS
   ```

2. **State Mutations**: Use dataclass `@dataclass` with `frozen=False` for mutability
   - Avoid expensive recompute in render() — cache in state

3. **Large Job Lists**: Use DataTable pagination, don't render 1000+ rows
   - Show top 100, pagination controls

4. **Async Operations**: All I/O (crawl, LLM, DB queries) must be async
   - Use `@work` decorator for long tasks
   - Don't block main thread
   - Use `@work(exclusive=True)` when updating StateManager to prevent race conditions
   - Single writer pattern: only one task mutates StateManager at a time

## Backward Compatibility

- Add `--tui` flag (auto-detect if not specified)
- Keep `--no-tui` flag for text-only output
- Existing scripts continue to work (no TTY → text mode)
- Logs written to `logs/app.log` regardless of mode

## Deployment Checklist

- [ ] Textual v0.42+ installed
- [ ] Rich library available (auto-installed with textual)
- [ ] Tests passing (including TUI tests)
- [ ] Keybindings documented in footer
- [ ] Error handling tested
- [ ] Large dataset tested (1000+ jobs)
- [ ] Terminal resize tested
- [ ] Color scheme works in light/dark terminals
- [ ] Accessibility: screenreader compatibility checked

---

**Status**: Ready for Phase 1 implementation
**Last Updated**: 2026-07-04
