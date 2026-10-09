# Multi-Agent Phase Coordination

Agent roles during crawl, preprocess, assess, and export phases.

---

## Phase Coordination Pattern

Each phase follows: **Architect (design) → Builder (implement) → Reviewer (test)**

### Crawl Phase

**Architect:** Define CSS selectors in `config/companies.json`, plan rate limiting
**Builder:** Implement `BrowserManager`, handle Playwright lifecycle, error handling
**Reviewer:** Verify extraction rate, test pagination + edge cases

**Handoff:** `config/companies.json` → Crawled jobs in database

### Preprocess Phase

**Architect:** Decide chunking strategy, set token thresholds
**Builder:** Implement `parse_html()`, `chunk_by_sentences()`, token counting
**Reviewer:** Verify chunk sizes reasonable (100–600 tokens), check cost estimates

**Handoff:** MarkItDown output → Clean chunks + token counts

### Verify Phase

**Architect:** Define review workflow (confirm/reject/skip flow), status transitions
**Builder:** Implement `JobReviewer` interactive CLI, persist status to DB
**Reviewer:** Test interactive prompts, re-review workflow, filtering combinations

**Handoff:** User confirmations → Job reviews saved to database

### Assess Phase

**Architect:** Define assessment prompt, score categories, filtering logic
**Builder:** Implement `LLMProvider`, retries, rate limiting, cost tracking
**Reviewer:** Verify JSON parsing, score ranges, cost accuracy

**Handoff:** Assessment prompt → Results + cost metrics in database

### Export Phase

**Architect:** Define report structure (title, summary, job table, sorting)
**Builder:** Implement `export_markdown()`, filtering, sorting
**Reviewer:** Verify markdown output, summary stats accuracy

**Handoff:** Assessment data → Markdown report

---

## Handoff Checklist

Before Builder starts:
- [ ] Architect design doc reviewed
- [ ] API contracts defined
- [ ] tasks.md written + approved

Before Reviewer starts:
- [ ] All tests passing (pytest, coverage, lint)
- [ ] Commits have clear messages
- [ ] Design issues flagged to Architect if any

Before Human merges:
- [ ] Reviewer approves code quality
- [ ] No blocking issues
- [ ] Documentation updated

---

## Code Graph Tooling (Issue #325, #328)

Architect queries `code-review-graph` (MCP, global scope, project-
isolated DB) for blast-radius/structural context before wide Grep/Glob
scans in any phase's design step. Advisory only — no phase blocks on it.

## Cross-Phase Dependencies

```
CRAWL → PREPROCESS → VERIFY → ASSESS → EXPORT
  ↓        ↓           ↓        ↓        ↓
Raw    Clean+      Status   Scores   Report
HTML   Tokens      DB       DB       MD
```

**Single-Writer Rule:** Only one phase writes to database at a time (prevent locks).

---

## Error Escalation

If any phase fails 3+ times: Halt, escalate to human with context.

---

## Related

- **AGENTS.md** – Role definitions + permissions
- **DESIGN.md** – Architecture decisions
- **CLAUDE.md** – Git workflow, setup

---

**Last Updated:** 2026-09-07 (Issue #328: swap better-code-review-graph → code-review-graph)
**Status:** 106 lines; Phase 5-7 enhancements documented
