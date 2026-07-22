# Testing Textual Review PoC

## Manual Interactive Test

Run the app in interactive mode and manually test keyboard navigation:

```bash
uv run python examples/textual_review_poc/run_poc.py
```

### Expected Output

```
🧪 Textual Review PoC
   Demonstrates proper Textual interaction patterns

┌──────────────────────────────────────────────────────────────────┐
│ ⭘          ReviewPoCApp                                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Job 1/3: Senior Python Developer                              │
│   Use Tab to navigate, Enter to select, Escape to skip          │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Job Review                                                 │ │
│  │ Title: Senior Python Developer                             │ │
│  │ Company: TechCorp                                          │ │
│  │ ┌─────────────────────────────────────────────────────────┐ │
│  │ │ 5+ years Python, FastAPI, PostgreSQL...                  │ │
│  │ ┌──────────────────────────────────────────────────────────┐ │
│  │ │      [Confirm]       [Reject]       [Skip]              │ │
│  │ └──────────────────────────────────────────────────────────┘ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│ q  Quit                                    ^p palette            │
└──────────────────────────────────────────────────────────────────┘
```

### Test Sequence

**For each job, test these interactions:**

1. **Initial Focus**
   - Confirm button should be highlighted with blue background
   - ✓ If yes: deferred focus working
   - ✗ If no: focus() called before widgets mounted

2. **Tab Navigation**
   - Press Tab
   - Button highlight moves: Confirm → Reject
   - Press Tab again
   - Button highlight moves: Reject → Skip
   - Press Tab again
   - Button highlight moves: Skip → Confirm (wraps)
   - ✓ If yes: focus management working
   - ✗ If no: focus not set, Tab doesn't navigate

3. **Enter Activation**
   - Focus Confirm button (Tab if needed)
   - Press Enter
   - Dialog closes, next job appears
   - Status shows "Job 1/3 completed, moving to Job 2"
   - ✓ If yes: button press handler working
   - ✗ If no: dialog stays open or error

4. **Reject Flow**
   - Focus Reject button (Tab to it)
   - Press Enter
   - Dialog closes with "rejected" decision recorded
   - ✓ If yes: button ID detection working

5. **Escape Key**
   - Press Escape
   - Dialog closes with "skip" decision (no decision)
   - ✓ If yes: keybinding working

6. **Final Summary**
   - After all 3 jobs, app exits automatically
   - Shows summary with decision counts:
     ```
     📊 Review Summary
       Confirmed: X
       Rejected: Y
       Skipped: Z
       Pending: 0
     ```
   - ✓ If yes: state accumulation working

7. **Terminal State**
   - After app exits, type a command
   - Command echoes and executes normally
   - ✓ If yes: `stty sane` working
   - ✗ If no: see `^M` artifacts, input broken

## Debugging Commands

### Check Focus Implementation

```bash
cd examples/textual_review_poc
grep -n "call_later\|_set_focus" review_dialog.py
```

**Expected output:**
```
67:    def on_mount(self) -> None:
68:        """Deferred focus: call_later ensures widgets are fully mounted."""
69:        self.call_later(self._set_focus)
71:    def _set_focus(self) -> None:
```

### Check Button Handlers

```bash
grep -n "on_button_pressed\|event.button.id" review_dialog.py
```

**Expected output:**
```
87:    def on_button_pressed(self, event: Button.Pressed) -> None:
88:        """Handle button presses (Tab + Enter workflow)."""
89:        if event.button.id == "confirm":
```

### Check Keybindings

```bash
grep -n "BINDINGS\|action_quit" review_dialog.py
```

**Expected output:**
```
100:    BINDINGS = [
101:        ("escape", "quit_dialog", "Cancel"),
```

## Comparison with Dashboard

After testing PoC, verify dashboard has same patterns:

### 1. Check focus deferral in JobReviewDialog

```bash
grep -A 5 "def on_mount" src/tui/dialogs/job_review.py
```

Should show:
```python
def on_mount(self) -> None:
    """Set focus to first button after compose completes."""
    self.call_later(self._set_focus)
```

### 2. Check review phase has dialogs

```bash
grep -B 5 "push_screen_wait.*JobReviewDialog" src/tui/dashboard.py
```

Should show interactive dialog in `_phase_review()`, NOT in `_phase_crawl()`.

### 3. Check terminal cleanup

```bash
grep -B 2 "stty sane" src/cli.py
```

Should show in `finally:` block after `app.run()`.

## Test Results Template

Copy and fill in after testing:

```
# PoC Interaction Test Results

Date: 2026-07-XX
Tester: [name]

## Manual Interactive Test
- [ ] Initial focus on Confirm button
- [ ] Tab cycles through buttons (Confirm → Reject → Skip)
- [ ] Enter activates focused button
- [ ] Confirm decision captured correctly
- [ ] Reject decision captured correctly
- [ ] Skip decision captured correctly
- [ ] Escape cancels (skip without decision)
- [ ] All 3 jobs processed
- [ ] Final summary shows all decisions
- [ ] Terminal state restored (commands work)

## Result
✓ PASS - All interactions working as expected
✗ FAIL - See failed items above

## Dashboard Verification
- [ ] JobReviewDialog has call_later(_set_focus)
- [ ] Interactive dialogs in _phase_review(), not _phase_crawl()
- [ ] Terminal cleanup (stty sane) in finally block
- [ ] StateManager mutations in @work(exclusive=True)

## Notes
[Add observations, errors, or additional findings]
```

## Common Issues

### Issue: Focus doesn't appear on buttons

**Symptom:** No button is highlighted when dialog opens

**Root cause:** `on_mount()` didn't call `call_later()`

**Check:**
```bash
grep "def on_mount" review_dialog.py -A 3
```

**Fix:** Must have:
```python
def on_mount(self):
    self.call_later(self._set_focus)
```

### Issue: Tab doesn't navigate buttons

**Symptom:** Tab key goes to next field, not next button

**Root cause:** Focus not set in `on_mount()`

**Check:** Run verification above (Focus doesn't appear)

### Issue: Enter doesn't activate button

**Symptom:** Press Enter, nothing happens

**Root cause:** `on_button_pressed()` not defined or button ID mismatch

**Check:**
```bash
grep "on_button_pressed\|event.button.id" review_dialog.py
```

### Issue: Escape doesn't work

**Symptom:** Press Escape, dialog stays open

**Root cause:** BINDINGS not defined or action method missing

**Check:**
```bash
grep -A 3 "BINDINGS\|action_quit" review_dialog.py
```

### Issue: Terminal broken after exit

**Symptom:** No echo when typing commands, see `^M`

**Root cause:** `stty sane` not called in finally block

**Check:**
```bash
grep -B 5 "stty sane" review_poc.py
```

Should be in:
```python
finally:
    subprocess.run(["stty", "sane"], check=False)
```

## Performance Notes

- Dialog should appear instantly (no lag)
- Tab navigation should feel responsive (no delay)
- Button press should close dialog immediately
- Summary should display in <1s
- App exit should be instant

If any of these are slow, check for:
- Long-running operations in dialog methods
- Blocking I/O in event handlers
- Missing `await asyncio.sleep()` calls
