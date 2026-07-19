# DESIGN.md: ATS Playground Architecture

**Version:** 2.0 (Anthropic standards)  
**Last Updated:** 2026-07-19  
**Status:** Condensed; TUI details → `.claude/rules/tui/`

---

## 1. PRODUCT NARRATIVE

ATS Playground orchestrates 4 phases:
- **Crawl:** Extract jobs from career pages (Playwright, CSS selectors, rate-limited)
- **Preprocess:** Clean HTML → semantic chunks, estimate tokens
- **Verify:** Interactive confirmation before costly API calls
- **Assess:** Claude evaluates CV fit (scores: tech, seniority, location)
- **Export:** Markdown reports with rankings

Raw HTML ~6,000 tokens/job → clean text ~400 tokens (15× cost reduction).

**Design Philosophy:** Replace verbose text output with interactive dashboard: real-time progress, live cost tracking, top matches visible, async-aware.

---

## 2. WORKFLOW PIPELINE

```
CONFIG (companies.json + CSS selectors)
  ↓
CRAWL (Playwright + pagination)
  ↓ Raw HTML
PREPROCESS (MarkItDown + spaCy sentences + tiktoken)
  ↓ Clean chunks + token estimates
VERIFY (Interactive CLI, cost transparency)
  ↓ Confirmed jobs
ASSESS (Claude 3.5 Sonnet + rate limiting)
  ↓ Scores + actual tokens/cost
STORAGE (SQLite + FTS5)
  ↓ Queryable database
EXPORT (Markdown reports)
```

---

## 3. MODULE STRUCTURE

| Module | Purpose |
|--------|---------|
| **src/models/** | Pydantic schemas (Job, Assessment, CostMetrics) |
| **src/browser/** | Playwright automation (BrowserManager) |
| **src/parsers/** | HTML cleaning (MarkItDown → BeautifulSoup) |
| **src/tokenization/** | NLP chunking (spaCy) + token counting (tiktoken) |
| **src/verification/** | Interactive review before LLM |
| **src/llm/** | Claude API client (provider-agnostic) |
| **src/storage/** | SQLite (FTS5, export, queries) |
| **src/cli.py** | Typer CLI orchestration |
| **src/tui/** | Textual dashboard (Phase 1+) |

---

## 4. KEY DECISIONS

- **Semantic Chunking:** Split at sentences (spaCy), not fixed tokens. Preserves meaning; chunk sizes 100–600 tokens (intentional).
- **Pre-API Cost Transparency:** Show user estimate + cost before LLM call. tiktoken estimates; actual Claude tokens tracked in cost_tracking table.
- **Confirmation Required:** Assessment only runs on jobs where status == "confirmed". Prevents wasting API quota on low-confidence extractions.
- **Single-Writer SQLite:** Don't run concurrent assessment processes on same DB (deadlock risk). Use queue or single-process pattern.
- **Async-First TUI:** StateManager is source of truth. Panels poll every 0.5s. All I/O in `@work(exclusive=True)` tasks.

**TUI Details:** See `.claude/rules/tui/` for StateManager, Panel, Widget, Async Workflow specifications.

---

## 5. PHASE-SPECIFIC RULES

See `.claude/rules/` for detailed patterns:

- **crawl.md** – Playwright, CSS selectors, rate limiting
- **preprocess.md** – MarkItDown, spaCy, token counting
- **verify.md** – Interactive CLI, cost transparency, status flow
- **assess.md** – Claude API, prompts, rate limiting
- **storage.md** – SQLite schema, FTS5, markdown export
- **cli.md** – Typer patterns, command organization
- **multi-agent.md** – Phase coordination across agent roles

---

## 6. ANTI-PATTERNS & BOUNDARIES

### NEVER DO THIS

- **Don't assess unconfirmed jobs.** Use `--confirmed-only` (default).
- **Don't run concurrent assessment processes.** SQLite single-writer. Use queue/single-process.
- **Don't send raw HTML to Claude.** Always preprocess (clean + chunk). Raw HTML ~6,000 tokens.
- **Don't skip verification.** Show cost estimate before API calls.
- **Don't force uniform token chunks.** Split at sentences (spaCy); chunks vary 100–600 tokens intentionally.
- **Don't re-assess already reviewed jobs.** Use `--skip-assessed`, `--skip-rejected`.
- **Don't commit to main directly.** Feature branch workflow enforced by pre-commit hook (see CLAUDE.md).

### TUI-Specific

- **Don't mutate StateManager outside `@work(exclusive=True)`.** Causes race conditions. Single-writer pattern only.
- **Don't block main Textual thread.** All I/O async (crawl, LLM, DB).
- **Don't render 1000+ rows in DataTable.** Use pagination; show top 100.
- **Don't update UI at 60 FPS.** Poll StateManager at 0.5s (2 Hz) to prevent flicker + CPU thrashing.

---

## 7. ENVIRONMENT & DEPLOYMENT

**Tech Stack:**
- **Browser:** Playwright (async, JS rendering)
- **HTML cleaning:** MarkItDown (primary), BeautifulSoup (fallback)
- **NLP:** spaCy (sentence segmentation)
- **Tokens:** tiktoken (estimates), Claude API (actual)
- **DB:** SQLite with FTS5
- **LLM:** Claude 3.5 Sonnet ($0.003 per 1M input tokens)
- **CLI:** Typer (async-ready)
- **TUI:** Textual 0.42+, Rich 13.0+

**Setup:**
```bash
uv sync
uv run python -m spacy download en_core_web_md
uv run playwright install chromium
cp .env.example .env  # Set ANTHROPIC_API_KEY
uv run python src/storage/db.py --init
```

---

## Summary: Key Takeaways

1. **4-phase workflow** with cost-transparency, user confirmation, and async-first design
2. **Semantic chunking** (sentences, not fixed tokens) for better preservation of meaning
3. **Single-writer SQLite** to prevent deadlocks under concurrent load
4. **StateManager as source of truth** for TUI state (polling every 0.5s)
5. **All I/O non-blocking** (Textual `@work` decorator for async tasks)
6. **TUI modularized** into architecture/widgets/patterns sub-files (see `.claude/rules/tui/`)

---

**See Also:**
- **CLAUDE.md** – Project setup, quick workflows, git process
- **AGENTS.md** – Agent roles (Architect, Coder, Reviewer, Orchestrator)
- **.claude/rules/** – Phase-specific patterns + TUI details
