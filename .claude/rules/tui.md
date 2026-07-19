# TUI Implementation Rules

Textual-based Text User Interface for ATS Playground workflow orchestration.

**Status:** Modularized (see sub-files)

---

## Quick Navigation

- **[Architecture](tui/architecture.md)** – StateManager, Dashboard, core classes
- **[Widgets](tui/widgets.md)** – Custom UI components (ProgressBar, JobTable, CostTracker)
- **[Patterns](tui/patterns.md)** – Async, testing, error handling, performance

---

## Overview

TUI replaces verbose CLI text output with interactive dashboard showing:
1. Real-time progress (crawl → preprocess → assess → export)
2. Live cost tracking (tokens + USD)
3. Top matches inline
4. Async-aware (reflects parallel operations)

**Tech Stack:** Textual 0.42+, Rich 13.0+, Pydantic 2.5+

---

## Core Concept

**StateManager** = single source of truth for phase status, metrics, job data, cost.

Update at 0.5s intervals (not 60 FPS). Mutate only in `@work(exclusive=True)` tasks.

---

## Files

- `tui/index.md` – Overview
- `tui/architecture.md` – StateManager, Dashboard (concise reference)
- `tui/widgets.md` – UI components (reference patterns)
- `tui/patterns.md` – Async, testing, error handling, performance
- `tui.md` (this file) – Index

Original monolithic guide retained as reference in parent directory if needed.

---

**Last Updated:** 2026-07-19  
**Effort:** Split from 824 lines (6.5K tokens) to modular sub-files (~1.2K per file)
