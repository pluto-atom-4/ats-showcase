# DESIGN.md: ATS Playground Architecture

**Version:** 2.0 (Anthropic standards, Semantic Design Tokens)
**Last Updated:** 2026-07-04
**Status:** Ready for Phase 1 TUI Implementation

---

## 1. PRODUCT NARRATIVE

### The Problem

ATS Playground orchestrates a 4-phase workflow: crawl career pages, preprocess HTML, assess CV fit via Claude, and export results. Each phase handles dozens to thousands of jobs. Raw HTML is ~6,000 tokens per job; preprocessed text is ~400 tokens (15× reduction in cost).

Currently, the CLI outputs 300+ lines of text for a single `all` command run. This creates several UX challenges:

- **Information Overload:** User can't track which phase is running or identify bottlenecks
- **Poor Real-Time Feedback:** No progress percentage, ETA, or live cost tracking
- **Context Switching Required:** User must scroll through massive output to find top matches
- **No Cost Visibility:** Token counts scattered throughout output; total cost unknown until completion

### The Design Philosophy

Replace verbose text output with a single cohesive dashboard that provides:

1. **Real-time progress** (crawl, preprocess, assess, export phases)
2. **Live cost accumulation** (tokens + USD in real-time)
3. **Top matches visible** (best jobs shown as they're processed)
4. **Async workflow support** (dashboard reflects parallel crawl + LLM calls)

### Core Principles

**Clarity:** What's happening right now? Which phase? Which job?
**Confidence:** How much will this cost? How long until done?
**Control:** Pause/resume/cancel if costs exceed budget or progress stalls.

### Key Insight

ATS is inherently async. Multiple jobs crawled in parallel, multiple assessments queued for Claude (rate-limited by TPM). The TUI must reflect this: progress bars for each phase, live token accumulation, ETA estimates. Text-based output (sequential, blocking) obscures the true async nature of the workflow.

---

## 2. SEMANTIC DESIGN TOKENS

This section defines architectural roles as semantic decisions, not just class names. Each token clarifies "when to use" and "when NOT to use."

### StateManager: Source-of-Truth Token

**Role:** Centralized state for entire workflow lifecycle. Single source of truth for phase progress, job data, and cost tracking.

**Responsibilities:**
- Track phase status (idle → running → paused → completed/error)
- Accumulate metrics (processed items, failed items, tokens, cost)
- Store job data (id, title, company, assessment scores)
- Calculate derived values (progress %, ETA, items per second)
- Provide top matches (top 5 by overall_score)

**When to Use:**
- Any component needs current phase progress
- Multiple panels need to sync on same state
- Tests need to verify state transitions
- External code (crawl, assess phases) reports progress

**When NOT to Use:**
- UI rendering logic (panels decide rendering, not StateManager)
- Cross-panel communication (use state, not panel-to-panel messaging)
- Workflow orchestration (crawl/assess logic lives in CLI, not state)
- Storing UI-specific data (theme, scroll position, etc.)

**Example (Correct):**
```python
# StateManager is observed, not an actor
state = StateManager()
state.start_phase("crawl", total_items=100)

# CLI code updates state as jobs are processed
state.add_job("job-1", "Senior Dev", "TechCorp")
state.increment_phase_progress("crawl", tokens=150, cost=0.0005)

# Panel observes state
panel.render()  # Reads state.phase_metrics["crawl"].progress_percent
```

**Example (Incorrect):**
```python
# ❌ Don't use StateManager for UI decisions
if state.phase_status["crawl"] == PhaseStatus.RUNNING:
    button.disabled = True  # Wrong: UI logic leaks into state

# ❌ Don't use StateManager to coordinate between panels
state.current_panel = "assess"  # Wrong: use visibility flag instead
```

---

### Panel: Phase-Specific View Token

**Role:** Display metrics and content for one phase (crawl/preprocess/assess/export). Panels switch visibility as workflow progresses.

**Responsibilities:**
- Read from StateManager
- Render phase-specific widgets (progress bar, job list, cost tracker)
- Bind to state updates (poll every 0.5s)
- Handle phase-specific error display

**When to Use:**
- One phase = one panel (CrawlPanel, AssessPanel, etc.)
- Panel displays multiple widgets related to same phase
- Panel needs to show phase-specific details (e.g., top matches in assess phase only)

**When NOT to Use:**
- Cross-panel communication (use StateManager for shared state)
- Global state mutations (panels are observers, not actors)
- Workflow logic (panel doesn't execute crawl/assess; CLI does)

**Example (Correct):**
```python
class AssessPanel(BasePanelWidget):
    def on_mount(self):
        self.set_interval(0.5, self._update_display)

    def _update_display(self):
        # Read state, update widgets
        metrics = self.state.phase_metrics["assess"]
        self.query_one("#progress").update(f"{metrics.progress_percent:.0f}%")
        self.query_one("#top-matches").update_rows(self.state.top_matches)
```

---

### Widget: Reusable Component Token

**Role:** Composable UI component used across panels (ProgressBar, CostTracker, JobTable, PhaseIndicator). Widgets are stateless views of StateManager.

**Responsibilities:**
- Accept StateManager in `__init__`
- Render based on current state
- Update at ~2Hz (0.5s interval) to prevent flicker
- Handle user interaction (clicks, keys) if applicable

**When to Use:**
- Component is reusable across 2+ panels
- Component has complex rendering logic
- Component updates frequently (not static text)

**When NOT to Use:**
- One-off static text (use Static widget instead)
- Workflow logic (widgets are presentational)
- Storing widget's own state (StateManager owns state)

**Example (Correct):**
```python
class ProgressBar(Widget):
    def __init__(self, state: StateManager, phase: str):
        super().__init__()
        self.state = state
        self.phase = phase

    def render(self) -> str:
        metrics = self.state.phase_metrics[self.phase]
        bar_width = 40
        filled = int((metrics.progress_percent / 100) * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        eta_str = f"ETA: {metrics.eta_seconds / 60:.0f}m" if metrics.eta_seconds > 0 else "ETA: --"
        return f"{self.phase.upper()}: {bar} {metrics.progress_percent:.0f}%\n({metrics.processed_items}/{metrics.total_items}) | {eta_str}"
```

---

### Async Workflow: Non-Blocking I/O Token

**Role:** Run long-lived operations (crawl, LLM calls, DB queries) without blocking UI or main thread. Textual's `@work` decorator coordinates async operations while UI polls StateManager.

**Responsibilities:**
- Execute phases sequentially (crawl → preprocess → assess → export)
- Update StateManager as jobs are processed
- Catch exceptions, call state.error_phase() to notify UI
- Respect pause/resume signals from UI

**When to Use:**
- Any I/O-bound operation (network, LLM, DB)
- Need real-time progress updates without blocking UI
- Must avoid blocking main Textual thread

**When NOT to use:**
- Synchronous operations in TUI context (use async/await)
- UI rendering in async context (Textual handles this)
- Multiple writers to StateManager (causes race conditions; use exclusive=True)

**Example (Correct):**
```python
class Dashboard(Screen):
    @work(exclusive=True)
    async def run_workflow(self):
        # All I/O is async; StateManager updates trigger UI redraws
        await self._phase_crawl()
        await self._phase_preprocess()
        await self._phase_assess()
        await self._phase_export()

    async def _phase_crawl(self):
        self.state.start_phase("crawl", total_items=100)
        async with BrowserManager() as browser:
            for job in await browser.fetch_all_jobs(configs):
                self.state.add_job(job.id, job.title, job.company)
                self.state.increment_phase_progress("crawl", tokens=0)
        self.state.complete_phase("crawl")
```

---

## 3. ARCHITECTURE OVERVIEW

### 3.1 Workflow Pipeline

```
CONFIG (companies.json, CSS selectors)
    ↓
CRAWL (src/browser/)
    • Playwright renders JavaScript
    • Extracts via CSS selectors + pagination
    • Rate limits & retries
    ↓ Raw HTML + metadata
PREPROCESS (src/parsers/ + src/tokenization/)
    • MarkItDown cleans HTML → clean text
    • spaCy segments by sentences (semantic, not token-based)
    • tiktoken counts tokens before LLM
    ↓ Clean chunks + token estimates
VERIFY (src/verification/)
    • Interactive CLI shows extracted jobs
    • User confirms/rejects before expensive API calls
    • Cost transparency (token count + USD estimate)
    ↓ Confirmed jobs
ASSESS (src/llm/)
    • Claude 3.5 Sonnet evaluates CV fit
    • Scores by category (tech skills, seniority, etc.)
    • Rate limiting & retry logic
    • Tracks actual vs estimated tokens
    ↓ Assessment + metadata
STORAGE (src/storage/)
    • SQLite with FTS5 full-text search index
    • Stores jobs, assessments, token counts, costs
    ↓ Queryable database
EXPORT (src/storage/)
    • Generate Markdown reports
    • Search by keyword/score
    • Analytics (token usage, cost breakdown)
```

### 3.2 Module Structure

| Module | Purpose | Key Exports |
|--------|---------|-------------|
| **src/models/** | Pydantic schemas for data validation | Job, Assessment, CostMetrics |
| **src/browser/** | Playwright automation | BrowserManager (async) |
| **src/parsers/** | HTML cleaning (MarkItDown → BeautifulSoup fallback) | parse_html(), clean_text() |
| **src/tokenization/** | NLP chunking (spaCy) + token counting (tiktoken) | chunk_by_sentences(), count_tokens() |
| **src/verification/** | Interactive CLI review before LLM | review_jobs_interactive() |
| **src/llm/** | Claude API client (provider-agnostic pattern) | LLMProvider, assess_job() |
| **src/storage/** | SQLite persistence + queries + markdown export | JobStore, export_markdown() |
| **src/cli.py** | Typer CLI orchestration | app (Typer instance) |
| **src/tui/** | Textual dashboard for workflow visualization (Phase 1+) | Dashboard, StateManager, Panels |

### 3.3 Data Flow & State

```
Extracted Job (from crawl):
  status: pending_review → confirmed/rejected
  raw_html: <raw HTML from career page>

  ↓ After preprocess:
  clean_text: <MarkItDown output>
  chunks: [chunk1, chunk2, ...]
  estimated_tokens: 650
  estimated_cost: $0.002

  ↓ After verify (user confirms):
  status: confirmed

  ↓ After assess:
  assessment: {match_score: 78, categories: {...}, reasoning: "..."}
  actual_tokens: 673
  actual_cost: $0.002

  ↓ In storage (queryable):
  job_id, company, title, clean_text, chunks, assessment, tokens, cost
  (indexed by FTS5 for fast search)
```

### 3.4 Important Non-Obvious Behavior

- **Chunks are sentences, not fixed-size tokens:** Splitting at sentence boundaries (spaCy) means chunk sizes vary 100–600 tokens. This is intentional—preserves meaning better than token-based splits. Don't treat variable chunk sizes as a bug.

- **Token estimates are pre-API:** tiktoken estimates before sending to Claude. Actual Claude tokens may differ slightly (special tokens, prompt overhead). Differences tracked in cost_tracking table for future refinement.

- **Confirmed status required for assessment:** By default, `assess` only processes jobs where `status == "confirmed"`. Use `--confirmed-only` flag to enforce. Prevents wasting API quota on low-confidence extractions.

- **SQLite is single-writer:** Don't run multiple assessment processes concurrently on same DB (lock contention causes deadlocks). Use queue/single-process pattern or external locks.

- **Verification is not optional:** Show user cost estimate before sending to LLM. Gives user transparency and chance to cancel if costs exceed expectations.

### 3.5 Common Implementation Patterns

**Add a new CLI command:**
```python
from typer import Typer, Option
import logging

logger = logging.getLogger(__name__)
app = Typer()

@app.command()
def my_command(
    param: str = Option(..., help="Description"),
) -> None:
    """Help text visible in --help."""
    logger.info(f"Starting my_command with {param}")
    # implementation
```

**Access database from a module:**
```python
from src.storage.db import JobStore

store = JobStore("data/ats_playground.db")
results = store.query_by_keyword("python", min_score=75)
assessment = store.get_assessment(job_id)
store.update_job_status(job_id, "confirmed")
```

**Count tokens for a string:**
```python
from src.tokenization.counter import count_tokens

tokens = count_tokens(text)
cost_usd = tokens * 0.000003  # Claude 3.5 input rate
print(f"Estimated cost: ${cost_usd:.6f}")
```

**Parse HTML to clean text:**
```python
from src.parsers.html import parse_html

raw_html = "<html>...</html>"
clean_text = parse_html(raw_html)  # MarkItDown or BeautifulSoup fallback
```

**Chunk text by sentences:**
```python
from src.tokenization.chunking import chunk_by_sentences

chunks = chunk_by_sentences(clean_text, target_tokens=400)
for chunk in chunks:
    token_count = count_tokens(chunk)
    print(f"Chunk: {token_count} tokens")
```

---

## 4. KEY DECISIONS — SUMMARY LAYER

This section provides 1-page summaries of critical architectural decisions. For detailed analysis, alternatives considered, and risk mitigation, see **docs/ARCHITECTURE-DECISIONS.md**.

### Decision 1: TUI Framework = Textual

**Selected:** Textual v0.42+ (by Textualize, maintainers of Rich)

**Why:** Async-native (crawl + LLM calls run in parallel without blocking UI), real-time updates without flicker, composable widgets, Rich integration, testing API for CI/CD.

**Alternatives considered:** Urwid (lacks async), Blessed (too low-level), Rich alone (output-only, no input), Prompt Toolkit (single prompts, not multi-panel dashboards), Curses (dated, low-level).

**Constraints:** Textual < v1.0 (pin `^0.42.0`). Must wrap async operations in `@work` decorator. Don't block main thread with sync I/O.

**See:** docs/ARCHITECTURE-DECISIONS.md § Framework Selection (800w, detailed comparison & ATS-specific reasoning)

---

### Decision 2: Semantic Chunking (Sentences, Not Tokens)

**Selected:** spaCy sentence segmentation

**Why:** Preserves meaning. "Requires 5+ years MES. Must know Wonderware." stays together, not split at token boundary. Chunks vary 100–600 tokens intentionally.

**Constraints:** Don't force uniform token counts. Variable chunk sizes are correct behavior.

**See:** docs/ARCHITECTURE-DECISIONS.md § Semantic Chunking (300w)

---

### Decision 3: Token Counting Before LLM

**Selected:** tiktoken for estimates, Claude API response for actual

**Why:** Cost transparency to user before expensive API calls. Show estimate before asking for confirmation.

**Constraints:** Estimates may differ slightly from actual. Track both in cost_tracking table.

**See:** docs/ARCHITECTURE-DECISIONS.md § Token Counting Strategy (300w)

---

### Decision 4: StateManager Centralization

**Selected:** Single centralized StateManager (not distributed state)

**Why:** Panels stay in sync, easier to test, prevents race conditions in concurrent updates.

**Constraints:** Don't mutate StateManager from multiple async tasks. Use StateManager methods only, with `@work(exclusive=True)` for critical sections.

**See:** docs/ARCHITECTURE-DECISIONS.md § StateManager Centralization (300w)

---

### Decision 5: SQLite + FTS5 (Not PostgreSQL, NoSQL, etc.)

**Selected:** SQLite with FTS5 full-text search

**Why:** Single-machine use case, no server overhead, FTS5 provides <100ms queries on 1000+ jobs, ACID guarantees.

**Constraints:** Single-writer (no concurrent assessment processes). Use queue pattern if multiple processes needed.

**See:** docs/ARCHITECTURE-DECISIONS.md § Storage Layer (300w)

---

### Decision 6: Claude 3.5 Sonnet (Not Batch API)

**Selected:** Claude 3.5 Sonnet (sync API)

**Why:** Fast enough for interactive workflows (results needed immediately for verification). Batch API not suitable (output needed now, not in 24h). Rate limits: ~10 RPM, ~50k TPM.

**See:** docs/ARCHITECTURE-DECISIONS.md § Claude 3.5 Sonnet (200w)

---

## 5. PHASE-SPECIFIC RULES

Detailed implementation patterns for each phase live in separate rule files. This section indexes them.

| Phase | Rule File | Key Decision | Status |
|-------|-----------|--------------|--------|
| **Crawl** | `.claude/rules/crawl.md` | Playwright + CSS selectors, async coordination, rate limiting | Ready |
| **Preprocess** | `.claude/rules/preprocess.md` | MarkItDown primary, semantic chunking (sentences), token counting | Ready |
| **Verify** | `.claude/rules/verify.md` | Interactive CLI, cost transparency, status flow | Ready |
| **Assess** | `.claude/rules/assess.md` | Claude API, prompt design, rate limiting, error handling | Ready |
| **Storage** | `.claude/rules/storage.md` | SQLite schema, FTS5, single-writer pattern, markdown export | Ready |
| **CLI** | `.claude/rules/cli.md` | Typer patterns, async orchestration, help text | Ready |
| **TUI** | `.claude/rules/tui.md` | Textual patterns, StateManager, dashboard architecture | Ready for Phase 1 |

---

## 6. ANTI-PATTERNS & BOUNDARIES

This section codifies critical "never" behaviors. Violating these causes bugs, wasted API quota, or data loss.

### Don't assess unconfirmed jobs
**Why:** Prevents wasting API quota on low-confidence HTML extractions.
**How to avoid:** Use `--confirmed-only` flag (default: True). Check job status before passing to assess.

### Don't run multiple assessment processes on same DB
**Why:** SQLite is single-writer. Multiple processes cause lock contention and deadlocks.
**How to avoid:** Use queue/single-process pattern or external locking mechanism. Run assessments sequentially.

### Don't send raw HTML to Claude
**Why:** Raw HTML ~6,000 tokens per job. Preprocessed text ~400 tokens. Costs 15× more without cleaning.
**How to avoid:** Always run preprocess phase before assess. Never skip cleaning step.

### Don't skip user verification
**Why:** Unconfirmed extractions cause assessment errors. User deserves cost transparency.
**How to avoid:** Always show cost estimate before LLM calls. Require user confirmation.

### Don't force uniform token counts in chunks
**Why:** Chunks split at sentence boundaries (spaCy), not token counts. Sizes vary 100–600 tokens intentionally.
**How to avoid:** Accept variable chunk sizes. This is correct behavior, not a bug.

### Don't mutate StateManager from multiple async tasks
**Why:** Race conditions. Multiple tasks writing simultaneously cause state inconsistency.
**How to avoid:** Use StateManager methods only. Wrap critical sections with `@work(exclusive=True)`.

### Don't block the main thread in TUI
**Why:** UI becomes unresponsive, appears broken. User can't pause/cancel.
**How to avoid:** All I/O in async tasks. Use `@work` decorator. Never use `time.sleep()` in UI code.

### Don't render from StateManager in UI logic
**Why:** Mixes state management with presentation. Hard to test and maintain.
**How to avoid:** Panels read state, transform for rendering. Don't mutate state in render() methods.

---

## 7. ENVIRONMENT & DEPLOYMENT

### 7.1 Common Implementation Patterns

**Add a new CLI command:**
```python
@app.command()
def new_command(
    param: str = typer.Option(..., help="Description"),
) -> None:
    """Help text visible in --help."""
    logger.info(f"Starting new_command with {param}")
    typer.echo("Output to user")
```

**Access database from a module:**
```python
from src.storage.db import JobStore
store = JobStore("data/ats_playground.db")
results = store.query_by_keyword("python", min_score=75)
```

**Count tokens for a string:**
```python
from src.tokenization.counter import count_tokens
tokens = count_tokens(text)
cost_usd = tokens * 0.000003  # Claude 3.5 input rate
```

**Parse HTML to clean text:**
```python
from src.parsers.html import parse_html
clean_text = parse_html(raw_html)
```

**Chunk text by sentences:**
```python
from src.tokenization.chunking import chunk_by_sentences
chunks = chunk_by_sentences(clean_text, target_tokens=400)
```

**Track costs during assessment:**
```python
cost_tracking = {
    "job_id": "...",
    "estimated_tokens": 650,
    "actual_tokens": 673,
    "estimated_cost": 0.00195,
    "actual_cost": 0.00202,
    "api_call_time_ms": 1250
}
```

### 7.2 TUI Deployment Checklist

Before shipping Phase 1 TUI, verify:

- [ ] Textual v0.42+ installed
- [ ] Rich library available (auto-installed with Textual)
- [ ] Tests passing (including TUI unit + integration tests)
- [ ] Keybindings documented in footer ([p]ause, [q]uit, etc.)
- [ ] Error handling tested (ErrorDialog shows full traceback)
- [ ] Large dataset tested (1000+ jobs, verify no memory leaks)
- [ ] Terminal resize tested (dashboard adapts to window size)
- [ ] Color scheme works in light and dark terminals
- [ ] Accessibility: ANSI screenreader compatibility verified
- [ ] Cost tracker updates in real-time (no lag)
- [ ] Progress bars update smoothly (~2Hz, no flicker)

---

## Summary: Key Takeaways

1. **Semantic Tokens:** StateManager, Panels, Widgets, Async Workflow are architectural roles, not just classes. Each has clear responsibilities and boundaries.

2. **Centralized State:** StateManager is the source of truth. Panels observe. UI doesn't drive state; state drives UI.

3. **Async-First:** Workflow is inherently async (crawl + LLM parallel). TUI must reflect this: real-time progress, live cost tracking, non-blocking operations.

4. **Cost Transparency:** Always show token estimates before LLM calls. Track actual vs estimated for future refinement.

5. **Verification First:** Unconfirmed extractions are toxic. Require user approval before expensive operations.

6. **Single-Writer DB:** SQLite has limits. Don't run concurrent assessment processes on same database.

7. **Decision Rationale:** See **docs/ARCHITECTURE-DECISIONS.md** for detailed analysis of framework choice, chunking strategy, and other key decisions.

---

**Next:** See `.claude/rules/` files for phase-specific implementation patterns. See `docs/ARCHITECTURE-DECISIONS.md` for detailed decision rationale.

**Status:** Ready for Phase 1 TUI implementation.
