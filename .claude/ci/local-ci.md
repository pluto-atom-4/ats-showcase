# Local CI Workflow

Developer-facing CI checks that run locally before pushing.

---

## Quick Start

```bash
# Run all checks on staged files
bash .claude/scripts/run-local-ci.sh

# Run with tests included
bash .claude/scripts/run-local-ci.sh --tests

# Run tests in parallel (non-perf with xdist, then perf serially)
bash .claude/scripts/run-local-ci.sh --tests-workers=auto

# Run with strict mypy mode
bash .claude/scripts/run-local-ci.sh --strict
```

---

## What Gets Checked

### Pre-commit Hooks (on staged files)
| Hook | Purpose | Fail? |
|------|---------|-------|
| Trailing whitespace | Remove trailing spaces | Auto-fix |
| End-of-file fixer | Ensure file ends with newline | Auto-fix |
| detect-secrets | Scan for leaked credentials | Yes |
| bandit | Security analysis (high severity only) | Yes |
| ruff | Format + lint + sort imports | Auto-fix + report |
| mypy | Type checking (Python 3.12) | Yes |

### Optional: Tests
- Only if `--tests` flag used
- Runs pytest with coverage report
- Required before merge
- `--tests-workers=N|auto` implies `--tests`: runs `-m "not perf" -n N`, then `-m perf -n 0`
- Default stays serial (`pytest tests/`). On low-core machines parallel plus a serial perf phase can be slower
- Invalid N exits 1 before any check runs

### Optional: Strict Mode
- Only if `--strict` flag used
- Enables mypy --strict for all files
- Catches more type issues

---

## Workflow

1. **Make changes**
   ```bash
   git add src/myfeature.py
   ```

2. **Run local CI**
   ```bash
   bash .claude/scripts/run-local-ci.sh
   ```

3. **Fix issues (auto-fixed hooks)**
   - ruff fixes formatting/imports automatically
   - Trailing whitespace auto-removed
   - Re-stage fixed files: `git add -A`

4. **Fix issues (manual)**
   - Address mypy errors in code
   - Fix bandit security issues
   - Handle detect-secrets findings

5. **Commit**
   ```bash
   git commit -m "feat: description"
   git push origin feat/branch-name
   ```

---

## Troubleshooting

### Pre-commit Hooks Won't Install
```bash
# Reinstall git hooks
bash .claude/skills/pre-commit-enforce/setup.sh
```

### Skip Specific Hook (if needed)
```bash
# Skip ruff linting
SKIP=ruff git commit -m "message"

# Skip multiple hooks
SKIP=ruff,mypy git commit -m "message"
```

### Pre-commit Hook Failed on Commit
```bash
# Run local CI to catch issues first
bash .claude/scripts/run-local-ci.sh

# Fix issues, re-stage, then commit
git add .
git commit -m "message"
```

### mypy Failing But Code Looks OK
```bash
# Try strict mode to see more issues
bash .claude/scripts/run-local-ci.sh --strict

# Or run mypy directly on a file
uv run mypy src/your_file.py --ignore-missing-imports
```

### Bandit Security Warning
Check `.pre-commit-config.yaml` for `-lll` (high severity only).
- Most warnings safe to ignore in test/demo code
- Security issues in src/ should be addressed

---

## Integration with Git Hooks

Pre-commit hooks also run on `git commit`:
- Automatically on staged files
- Fail if checks don't pass
- Same checks as `run-local-ci.sh`

**To bypass (use cautiously):**
```bash
git commit --no-verify -m "message"  # Not recommended
```

---

## Pre-Commit vs Local CI Script

| Aspect | Git Hook | Local CI Script |
|--------|----------|-----------------|
| When | On `git commit` | Manually before commit |
| Files | Staged only | Staged only (by default) |
| Speed | Fast (staged files) | Fast (staged files) |
| Control | Automatic | Manual (can add --tests) |
| Output | Inline | Formatted, easy to read |

**Best practice:** Run `bash .claude/scripts/run-local-ci.sh` before committing to catch issues early.

---

## Configuration

### Hook Config Location
- `.pre-commit-config.yaml` – Hook definitions, stages, arguments

### Modify Hooks
Edit `.pre-commit-config.yaml`:
- Add new hooks from pre-commit registry
- Adjust mypy args
- Change bandit severity level

After editing:
```bash
bash .claude/skills/pre-commit-enforce/setup.sh
uv run pre-commit validate-config
```

---

## Related

- **CLAUDE.md** – Project setup + quick commands
- **Pre-commit Registry** – https://pre-commit.com/hooks.html
- **GitHub Workflows** – `.github/workflows/quality-checks.yml` (runs in CI)

---

**Last Updated:** 2026-07-28
