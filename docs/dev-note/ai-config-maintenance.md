# AI Configuration Maintenance Runbook

Quarterly process for maintaining and validating AI context files.

---

## Quarterly Maintenance Schedule

**Cadence:** Every ~13 weeks (roughly once per quarter)
**Effort:** ~30 minutes per quarter
**Owner:** AI Configuration Team (rotates)

**Recommended Schedule:**
- Q1: Late March
- Q2: Late June
- Q3: Late September
- Q4: Late December

---

## Pre-Audit Checklist (5 min)

1. **Create issue** from template `.github/ISSUE_TEMPLATE/quarterly-context-audit.md`
   ```bash
   gh issue create \
     --title "Q[N] [YEAR] Context Audit" \
     --label chore,documentation,ai-configuration \
     --body "$(cat .github/ISSUE_TEMPLATE/quarterly-context-audit.md)"
   ```

2. **Assign to self** (or nominate team member)
3. **Set due date** (end of week or sprint)

---

## Audit Execution (20 min)

### 1. Run Automated Audit (2 min)

```bash
uv run python scripts/context-audit.py
```

Check output:
- **Compliant:** All 12 files within budgets? ✓ Continue
- **Warnings:** Any files at 95%+ utilization? ⚠ Flag for next sprint
- **Over-Budget:** Any files exceed budget? ✗ Fix before merging (use Phase 3 approach)

### 2. Manual Review (15 min)

Work through checklist in `.claude/audit-checklist.md`:

**File Presence (1 min):**
- [ ] All required files exist? (CLAUDE.md, DESIGN.md, AGENTS.md, etc.)
- [ ] All phase-specific rules present? (.claude/rules/*.md)

**Content Validation (5 min):**
- [ ] CLAUDE.md setup instructions up-to-date? (uv, playwright, spacy versions)
- [ ] Git workflow section matches CONTRIBUTING.md?
- [ ] Quick workflow commands runnable? (test 1–2 samples)
- [ ] DESIGN.md architecture matches code structure?

Example test:
```bash
# Verify commands in CLAUDE.md still work
uv run python -m src.cli --help
uv run pytest tests/ -v --co -q | head -5
```

**Staleness Detection (5 min):**
- [ ] Deprecated tools mentioned? (e.g., old Claude model, removed feature)
- [ ] Command examples use correct flags? (e.g., `uv run`, not `python -m`)
- [ ] API references current Claude API? (check version, pricing)
- [ ] Tech stack versions match pyproject.toml? (textual, pydantic, rich)

Example check:
```bash
# Compare documented versions with actual
grep "textual" pyproject.toml
grep "textual" .claude/rules/tui/architecture.md
```

**AI Compliance (2 min):**
- [ ] Review `docs/dev-note/ai-compliance-log.md`
- [ ] Were there violations last quarter?
- [ ] If yes: Was guidance updated?

### 3. Document Findings (3 min)

Update `.github/ISSUE_TEMPLATE/quarterly-context-audit.md` with:

```markdown
## Findings

### Compliant (✓)
- All 12 files within budgets
- No staleness detected
- Setup instructions verified

### Warnings (⚠)
- (if any)

### Required Actions
- (if any)

### Metrics
{
  "total_files": 12,
  "compliant": 12,
  "over_budget": 0,
  "utilization_percent": 39,
  "violations_found": 0
}
```

---

## Remediation (if needed) (5–15 min)

**If files are over budget:**
1. Follow Phase 3 approach (split/condense)
2. Create PR with changes
3. Re-run `scripts/context-audit.py`
4. Verify compliant before merging

**If staleness found:**
1. Update specific file (e.g., CLAUDE.md setup section)
2. Add example/test to verify command still works
3. Commit with message: `docs: update [file] for staleness`

**If compliance violations found:**
1. Add entry to `docs/dev-note/ai-compliance-log.md`
2. Update guidance to prevent recurrence
3. Document in issue comments

---

## Post-Audit (2 min)

1. **Generate final metrics:**
   ```bash
   uv run python scripts/context-audit.py
   ```

2. **Update baseline:**
   Check that `docs/dev-note/context-baseline.json` is current

3. **Schedule next audit:**
   Add calendar reminder for next quarter (13 weeks out)

4. **Close issue:**
   - Link any PRs created
   - Summarize findings in comment
   - Mark complete

**Example closure comment:**
```
## Audit Complete ✓

**Quarter:** Q3 2026
**Date:** 2026-10-19
**Status:** All files compliant

### Metrics
- Files: 12/12 compliant
- Utilization: 39%
- Violations: 0

### Actions Taken
- (if any; otherwise "None - all files current")

### Next Audit
- Scheduled for: [DATE + 13 weeks]
```

---

## Troubleshooting

### Audit Script Fails

**Error:** "No such file: docs/dev-note/"

**Fix:**
```bash
mkdir -p docs/dev-note
uv run python scripts/context-audit.py
```

**Error:** ModuleNotFoundError

**Fix:**
```bash
uv sync
uv run python scripts/context-audit.py
```

### Files Over Budget (Unexpected)

**Check:** Did someone add large example code blocks?

**Quick Fixes:**
1. Move examples to `.claude/rules/` sub-file
2. Condense verbose sections (remove redundant explanations)
3. Replace code examples with references ("See X for full code")

See Phase 3 tuning approach for detailed refactoring strategy.

### Staleness: Tech Stack Versions Changed

**Example:** pyproject.toml updated textual to 0.43, but DESIGN.md still says 0.42

**Fix:**
1. Update reference: `textual = "^0.43.0" # (was 0.42.0)`
2. Check if any patterns changed between versions (usually not)
3. Commit: `docs: update tech stack references`

### Compliance Violation Found

**Scenario:** AI suggested using removed flag `--skip-confirmed` instead of `--confirmed-only`

**Process:**
1. Add entry to `docs/dev-note/ai-compliance-log.md`:
   ```
   Date: 2026-10-19
   Violation: AI used wrong flag name
   Pattern Violated: CLAUDE.md (flag doc unclear)
   Root Cause: Flag examples scattered; no centralized reference
   Action: Consolidate flag docs in .claude/rules/cli.md
   Status: resolved (added examples)
   ```

2. Update guidance:
   - Add to `.claude/rules/cli.md`: clear flag reference table
   - Update CLAUDE.md: link to `.claude/rules/cli.md`

3. Re-run audit after fixes

---

## Ongoing Maintenance (Between Quarters)

**On every PR merge:**
- Workflow `.github/workflows/context-lint.yml` runs automatically
- If files exceed budget → PR blocked; fix required

**Between quarterly audits:**
- If AI violates pattern → Add to compliance log
- If guidance becomes stale → Update immediately; don't wait for quarterly review
- Quarterly review is comprehensive re-validation, not only opportunity to update

---

## Related Documentation

- **Audit Script:** `scripts/context-audit.py`
- **CI/CD Automation:** `.github/workflows/context-lint.yml`
- **Workflow Docs:** `docs/dev-note/context-maintenance-workflow.md`
- **Audit Checklist:** `.claude/audit-checklist.md`
- **Compliance Log:** `docs/dev-note/ai-compliance-log.md`
- **Baseline Metrics:** `docs/dev-note/context-baseline.json`

---

## Metrics SLA

**Target:** All files within budgets, utilization < 75%

| Metric | Target | Action if Exceeded |
|--------|--------|-------------------|
| Over-budget files | 0 | Fix before merge (blocking) |
| Utilization | < 75% | Schedule refactoring next sprint |
| Staleness (age of last update) | < 3 months | Update immediately |
| Compliance violations | 0 | Log + update guidance |

---

**Last Updated:** 2026-07-19
**Cadence:** Quarterly
**Next Scheduled:** 2026-10-19
