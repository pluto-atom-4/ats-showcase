---
name: Quarterly AI Config Audit
about: Maintain and validate AI context files (CLAUDE.md, DESIGN.md, etc.)
title: "Q[N] [YEAR] Context Audit"
labels: chore, documentation, ai-configuration
---

## Quarterly AI Configuration Audit

**Quarter:** Q[N] [YEAR]
**Due Date:** [DATE]
**Owner:** @[assignee]

---

## Checklist

### File Presence & Size
- [ ] CLAUDE.md exists and within budget (< 1.5K tokens)
- [ ] DESIGN.md exists and within budget (< 3K tokens)
- [ ] AGENTS.md exists and within budget (< 1K tokens)
- [ ] .github/copilot-instructions.md exists and within budget (< 1K tokens)
- [ ] .claude/rules/* all exist and within budgets
- [ ] .claude/profiles.json exists (role-specific configs)

### Content Validation

**CLAUDE.md:**
- [ ] Setup instructions match current tech stack (uv, playwright, spacy)
- [ ] Git workflow section matches current CONTRIBUTING.md
- [ ] Quick workflow commands are runnable (test 1–2 samples)
- [ ] Phase-specific rules links are valid

**DESIGN.md:**
- [ ] Architecture overview matches actual code structure
- [ ] Anti-patterns section reflects current DO NOTs
- [ ] All referenced file paths exist

**AGENTS.md:**
- [ ] Agent roles clearly defined
- [ ] Responsibilities don't overlap
- [ ] Examples use current tech (Typer, Playwright, Claude API)

**.claude/rules/***
- [ ] Each file has "Verification Commands" section
- [ ] Example commands are copy-pasteable
- [ ] Tech stack references match current versions
- [ ] No contradictions between files

### Staleness Detection

- [ ] Last updated dates are recent (< 3 months)
- [ ] Deprecated tools or libraries mentioned?
- [ ] Command examples use correct flags/syntax
- [ ] API endpoint examples match current Claude API
- [ ] Database schema examples match current schema

### Metrics & Reporting

- [ ] Run `uv run python scripts/context-audit.py`
- [ ] All files within token budgets? (Verify JSON output)
- [ ] Overall utilization < 75%? (Alert if approaching limit)
- [ ] No over-budget files

### AI Compliance

- [ ] Review `docs/dev-note/ai-compliance-log.md`
- [ ] Were there violations last quarter?
- [ ] If yes: Was guidance updated to prevent recurrence?
- [ ] Log any new violations found during audit

### Completion

- [ ] Audit checklist (.claude/audit-checklist.md) reviewed
- [ ] Findings documented in comment below
- [ ] PR created if updates needed (or N/A if compliant)
- [ ] Metrics updated in `docs/dev-note/context-baseline.json`
- [ ] Close issue

---

## Findings

(Add comments with any issues found, files needing updates, recommendations)

---

## Metrics

```json
{
  "quarter": "Q[N] [YEAR]",
  "date": "[YYYY-MM-DD]",
  "total_files": 12,
  "compliant": 12,
  "over_budget": 0,
  "utilization_percent": 39,
  "violations_found": 0
}
```

---

## References

- **Audit Checklist:** `.claude/audit-checklist.md`
- **Audit Script:** `scripts/context-audit.py`
- **Previous Findings:** `docs/dev-note/ai-config-audit-findings.md`
- **Compliance Log:** `docs/dev-note/ai-compliance-log.md`
- **Workflow:** `docs/dev-note/context-maintenance-workflow.md`

---

**Effort:** ~30 minutes
**Cadence:** Every ~13 weeks
**Next Audit:** [DATE + 13 weeks]
