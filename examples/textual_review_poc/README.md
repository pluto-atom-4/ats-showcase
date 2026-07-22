# Textual Review PoC: Proof of User Interaction

## What This Proves

This minimal side project **proves that Textual modal dialogs correctly handle user input** without the complexity of the full ATS dashboard.

✓ ModalScreen focus management via `call_later()`
✓ Keyboard navigation (Tab between buttons)
✓ Button activation (Enter to press focused button)
✓ User decisions captured (confirm/reject/skip)
✓ Escape key cancellation
✓ Terminal state restoration (`stty sane`)
✓ Async workflow coordination (`@work(exclusive=True)`)

## Run the PoC

```bash
cd examples/textual_review_poc
python run_poc.py
```

**Expected interaction:**
1. App starts, shows first job title
2. Dialog displays with 3 buttons (Confirm, Reject, Skip)
3. Tab to cycle through buttons (Confirm → Reject → Skip → Confirm)
4. Enter to select (button gets highlighted → pressed → decision captured)
5. Escape dismisses dialog with "skip" decision
6. Loop repeats for remaining jobs
7. After all jobs, shows summary of decisions
8. Terminal returns to normal state (type commands work)

## Key Textual Patterns Explained

### 1. ModalScreen Lifecycle

```python
class ReviewDialog(ModalScreen):
    def compose(self) -> ComposeResult:
        # Runs first: creates widget tree
        yield Button("Confirm", id="confirm")

    def on_mount(self) -> None:
        # Runs after compose: widgets mounted but may not be in DOM yet
        self.call_later(self._set_focus)  # CRITICAL: defer focus

    def _set_focus(self) -> None:
        # Runs after render cycle: now safe to query and focus
        btn = self.query_one("#confirm", Button)
        btn.focus()
```

**Why `call_later()`?** Direct `focus()` in `on_mount()` fails because widgets haven't entered the DOM yet.

### 2. Button Event Flow

```python
def on_button_pressed(self, event: Button.Pressed) -> None:
    # Triggered when user presses Enter on focused button
    if event.button.id == "confirm":
        self.decision = "confirm"
    self.dismiss(self.decision)  # Close dialog, return value
```

**Flow:** User presses Enter → Button.Pressed event → handler runs → `dismiss()` closes screen

### 3. Keyboard Input Handling

```python
BINDINGS = [
    ("escape", "quit_dialog", "Cancel"),
]

def action_quit_dialog(self) -> None:
    # Escape key calls this action
    self.dismiss(None)  # Close dialog with no decision
```

**Tab** navigates widgets (built-in Textual behavior)
**Enter** activates focused widget
**Escape** bound to custom action

### 4. Async Workflow Coordination

```python
@work(exclusive=True)
async def run_review(self) -> None:
    # Single writer: only this task mutates state
    for job in jobs:
        # Wait for dialog (blocks until user decides)
        decision = await self.app.push_screen_wait(ReviewDialog(...))

        # Mutation safe: no concurrent tasks
        self.state.record_decision(job_id, decision)
```

**`@work(exclusive=True)`** prevents race conditions
**`push_screen_wait()`** blocks until dialog dismissed, returns user's decision

### 5. Terminal I/O Safety

```python
try:
    app.run()
finally:
    # Always restore terminal state
    import subprocess
    subprocess.run(["stty", "sane"], check=False)
```

**Why?** Textual enters "alternate screen mode" (raw, no echo). If app crashes, terminal left broken.
**`stty sane`** restores normal input/output behavior.

## File Structure

```
examples/textual_review_poc/
├── __init__.py          # Package marker
├── poc_state.py         # Minimal StateManager (decisions only)
├── review_dialog.py     # ModalScreen with 3 buttons, focus deferral
├── review_poc.py        # Main app with @work async workflow
├── run_poc.py           # Entry point
└── README.md            # This file
```

- **~25 LOC:** poc_state.py (state tracking)
- **~65 LOC:** review_dialog.py (modal + buttons + focus)
- **~70 LOC:** review_poc.py (orchestration, terminal cleanup)
- **~5 LOC:** run_poc.py (launcher)

**Total: ~165 LOC** - No dependencies on src.cli, src.tui.dashboard, or ATPDashboard

## Comparison: PoC vs Dashboard

| Feature | PoC | Dashboard |
|---------|-----|-----------|
| Focus management | ✓ `call_later(_set_focus)` | ✓ Same (commit f3acdd6) |
| Button handling | ✓ `on_button_pressed()` | ✓ Same |
| Keyboard input | ✓ Tab/Enter/Escape | ✓ Same |
| Dialog dismissal | ✓ `push_screen_wait()` | ✓ Same |
| Async coordination | ✓ `@work(exclusive=True)` | ✓ Same |
| Terminal cleanup | ✓ `stty sane` in finally | ✓ Added (commit 5cdc3c3) |
| State tracking | ✓ Minimal (just decisions) | ✗ Complex (tokens, cost, phases) |
| Crawler integration | ✗ No | ✓ Yes |
| Preprocessor | ✗ No | ✓ Yes |
| Phase coordination | ✗ No | ✓ Yes (crawl→preprocess→review→assess→export) |

**Key difference:** PoC isolates interaction patterns; dashboard has complexity that might mask issues.

## What to Check in Dashboard

After running this PoC, verify the actual dashboard has these fixes:

### 1. Focus Deferral (Commit f3acdd6)

**File:** `src/tui/dialogs/job_review.py`

```python
def on_mount(self) -> None:
    """Set focus to first button after compose completes."""
    self.call_later(self._set_focus)  # ← Should be present

def _set_focus(self) -> None:
    """Set focus to confirm button (called after compose)."""
    try:
        confirm_btn = self.query_one("#confirm", Button)
        confirm_btn.focus()
    except Exception:
        pass
```

**Verify:** If missing `call_later()`, buttons won't get focus → no Tab navigation.

### 2. Review Phase (Commit f0377d4)

**File:** `src/tui/dashboard.py`

```python
async def _phase_review(self) -> None:
    # ← Interactive dialogs should be HERE, not in _phase_crawl()
    for job_id, job_data in self.state.jobs.items():
        if self.interactive:
            decision = await self.app.push_screen_wait(JobReviewDialog(...))
            self.state.update_job(job_id, status=...)
```

**Verify:** Dialogs in review phase (not crawl) → review phase can run independently.

### 3. Terminal Restoration (Commit 5cdc3c3)

**File:** `src/cli.py`

```python
try:
    app.run()
except Exception as e:
    logger.exception(f"TUI error: {e}")
finally:
    import subprocess
    try:
        if sys.stdin.isatty():
            subprocess.run(["stty", "sane"], check=False)  # ← Required
    except Exception:
        pass
```

**Verify:** If missing, terminal left in raw mode after TUI exit → no input echo.

### 4. StateManager Mutations (Thread Safety)

**File:** `src/tui/dashboard.py`

```python
@work(exclusive=True)
async def run_workflow(self) -> None:
    # ← Only this task should mutate self.state
    await self._phase_crawl()
    await self._phase_review()  # Update job statuses here
    await self._phase_assess()
```

**Verify:** No other code path mutates StateManager (e.g., button handlers).

## Running the Verification

### Test keyboard interaction manually:
```bash
python run_poc.py

# Use keyboard:
# - Tab: navigate buttons
# - Enter: confirm/reject/skip
# - Escape: skip without decision
```

### Check terminal state after exit:
```bash
python run_poc.py
# App exits
# Type: echo "Terminal works"
# Should see output normally (no '^M' carriage return artifacts)
```

## Debugging Checklist

If interaction doesn't work:

- [ ] Does the dialog appear? (Check for error in logs)
- [ ] Can you Tab between buttons? (If not: focus not set)
- [ ] Does button highlight when focused? (If not: focus set wrong widget)
- [ ] Does Enter press the button? (If not: on_button_pressed not called)
- [ ] Does Escape dismiss? (If not: action_quit_dialog not bound)
- [ ] Does terminal work after exit? (If not: stty sane not called)

## Key Takeaways

1. **Deferred focus is essential** – use `call_later()` for focus management
2. **ModalScreen lifecycle matters** – compose → on_mount → on_show → active
3. **Button events are synchronous** – handler runs immediately on Enter
4. **Terminal cleanup is critical** – always call `stty sane` in finally block
5. **Async coordination prevents races** – use `@work(exclusive=True)` for state mutations

## Related Files in Dashboard

- `src/tui/dialogs/job_review.py` – Actual JobReviewDialog (should match PoC pattern)
- `src/tui/dashboard.py` – ATPDashboardApp and phase methods
- `src/tui/models/state.py` – StateManager (much more complex than PoC variant)
- `src/cli.py` – Terminal cleanup pattern
- `tests/tui/test_job_review_dialog.py` – Unit tests for dialog
- `tests/tui/test_review_phase_interactive.py` – Integration tests with mock jobs

## References

- Textual docs: https://textual.textualize.io/guide/screens/#modal-screen
- Rich docs: https://rich.readthedocs.io/
- Textual GitHub: https://github.com/Textualize/textual
