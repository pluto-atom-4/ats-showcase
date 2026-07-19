# Agent Roles & Governance

Multi-agent coordination framework for ATS Playground. Defines role boundaries and escalation.

---

## Agent Roles

### Architect/Planner
- Draft implementation plans (tasks.md)
- Design module boundaries + APIs
- Write architectural decisions
- ✅ Read codebase, write tasks.md + docs/
- ❌ FORBIDDEN: Write production code

### Coder/Implementer
- Implement features, write tests
- Create commits
- Flag design issues to Architect
- ✅ Write src/, tests/, run tests
- ❌ FORBIDDEN: Modify tasks.md, CLAUDE.md, skip tests

### Reviewer/Tester
- Verify implementation vs tasks.md
- Run full test suite (pytest, coverage, lint)
- Check test coverage, code quality
- ✅ Read codebase, run verification commands
- ❌ FORBIDDEN: Modify production code, merge without human approval

---

## Handover Protocol

```
ARCHITECT (plan)
    ↓ tasks.md
CODER (implement + test)
    ↓ PR + commits
REVIEWER (verify)
    ↓ approval/feedback
HUMAN (merge decision)
```

**Checklist:**
- [ ] tasks.md complete and approved
- [ ] Coder implements, writes tests
- [ ] All tests passing (pytest, coverage, lint)
- [ ] Reviewer approves code quality
- [ ] Human merges PR

---

## Error Escalation (Three-Strike Rule)

If any phase fails 3+ times on same task:
1. Halt current phase
2. Escalate to human with context
3. Wait for direction before retry

**Examples:**
- Test failures 3× → Escalate (design issue?)
- API errors 3× → Escalate (rate limiting or config?)
- Lint failures 3× → Escalate (style violation?)

---

## Single-Writer Guarantee

- Only one agent modifies code per task (prevent conflicts)
- Architect writes tasks.md; Coder reads-only
- Coder writes src/; Reviewer reads-only
- Reviewer approves; Human merges

**SQLite Parallel:** Assessment processes use single-writer pattern (no concurrent writes to same DB).

---

## Permission Matrix

| Role | tasks.md | src/ | tests/ | docs/ | CLAUDE.md | .claude/ |
|------|----------|------|--------|-------|-----------|----------|
| Architect | W | R | R | W | R | R |
| Coder | R | W | W | R | R | R |
| Reviewer | R | R | R | W | R | R |
| Human | R | R | R | R | W | W |

**W** = write, **R** = read

---

## Related

- **Phase Coordination:** See `.claude/rules/multi-agent.md` for phase-specific handoffs
- **CLAUDE.md:** Project setup, commands, git workflow
- **DESIGN.md:** Architecture decisions

---

**Last Updated:** 2026-07-19
**Status:** Condensed for token budget compliance
