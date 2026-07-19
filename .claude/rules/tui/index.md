# TUI Implementation (Index)

Textual-based Text User Interface for ATS Playground workflow orchestration.

**Status:** Modular reference (architecture, widgets, patterns extracted from monolithic guide)

---

## Quick Links

- **[Architecture](architecture.md)** – StateManager, Dashboard, core classes (concise)
- **[Widgets](widgets.md)** – Custom UI components (ProgressBar, JobTable, CostTracker)
- **[Patterns](patterns.md)** – Async, testing, error handling, performance

---

## Overview

TUI replaces verbose CLI output with interactive dashboard:

1. **Real-time progress** (crawl, preprocess, assess, export phases)
2. **Live cost tracking** (tokens + USD as jobs are processed)
3. **Top matches visible** (best jobs shown inline)
4. **Async-aware** (reflects parallel crawl + LLM calls)

**Tech Stack:** Textual 0.42+, Rich 13.0+, Pydantic 2.5+

---

## Core Concept: StateManager

Single source of truth for:
- Phase status (idle → running → completed/error)
- Metrics (progress %, ETA, token count, cost)
- Job data (id, title, company, scores)
- Top matches (best 5 jobs by score)

**Thread-safe:** Use `@work(exclusive=True)` for async state mutations.

---

## Dashboard Layout

```
┌──────────────────────────────┐
│ Header (status, total cost)   │
├──────────────────────────────┤
│ Phase Indicator               │
├──────────────────────────────┤
│ Active Panel (crawl/assess/..)│
│ ├─ Progress bar + ETA         │
│ ├─ Job list                   │
│ └─ Cost tracker               │
├──────────────────────────────┤
│ Footer [p]ause [q]uit         │
└──────────────────────────────┘
```

---

## Key Patterns

- **Async:** All I/O non-blocking (`@work(exclusive=True)`)
- **Updates:** 0.5s refresh (not 60 FPS)
- **State:** Only one task mutates StateManager
- **Errors:** All phases catch exceptions, update state, notify user
- **Backward Compat:** Text mode still works (auto-detect TTY)

---

## Files

```
.claude/rules/tui/
├── index.md           (this file)
├── architecture.md    (StateManager, Dashboard)
├── widgets.md         (UI components)
└── patterns.md        (async, testing, error handling)
```

Original monolithic `tui.md` retained for full implementation reference (not loaded by default).

---

**Last Updated:** 2026-07-19
**Token Budget:** ~1.2K (split from 6.5K original)
