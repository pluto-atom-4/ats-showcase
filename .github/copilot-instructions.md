---
applyTo: '**/*'
model: claude-sonnet-5
context: minimal
---

# Copilot Instructions

Global rules for GitHub Copilot IDE completions. Path-scoped rules in [.github/instructions/](instructions/).

**Key References:**
- [CLAUDE.md](../CLAUDE.md) – Project setup, commands, git workflow
- [AGENTS.md](../AGENTS.md) – Agent roles, permissions, model configuration
- [CONSTRAINTS.md](.claude/CONSTRAINTS.md) – Core constraints (NEVER/ALWAYS rules)
- [.claude/rules/](.claude/rules/) – Phase-specific guidance (crawl, preprocess, assess, etc.)
- [.github/instructions/](instructions/) – Instruction files (CLI, code patterns, issue workflow)

**Workflow:** Architect (plan) → Builder (implement) → Reviewer (verify). Gate 1 + Gate 2 before merge.

### WRAP Pattern

**Write** clear requirements in issues. **Refine** with Architect before coding. **Atomic** tasks in Phase 1–4. **Pair** Builder + Reviewer at verification gates.

## Coding Conventions

### DTO Pattern (Preferred)

Use `@dataclass` for data transfer objects with type hints:

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class JobAssessment:
    """Assessment result for a single job."""
    job_id: str
    match_score: int  # 0-100
    categories: dict[str, int] = field(default_factory=dict)
    reasoning: str = ""
    created_at: datetime = field(default_factory=datetime.now)
```

**Why**: Type safety, JSON-serializable, clear contracts for API boundaries.

### Error Handling Schema

**✅ Use these patterns:**
- Transient errors (429, 500–503): Backoff + retry (max 3 attempts)
- Auth errors (401): Fail immediately, check credentials
- Validation errors: Log + skip, continue processing
- Async context managers: Always ensure resource cleanup

**❌ Avoid these patterns:**
- Bare `except Exception` catches
- Silent failures or `pass` in error handlers
- Retry loops exceeding 3 attempts without exponential backoff
- Mixing sync/async in same function

**Example:**

```python
async def assess_job_with_retry(job, cv, max_attempts=3):
    """Retry with exponential backoff."""
    for attempt in range(max_attempts):
        try:
            return await provider.assess_job(cv, job)
        except RateLimitError:
            await asyncio.sleep(2 ** attempt)
        except AuthError:
            raise  # Fail immediately
```

### Coding Do/Do Not

| Do | Do Not |
|----|--------|
| Log before every API call (cost transparency) | Hardcode API keys or secrets |
| Test with `--limit 1` first | Run full crawl for testing |
| Use `async with` for resource cleanup | Mix sync/async in same module |
| Validate JSON responses before storing | Predict token counts; use tiktoken |
| Test locally with `pytest -v` | Skip tests or use `--no-cov` in CI |
| Commit frequently with clear messages | Force-push or hard-reset |
| Query via `JobStore` abstraction | Write raw SQL queries |

---

## Tool Constraints (sync with settings.json)

**Denied (blocked):**
- `Bash(rm -rf *)` – Never recursive delete
- `Bash(git push --force*)` – Never force-push
- `Bash(git reset --hard*)` – Never hard-reset

**Ask (confirm first):**
- `Bash(rm *)` – Delete files
- `Bash(git push *)` – Push any changes
- `Bash(git rebase *)` – Rebase branches
- `Bash(npm *)` – NPM commands

**Updated:** 2026-08-30 (Issue #305: Coding conventions + DTO/error patterns)
