---
name: context-audit-checklist
description: Maintenance checklist for AI context files
metadata:
  type: audit
  cadence: quarterly
---

# Context Files Audit Checklist

Run this checklist quarterly to verify context files remain aligned with codebase and within token budgets.

## Phase 1: File Presence & Size

- [ ] CLAUDE.md exists and < 200 lines (~1.5K tokens)
- [ ] DESIGN.md exists and 200–400 lines (~3K tokens)
- [ ] AGENTS.md exists and ~150 lines (~1K tokens)
- [ ] .github/copilot-instructions.md exists and < 60 lines (~1K words)
- [ ] .claude/rules/ directory exists with all phase files:
  - [ ] crawl.md
  - [ ] preprocess.md
  - [ ] verify.md
  - [ ] assess.md
  - [ ] storage.md
  - [ ] cli.md
  - [ ] multi-agent.md
  - [ ] tui.md (if in scope)
- [ ] .claude/profiles.json exists (or planned)

## Phase 2: Content Validation

**CLAUDE.md:**
- [ ] Setup instructions match current tech stack (uv, playwright, spacy models)
- [ ] Git workflow section matches CONTRIBUTING.md or current practice
- [ ] Quick workflow commands are runnable (test 1–2 samples)
- [ ] Verification commands reference correct file paths
- [ ] Phase-specific rules link to actual .claude/rules/ files
- [ ] Tech stack versions match pyproject.toml (textual, pydantic, rich)

**DESIGN.md:**
- [ ] Architecture diagram/description matches actual code structure
- [ ] Anti-patterns section reflects current DO NOTs
- [ ] Database schema matches src/storage/db.py
- [ ] All referenced file paths exist (no dead links)

**AGENTS.md:**
- [ ] Agent roles clearly defined (Architect, Coder, Reviewer, Orchestrator)
- [ ] Responsibilities don't overlap
- [ ] Examples use current tech (Typer, Playwright, Claude API)
- [ ] No references to removed tools or phases

**.github/copilot-instructions.md:**
- [ ] GitHub Copilot-specific rules are present
- [ ] No duplication with CLAUDE.md
- [ ] Codebase patterns reflect current code style
- [ ] Example code snippets match actual patterns in src/

**Phase-Specific Rules (.claude/rules/):**
- [ ] Each file has clear "Verification Commands" section
- [ ] Examples in each file are copy-pasteable (no placeholders)
- [ ] Tech stack references (versions, libraries) match current versions
- [ ] No contradictions between files (e.g., conflicting async patterns)

## Phase 3: Staleness Detection

- [ ] Last updated dates are recent (< 3 months)
- [ ] Deprecated tools or libraries mentioned? (e.g., old pyproject.toml versions)
- [ ] Command examples use correct flags (e.g., `uv run` not `python -m`)
- [ ] API endpoint examples match current Claude API (not legacy)
- [ ] Database schema examples match current schema
- [ ] Removed phases or workflows still documented? (mark as archived if yes)

## Phase 4: Redundancy Check

- [ ] Setup instructions not repeated across CLAUDE.md, DESIGN.md, SETUP.md
- [ ] Git workflow not duplicated (CLAUDE.md vs CONTRIBUTING.md)
- [ ] Tech stack references consistent across all files
- [ ] Example code blocks not duplicated (link instead of copy)

## Phase 5: Link Validation

- [ ] All relative links to .md files are valid (no 404s)
- [ ] Links to code files (src/, tests/) reference existing paths
- [ ] Issue/PR references are valid GitHub URLs or issue numbers
- [ ] Links to external docs (Claude API, Playwright) still valid

## Phase 6: Metrics & Reporting

Run `scripts/context-audit.py` and verify:

- [ ] All files within token budgets
- [ ] Baseline metrics updated in `docs/dev-note/context-baseline.json`
- [ ] No warnings or errors in audit output
- [ ] Cost tracking tables (estimated vs actual) still accurate

## Phase 7: AI Compliance Log

- [ ] Check `docs/dev-note/ai-compliance-log.md` for recent violations
- [ ] Review if violations are due to stale guidance (update if yes)
- [ ] Identify patterns: do violations cluster around specific phases or features?
- [ ] Update guidance if patterns detected

## Remediation

If issues found:

1. **Oversized file** → Refactor into `.claude/rules/` sub-files
2. **Dead links** → Update links or remove outdated references
3. **Stale command** → Update to match current tool versions
4. **Deprecated tool** → Document as removed, add migration note
5. **Contradictions** → Resolve in favor of current code; document why

## Completion

- [ ] All checklist items reviewed
- [ ] Findings documented in `docs/dev-note/ai-config-audit-findings.md`
- [ ] Metrics updated in `docs/dev-note/context-baseline.json`
- [ ] PR created with all fixes (if any)
- [ ] Quarterly maintenance issue closed

---

**Last Audited:** [DATE]  
**Next Audit:** [DATE + 13 weeks]  
**Auditor:** [NAME]
