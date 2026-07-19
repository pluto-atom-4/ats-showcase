# TUI Widgets Reference

Key UI components for ATS Playground dashboard.

---

## ProgressBar (Custom)

Real-time progress with ETA and throughput.

```python
class TUIProgressBar(ProgressBar):
    """Custom progress bar with ETA + speed."""

    def render(self) -> str:
        metrics = self.state.phase_metrics[self.phase]
        bar_width = 40
        filled = int((metrics.progress_percent / 100) * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        return f"{self.phase}: {bar} {metrics.progress_percent:.0f}%\n({metrics.processed_items}/{metrics.total_items}) | ETA: {metrics.eta_seconds / 60:.0f}m"
```

**Output:**
```
crawl: ████████░░░░░░░░░░░░ 45%
(90/200) | ETA: 2m | Speed: 10.5/s
```

---

## JobTable (DataTable)

Sortable table of jobs with scores.

```python
class JobTable(DataTable):
    """Sortable, searchable job list."""

    def on_mount(self) -> None:
        self.add_columns(
            "Title", "Company", "Overall", "Tech", "Seniority", "Location"
        )

    def update_rows(self, jobs: list) -> None:
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

**Features:** Sort by column (click), search (ctrl+f), pagination

---

## CostTracker (Static Widget)

Real-time cost display.

```python
class CostTracker(Static):
    """Running token + USD cost."""

    def render(self) -> str:
        metrics = self.state.phase_metrics[self.phase]
        return (
            f"💰 Cost Tracking ({self.phase})\n"
            f"Tokens: {metrics.total_tokens:,} | Cost: ${metrics.total_cost_usd:.6f}\n"
            f"Rate: $0.003 per 1M input tokens"
        )
```

---

## PhaseIndicator (Static)

Status of each phase.

```
crawl ✓  |  preprocess ⟳  |  assess —  |  export —
```

Shows: ✓ (done), ⟳ (running), — (pending), ✗ (error)

---

## HeaderPanel (Static)

Top-level status + total cost.

```
🎯 ATS Playground | Workflow Status: assess | Total Cost: $0.15 | Tokens: 5,420
```

---

## Panel Examples

### CrawlPanel
- Progress bar (companies crawled)
- Job count (total extracted)
- Running cost
- Error log (collapsed)

### AssessPanel
- Progress bar (jobs assessed)
- Top 5 matches table (by score)
- Running cost
- Compliance log

### ExportPanel
- Status (in progress / done)
- Output file path
- Summary stats (avg score, distribution)

---

## Custom CSS

Panels use Textual CSS:

```css
BasePanelWidget {
    height: 1fr;
    border: solid $primary;
    padding: 1;
}

#header {
    height: 3;
    border: solid $primary;
    background: $boost;
}

#content {
    height: 1fr;
}
```

**Colors:** `$primary`, `$boost`, `$background`, `$success`, `$error`, `$warning`

---

## Performance Tips

1. **Update Frequency:** 0.5s (not 60 FPS)
   ```python
   self.set_interval(0.5, self._update_display)
   ```

2. **Pagination:** Don't render 1000+ rows
   - Show top 100 jobs
   - Add pagination controls

3. **Async State:** Mutations in `@work(exclusive=True)` tasks

4. **Caching:** Pre-compute derived values in StateManager, not in render()

---

**See Also:** `architecture.md`, `patterns.md`, original `tui.md` (full implementations)
