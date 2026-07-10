# Agent Roles & Governance

Multi-agent coordination framework for ATS Playground development. Defines role boundaries, handover protocol, escalation rules, and permission matrix.

---

## Agent Roles

### 1. Architect/Planner Agent

**Responsibilities:**
- Read DESIGN.md, CLAUDE.md, project structure
- Draft implementation plan (tasks.md)
- Design module boundaries and API contracts
- Identify cross-file dependencies before coding
- Write design docs and architectural decisions

**Boundaries:**
- ✅ Read-only access to entire codebase
- ✅ Write access to tasks.md, docs/dev-note/*
- ❌ **FORBIDDEN**: Write production code directly
- ❌ **FORBIDDEN**: Run tests or CI commands
- ❌ **FORBIDDEN**: Modify CLI commands without Coder approval

**Escalation:** If architecture decision requires business context, halt and ask human.

---

### 2. Coder/Implementer Agent

**Responsibilities:**
- Read tasks.md from Architect
- Implement features in production code
- Write unit tests alongside code
- Create commits with clear messages
- Flag design issues back to Architect

**Boundaries:**
- ✅ Write access to src/*, tests/test_*
- ✅ Write access to new feature files
- ✅ Run test commands (pytest, ruff, black)
- ❌ **FORBIDDEN**: Modify tasks.md (read-only)
- ❌ **FORBIDDEN**: Delete or bypass tests
- ❌ **FORBIDDEN**: Force-push or rewrite history
- ❌ **FORBIDDEN**: Modify CLAUDE.md, AGENTS.md, or .claude/settings.json

**Escalation:** If code violates CLAUDE.md "NEVER DO THIS" rules, halt and ask human.

---

### 3. Reviewer/Tester Agent

**Responsibilities:**
- Review Coder's implementation against tasks.md
- Run full test suite (pytest, coverage, lint)
- Verify Coder's commits before merge
- Check test coverage thresholds
- Report code quality metrics

**Boundaries:**
- ✅ Read entire codebase
- ✅ Run all verification commands (pytest, ruff, black, coverage)
- ✅ Write to .test.* files, test reports
- ✅ Create merge/approval decisions based on tests
- ❌ **FORBIDDEN**: Modify production code
- ❌ **FORBIDDEN**: Merge PRs without explicit human approval
- ❌ **FORBIDDEN**: Skip pre-commit hooks

**Escalation:** If tests fail 3+ consecutive times, halt and report.

---

## Handover Protocol

### Happy Path: Architect → Coder → Reviewer

```
┌─────────────────┐
│ ARCHITECT       │
│ - Read design  │
│ - Draft plan   │
│ - Write tasks  │
└────────┬────────┘
         │
         ↓ tasks.md
┌─────────────────┐
│ CODER           │
│ - Implement     │
│ - Write tests   │
│ - Create PRs    │
└────────┬────────┘
         │
         ↓ Pull Request
┌─────────────────┐
│ REVIEWER        │
│ - Run tests     │
│ - Check lint    │
│ - Approve/block │
└─────────────────┘
```

### Handover Checklist

**Architect → Coder:**
- [ ] tasks.md complete and unambiguous
- [ ] Design doc linked
- [ ] Acceptance criteria clear
- [ ] Known blockers listed

**Coder → Reviewer:**
- [ ] All unit tests pass locally
- [ ] Code lints (ruff, black, mypy)
- [ ] No `NEVER DO THIS` violations
- [ ] Commit messages descriptive
- [ ] PR description links to issue

**Reviewer → Human:**
- [ ] Test suite passes (pytest, coverage)
- [ ] No lint errors
- [ ] Code review checklist signed off
- [ ] Ready for merge signal given

---

## Three-Strike Rule (Error Escalation)

If an agent hits the same error **3 consecutive times**, it must:

1. **Halt immediately** (stop attempting fixes)
2. **Dump state** to `.claude/errors.log`:
   ```
   === ERROR LOG ===
   Agent: [Coder|Reviewer|Architect]
   Attempt: 3/3
   Error: [exact error message]
   Context: [what was being attempted]
   Last successful step: [step before failure]
   Recommendation: [what human should check]
   ```
3. **Escalate to human** with link to error log
4. **Wait for explicit approval** before retrying

**Trigger Examples:**
- Compilation failure on same line 3 times → escalate
- Test failure on same assertion 3 times → escalate
- API call timeout 3 times → escalate
- Linting rule violation 3 times → escalate (likely false positive)

---

## State Locking (Sub-Agent Recovery)

When spawning a sub-agent (e.g., Architect spawning a Coder), parent must:

1. **Write current state** to `.claude/agent_state.json`:
   ```json
   {
     "parent_agent": "architect",
     "phase": "implementation",
     "last_checkpoint": "tasks.md completed",
     "current_task": "implement authentication module",
     "blockers": ["database schema not yet migrated"],
     "context_file": "docs/dev-note/feature-xxx.md"
   }
   ```

2. **Spawn child agent** with link to state file
3. **Child modifies state** as it progresses
4. **Parent resumes** by reading updated state if connection lost

---

## Permission Matrix

| Action | Architect | Coder | Reviewer |
|--------|-----------|-------|----------|
| Read code | ✅ | ✅ | ✅ |
| Write production code | ❌ | ✅ | ❌ |
| Write test code | ⚠ | ✅ | ✅ |
| Modify tasks.md | ✅ | ❌ | ❌ |
| Modify CLAUDE.md | ❌ | ❌ | ❌ |
| Run tests | ⚠ | ✅ | ✅ |
| Run linters | ⚠ | ✅ | ✅ |
| Merge PRs | ❌ | ❌ | ⚠ (human approval required) |
| Force-push | ❌ | ❌ | ❌ |
| Delete branches | ❌ | ❌ | ❌ |

**Legend:** ✅ Allowed | ⚠ Allowed with caution | ❌ Forbidden

---

## Tool Permissions

**Architect:**
- autoApprove: read, view, bash (grep/git log only)
- requireApproval: write, edit, execute (external commands)
- Blocked: push, merge, delete

**Coder:**
- autoApprove: read, write (production code), bash (compile/test), edit
- requireApproval: git push (interactive), git force-push (blocked)
- Blocked: merge, delete, git reset --hard

**Reviewer:**
- autoApprove: read, bash (test/lint)
- requireApproval: write (report only), git push
- Blocked: edit (production), merge, delete, git operations (except CI status check)

---

## Conflict Resolution

If roles overlap or conflict (e.g., Coder finds design issue):

1. **Document the issue** in comments or GitHub issue
2. **Stop work on conflict** (don't work around design)
3. **Escalate to Architect** for decision
4. **Resume only after resolution**

**Example:**
- Coder finds database schema doesn't support feature
- Coder flags issue to Architect
- Architect updates design doc + tasks.md
- Coder resumes implementation

---

## Single-Writer Guarantee

**SQLite Database Rule:**
- Only **one agent can write to database at a time**
- Implementation: Implement database locking or use task queue
- If conflict detected: Reviewer (slowest task) yields priority to Coder

---

## Status

- Created: 2026-07-10
- Last Updated: 2026-07-10
- Referenced in: .claude/settings.json (agent role mappings)
