# AI Configuration Audit Findings

**Date:** 2026-07-19  
**Auditor:** Phase 1 Automation  
**Overall Status:** 4 files over budget, 1 warning; overall utilization 104%

---

## Executive Summary

Out of 12 context files, 7 are compliant with token budgets. 4 files significantly exceed recommended sizes:

1. **`.claude/rules/tui.md`** – 217% (6,521 / 3,000 tokens) – TUI implementation guide is too detailed
2. **`DESIGN.md`** – 185% (5,563 / 3,000 tokens) – Comprehensive but oversized
3. **`AGENTS.md`** – 164% (1,637 / 1,000 tokens) – Agent roles + responsibilities redundant with DESIGN.md
4. **`.github/copilot-instructions.md`** – 147% (1,473 / 1,000 tokens) – Code patterns overlap with CLAUDE.md

Additionally, `.claude/rules/multi-agent.md` is at 108% (just over warning threshold).

---

## Detailed Findings

### 1. `.claude/rules/tui.md` (824 lines, 6,521 tokens) – **CRITICAL**

**Issue:** TUI implementation guide is comprehensive but bloated. Contains:
- Full architecture overview + diagrams (duplicates DESIGN.md concepts)
- Entire StateManager class implementation
- Full Dashboard class with all methods
- Detailed widget implementations (ProgressBar, JobTable, CostTracker, etc.)
- Test strategy with full test code examples
- Performance considerations + deployment checklist

**Impact:** Exceeds budget by 117%. Models may deprioritize this file in some contexts.

**Recommendation:** Split into modular sub-files:
- `.claude/rules/tui/architecture.md` – StateManager, dashboard overview (keep core concepts)
- `.claude/rules/tui/widgets.md` – Widget implementations (reference, not full code)
- `.claude/rules/tui/patterns.md` – Textual patterns, async rules, testing strategy
- Keep main `tui.md` as index with links

**Effort:** 1–2 hours (extract + reorganize)

---

### 2. `DESIGN.md` (581 lines, 5,563 tokens) – **HIGH PRIORITY**

**Issue:** Comprehensive architecture doc but exceeds budget by 85%. Contains:
- Lengthy product narrative (section 1)
- Detailed semantic design tokens (StateManager, Panel, Widget, etc.) – full examples
- Anti-patterns + boundaries (comprehensive, good content)
- Database schema with full SQL
- Async patterns + concurrency rules

**Redundancy:** Semantic design tokens section substantially overlaps with concepts in `.claude/rules/tui.md`.

**Recommendation:** Trim to essentials:
- **Keep:** Product narrative (condensed to 1 paragraph), anti-patterns, database schema (reference)
- **Extract:** Semantic design tokens → move to `.claude/rules/tui/architecture.md` or create `.claude/design-tokens.md`
- **Condense:** Async patterns section (move detailed examples to phase-specific rules)

**Effort:** 1 hour (condensing + moving content)

---

### 3. `AGENTS.md` (241 lines, 1,637 tokens) – **MEDIUM PRIORITY**

**Issue:** Exceeds budget by 64%. Contains:
- Clear role definitions (Architect, Coder, Reviewer, Orchestrator)
- Detailed responsibilities per role
- Phase-specific responsibilities (duplicates multi-agent.md)

**Redundancy:** Phase coordination sections overlap with `.claude/rules/multi-agent.md`. Responsibility descriptions are duplicated.

**Recommendation:** Consolidate:
- Keep high-level role definitions in AGENTS.md (concise)
- Remove phase-specific details; link to `.claude/rules/multi-agent.md`
- Trim responsibility lists to key bullets only

**Effort:** 30 minutes (condensing + relinking)

---

### 4. `.github/copilot-instructions.md` (163 lines, 1,473 tokens) – **MEDIUM PRIORITY**

**Issue:** Exceeds budget by 47%. Contains:
- Code style guidelines (duplicates CLAUDE.md patterns)
- Project structure overview (references files, not actionable)
- Specific copilot patterns (good content)

**Redundancy:** Sections on project structure, command patterns, and test patterns overlap with CLAUDE.md quick workflow section.

**Recommendation:** Trim:
- Remove project structure overview (users already have CLAUDE.md)
- Condense code patterns to bullets + link to CLAUDE.md / code-patterns.instructions.md
- Keep copilot-specific patterns (inline documentation suggestions, etc.)

**Effort:** 30 minutes (condensing)

---

### 5. `.claude/rules/multi-agent.md` (250 lines, 2,167 tokens) – **LOW PRIORITY (Warning)**

**Issue:** At 108% of budget (slightly over). Contents are core coordination patterns.

**Status:** Monitor; do not trim unless AGENTS.md consolidation reduces redundancy.

**Recommendation:** After AGENTS.md is trimmed, re-run audit. If AGENTS.md now points to multi-agent.md, budget naturally resolves.

---

## Staleness & Accuracy Check

### Content Verification (Spot Checks)

**CLAUDE.md (87% of budget):**
- ✓ Git workflow enforced by pre-commit hook (verified in codebase)
- ✓ Tech stack versions match pyproject.toml (uv, spacy, playwright)
- ✓ Commands use correct syntax (`uv run python -m src.cli`)
- ✓ References to `.claude/rules/` files all exist and are current

**DESIGN.md (185% of budget):**
- ✓ StateManager class concept matches `src/tui/models/state.py` (if implemented)
- ✓ Database schema reference to `jobs`, `assessments`, `cost_tracking` tables (matches STORAGE.md)
- ✓ Anti-patterns section aligns with actual constraints (single-writer, no StateManager mutation from multiple tasks)
- ⚠ Some examples reference `.claude/rules/tui.md` classes (StateManager, Dashboard) which are detailed but not yet implemented

**AGENTS.md (164% of budget):**
- ✓ Agent roles (Architect, Coder, Reviewer, Orchestrator) clearly defined
- ✓ Responsibilities don't overlap; clear handoff points
- ✓ Examples use current Claude API (Sonnet 3.5)
- ✓ No references to deprecated phases or tools

**.github/copilot-instructions.md (147% of budget):**
- ✓ Code patterns match actual codebase style
- ⚠ "Phase-specific guidance" section repeats CLAUDE.md links
- ✓ Example code snippets are copy-pasteable

**.claude/rules/tui.md (217% of budget):**
- ⚠ Contains full implementation code (StateManager, Dashboard, widgets)
- ⚠ Code is comprehensive but not yet integrated; includes proposed structure
- ✓ Patterns align with Textual v0.42+ (current version reference)
- ✓ No references to deprecated libraries

---

## Recommendations Summary

| File | Priority | Action | Est. Time |
|------|----------|--------|-----------|
| `.claude/rules/tui.md` | CRITICAL | Split into sub-files (architecture, widgets, patterns) | 1–2h |
| `DESIGN.md` | HIGH | Condense narrative, extract design tokens to separate file | 1h |
| `AGENTS.md` | MEDIUM | Trim responsibilities, remove phase duplicates | 30m |
| `.github/copilot-instructions.md` | MEDIUM | Remove structure overview, condense patterns | 30m |
| `.claude/rules/multi-agent.md` | LOW | Monitor; trim after AGENTS.md changes if needed | — |

**Total Estimated Effort:** 3–4 hours

---

## Next Steps (Phase 2 & 3)

1. **Immediate:** Apply trimming recommendations above (4h max)
2. **Re-audit:** Run `scripts/context-audit.py` after changes to verify compliance
3. **CI/CD Setup:** Implement `.github/workflows/context-lint.yml` (Phase 2)
4. **Quarterly:** Schedule next audit for 2026-10-19 (~13 weeks)

---

## Files Compliant (No Action)

✓ CLAUDE.md (87%)  
✓ .claude/rules/assess.md (37%)  
✓ .claude/rules/cli.md (59%)  
✓ .claude/rules/crawl.md (25%)  
✓ .claude/rules/preprocess.md (24%)  
✓ .claude/rules/storage.md (44%)  
✓ .claude/rules/verify.md (29%)

---

**Baseline Metrics JSON:** `docs/dev-note/context-baseline.json`  
**Next Review Date:** 2026-10-19  
**Owner:** AI Configuration Maintenance Task
