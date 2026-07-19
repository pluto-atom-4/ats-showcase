# TUI Patterns (Async, Testing, Error Handling)

---

## Async Patterns

**All I/O must be async:** crawl, LLM calls, DB queries.

```python
from textual import work

class Dashboard(Screen):
    @work(exclusive=True)
    async def run_workflow(self) -> None:
        """Single writer: only task that mutates StateManager."""
        await self._phase_crawl()
        await self._phase_assess()

    async def _phase_crawl(self) -> None:
        self.state.start_phase("crawl", total_items=100)
        async with BrowserManager() as browser:
            for company in companies:
                jobs = await browser.fetch_jobs(company)  # Non-blocking
                self.state.add_job(...)
                self.state.increment_phase_progress("crawl", tokens=150)
```

**Rule:** Only one `@work(exclusive=True)` task mutates StateManager at a time.

---

## Testing Strategy

### Test StateManager
```python
def test_state_transitions():
    state = StateManager()
    state.start_phase("crawl", total_items=100)
    state.increment_phase_progress("crawl", tokens=150, cost=0.0005)
    assert state.phase_metrics["crawl"].processed_items == 1
    assert state.phase_metrics["crawl"].total_tokens == 150
```

### Test Dashboard Rendering
```python
async def test_dashboard_init():
    app = ATPDashboard(StateManager())
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query("#crawl-panel")
        assert app.query("#header")
```

### Test Widget Updates
```python
def test_progress_bar():
    state = StateManager()
    state.start_phase("crawl", total_items=100)
    pb = TUIProgressBar(state, "crawl")

    for i in range(45):
        state.increment_phase_progress("crawl")

    render = pb.render()
    assert "45%" in render
```

---

## Error Handling

All phases catch exceptions and update state:

```python
async def _phase_assess(self) -> None:
    try:
        self.state.start_phase("assess", total_items=len(jobs))
        for job in jobs:
            score = await llm.assess(job)
            self.state.increment_phase_progress("assess", tokens=673, cost=0.002)
    except LLMError as e:
        logger.exception(f"Assessment failed: {e}")
        self.state.error_phase("assess", str(e))
        self.notify(f"Error: {e}", severity="error", timeout=10)
        # Optional: show ErrorDialog with traceback
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        self.state.error_phase("assess", "Unexpected error")
        self.app.exit(message="Fatal error - see logs")
```

**Pattern:**
1. Catch specific + general exceptions
2. Log full traceback
3. Update state with `error_phase()`
4. Notify user
5. Allow retry or exit

---

## Performance Considerations

### Redraw Frequency
```python
# Good: 2 Hz (500ms), prevents flicker
self.set_interval(0.5, self._update_display)

# Bad: 60 FPS, CPU thrashing
self.set_interval(0.016, self._update_display)
```

### State Mutations
Only `@work(exclusive=True)` tasks mutate StateManager:
```python
# Good
@work(exclusive=True)
async def run_workflow(self):
    self.state.increment_phase_progress(...)

# Bad
async def handle_input(self):
    self.state.paused = True  # Race condition if run_workflow also writes
```

### Large Datasets
```python
# Good: Pagination
jobs_page = jobs[:100]
self.job_table.update_rows(jobs_page)

# Bad: Render 5000 rows
self.job_table.update_rows(all_jobs)
```

### Caching Derived Values
```python
# Good: Pre-compute in StateManager
@property
def total_cost_usd(self):
    return sum(m.total_cost_usd for m in self.phase_metrics.values())

# Bad: Recompute in render()
def render(self):
    cost = sum(...)  # Expensive, runs every 500ms
```

---

## Backward Compatibility

Keep existing text-mode CLI working:

```python
@app.command()
async def all(..., tui: Optional[bool] = None) -> None:
    if tui is None:
        tui = sys.stdout.isatty() and sys.stdin.isatty()

    if tui:
        app = ATPDashboard(StateManager())
        app.run()
    else:
        # Existing text-based workflow (no TUI)
        await crawl(...)
        await preprocess(...)
```

**Flags:**
- `--tui` – Force TUI mode
- `--no-tui` – Force text mode
- No flag – Auto-detect (TTY → TUI; piped → text)

---

## Deployment Checklist

- [ ] Textual 0.42+ installed
- [ ] Rich 13.0+ installed
- [ ] Tests passing (dashboard, state, widgets)
- [ ] Keybindings documented in footer
- [ ] Error handling tested (network timeout, LLM error, etc.)
- [ ] Large dataset tested (1000+ jobs)
- [ ] Terminal resize tested
- [ ] Light/dark theme works
- [ ] Logs still written to `logs/app.log`
- [ ] Backward compat: text mode still works

---

**See Also:** `architecture.md`, `widgets.md`, original `tui.md` (full code)
