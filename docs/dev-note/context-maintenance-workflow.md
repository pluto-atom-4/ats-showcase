# Context Maintenance Workflow

**Automation:** GitHub Actions + Python Audit Script  
**Frequency:** On every push/PR to main/dev  
**Owner:** AI Configuration Team

---

## Overview

Automated validation of AI context files (CLAUDE.md, DESIGN.md, AGENTS.md, copilot-instructions.md, .claude/rules/) ensures they remain:
- Within recommended token budgets
- Current with codebase (no stale commands/examples)
- Linked and consistent across files

**Workflow:** `.github/workflows/context-lint.yml`  
**Audit Script:** `scripts/context-audit.py`  
**Output:** Pass/Warn/Fail with actionable recommendations

---

## How It Works

### Trigger Events

- **Push to main/dev** – Automatically runs audit
- **Pull Request to main/dev** – Runs audit + comments on PR with results
- **Path filters** – Only runs if context files changed

```yaml
on:
  push:
    branches: [main, dev]
    paths:
      - "CLAUDE.md"
      - "DESIGN.md"
      - "AGENTS.md"
      - ".github/copilot-instructions.md"
      - ".claude/**/*.md"
```

### Checks Performed

1. **File Presence** – All required context files exist
2. **Token Count Audit** – Run `scripts/context-audit.py`
   - Scan all .md files
   - Estimate tokens (chars / 4)
   - Compare against budgets in BUDGETS dict
3. **Parse Results** – Extract over_budget, warnings, utilization from JSON
4. **Fail/Warn Decision**
   - ❌ **Fail if:** Any file exceeds budget (reject PR/push)
   - ⚠️  **Warn if:** Utilization > 95% (pass but flag for next sprint)
   - ✓ **Pass if:** All compliant

### Output

**On Push (main/dev):**
- Workflow runs silently if compliant
- Workflow fails if over budget (requires fix + retest)

**On Pull Request:**
- Workflow runs on each commit
- Comments on PR with audit summary table
- Shows file-by-file status (✓ compliant, ⚠ warning, ❌ over)
- Links to detailed findings

**Example PR Comment:**
```
## 📋 Context Files Audit

**Utilization:** 104% of recommended budget
**Files:** 12 audited
**Status:** ❌ 4 file(s) over budget

### Over Budget
- `DESIGN.md: EXCEEDS budget (185%)`
- `.claude/rules/tui.md: EXCEEDS budget (217%)`
- `AGENTS.md: EXCEEDS budget (164%)`
- `.github/copilot-instructions.md: EXCEEDS budget (147%)`

### File Summary
| File | Tokens | Budget | Status |
|------|--------|--------|--------|
| `CLAUDE.md` | 1305 | 1500 | ✓ |
| `DESIGN.md` | 5563 | 3000 | ❌ |
| ...
```

---

## Budget Configuration

Budgets defined in `scripts/context-audit.py`:

```python
BUDGETS = {
    "CLAUDE.md": 1500,
    "DESIGN.md": 3000,
    "AGENTS.md": 1000,
    ".github/copilot-instructions.md": 1000,
    ".claude/rules/crawl.md": 2000,
    # ... etc
}
```

**To adjust budgets:** Edit BUDGETS dict in audit script, commit, workflow auto-runs.

---

## Running Locally

Test workflow behavior locally before pushing:

```bash
# Run audit script
uv run python scripts/context-audit.py

# Output
🔍 Auditing context files...
✓ CLAUDE.md
   Lines: 148 | Tokens: 1305 | Budget: 1500
   87% of budget

✗ DESIGN.md
   Lines: 581 | Tokens: 5563 | Budget: 3000
   185% of budget

# ... more files ...

📊 Report exported to: docs/dev-note/context-baseline.json
```

Check JSON output:

```bash
cat docs/dev-note/context-baseline.json | jq '.summary'
```

```json
{
  "total_files": 12,
  "compliant": 7,
  "warnings": 1,
  "over_budget": 4,
  "total_tokens": 21887,
  "total_budget": 21000,
  "utilization_percent": 104
}
```

---

## Workflow Failures

### Case 1: Missing Required File

**Error:**
```
❌ Missing required files: AGENTS.md
```

**Fix:**
1. Restore file from git: `git checkout AGENTS.md`
2. Or create with proper structure (see `.claude/audit-checklist.md`)
3. Commit and push

### Case 2: File Over Budget

**Error:**
```
❌ Context files exceed recommended budgets.
See audit report: docs/dev-note/context-baseline.json
```

**Fix:**
1. Review findings in `docs/dev-note/ai-config-audit-findings.md`
2. Trim or refactor file:
   - Condense verbose sections
   - Extract details to `.claude/rules/` sub-files
   - Remove redundant examples
3. Re-run audit locally: `uv run python scripts/context-audit.py`
4. Verify compliant: Check JSON `summary.over_budget == 0`
5. Commit and push

### Case 3: High Utilization (Warning)

**Warning:**
```
⚠  Context utilization at 98% (approaching limit)
Consider refactoring for next sprint
```

**Action:**
- PR merges, but flag for next sprint
- Schedule lightweight refactoring in next planning
- Not blocking; for awareness

### Case 4: Workflow Timeout

**Rare:** If audit script hangs:
1. Check `scripts/context-audit.py` for infinite loops
2. Manually run: `timeout 30 uv run python scripts/context-audit.py`
3. If timeout, add explicit timeout to workflow step

---

## Extending the Workflow

### Add Custom Checks

Edit `.github/workflows/context-lint.yml`:

```yaml
- name: Custom check (example)
  run: |
    # Verify specific guidance exists
    grep -q "DO NOT" CLAUDE.md || echo "⚠  CLAUDE.md missing DO NOT section"

    # Verify all links are valid
    # grep -o '\[.*\](' CLAUDE.md | check_links.sh
```

### Add Frontmatter Validation

If using YAML frontmatter in .md files:

```yaml
- name: Validate frontmatter
  run: |
    for file in CLAUDE.md DESIGN.md AGENTS.md; do
      head -5 "$file" | grep -q "^---" || echo "⚠  $file missing frontmatter"
    done
```

### Notify on Failure

Add Slack/email notification:

```yaml
- name: Notify on failure
  if: failure()
  uses: slackapi/slack-github-action@v1
  with:
    webhook-url: ${{ secrets.SLACK_WEBHOOK }}
    payload: |
      {
        "text": "Context audit failed on ${{ github.ref }}"
      }
```

---

## Quarterly Maintenance

Workflow automates *detection*; quarterly review is *action*:

1. **Every 13 weeks** (start of sprint):
   - Open issue: "Q3 2026 Context Audit"
   - Run checklist from `.claude/audit-checklist.md`
   - Manual review: Are commands still accurate? Are examples stale?
   - Update findings in `docs/dev-note/ai-config-audit-findings.md`
   - Apply fixes if needed
   - Close issue

2. **Ad-hoc**: If workflow flags violations
   - Review PR comment
   - Fix before merging
   - No manual action needed for CI passes

---

## Troubleshooting

### Workflow doesn't run

**Issue:** Pushed context file but workflow didn't trigger.

**Check:**
1. Verify branch is main/dev: `git branch -a`
2. Verify path matches filter: `.github/workflows/context-lint.yml` → `paths:`
3. Check Actions tab in GitHub for skipped runs

**Fix:** Re-push or manually trigger via GitHub UI:
- Go to Actions → Context Files Lint & Audit → Run workflow

### Audit script errors

**Issue:** "ModuleNotFoundError: No module named 'pathlib'"

**Fix:**
```bash
uv sync
uv run python scripts/context-audit.py
```

**Issue:** "No such file: docs/dev-note/"

**Fix:**
```bash
mkdir -p docs/dev-note
uv run python scripts/context-audit.py
```

### PR comment not appearing

**Issue:** Workflow runs but no comment on PR.

**Check:**
1. Workflow permissions: Settings → Actions → General → Workflow permissions → Read and write

**Fix:**
```yaml
permissions:
  pull-requests: write
  contents: read
```

---

## Related Documentation

- **Audit Checklist:** `.claude/audit-checklist.md` – Manual inspection items
- **Audit Findings:** `docs/dev-note/ai-config-audit-findings.md` – Latest findings + recommendations
- **Baseline Metrics:** `docs/dev-note/context-baseline.json` – Current token counts
- **Audit Script:** `scripts/context-audit.py` – Python implementation

---

## Metrics & SLA

**Expected Behavior:**
- ✓ Compliant: All files within budgets; workflow passes
- ⚠️  Warning: Utilization 95–100%; workflow passes but flags for next sprint
- ❌ Failing: Any file over budget; PR blocks until fixed

**Response Time:**
- Over-budget failures: Fix within same PR (blocking)
- Warnings: Addressed in next sprint (non-blocking)
- Quarterly audit: 30 min per quarter to review + document

---

**Last Updated:** 2026-07-19  
**Status:** Deployed  
**Owner:** AI Configuration Team
