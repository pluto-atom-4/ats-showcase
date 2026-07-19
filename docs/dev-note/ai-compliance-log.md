# AI Compliance Log

Track instances where AI assistants violate documented patterns or guidance. Use violations as signal to update outdated guidance.

---

## Format

```
Date: YYYY-MM-DD
Violation: [Brief description]
Pattern Violated: [Which file/section documents this]
Root Cause: [Why did AI miss/violate the rule?]
Action: [Update guidance, clarify pattern, add example]
Status: [open/resolved]
```

---

## Entries

### Example Entry (Template)

**Date:** 2026-07-19
**Violation:** AI suggested using `--skip-confirmed` flag instead of `--confirmed-only` for filtering
**Pattern Violated:** CLAUDE.md § NEVER DO THIS (incorrect flag name)
**Root Cause:** Flag documentation in CLAUDE.md unclear; example in code-patterns.md used wrong flag
**Action:** Clarified flag names in CLAUDE.md; added examples to .claude/rules/cli.md
**Status:** resolved

---

## Process

1. **Spot violations:** During code review or usage, note if AI violates documented pattern
2. **Log entry:** Add to this file with date + context
3. **Investigate:** Why did guidance miss? Stale? Unclear? Contradictory?
4. **Update:** Fix documentation (clarify, add example, reorganize)
5. **Close:** Mark resolved; note which doc was updated

---

## Quarterly Review

Every 13 weeks, review log:
- Identify patterns (do violations cluster around specific areas?)
- Update guidance if needed
- Archive resolved entries to dated section below

---

## Archived Entries

(Entries resolved in previous quarters)

---

**Last Updated:** 2026-07-19
**Entries:** 0 (baseline)
**Next Review:** 2026-10-19
