# Audit: AI Agent Configuration Files (Chore #124)

**Date**: 2026-07-10
**Status**: Phase 1 Complete

---

## Summary

Current instruction set spans 2,976 lines across 10 files, with significant overlap and token bloat.

| File | Lines | Words | Est. Tokens | Status |
|------|-------|-------|-------------|--------|
| CLAUDE.md | 267 | 1,381 | 1,035 | ✓ Good (under budget) |
| .github/copilot-instructions.md | 513 | 2,811 | 2,108 | ⚠ Oversized |
| .github/instructions/issue-workflow.instructions.md | 877 | 2,954 | 2,215 | ⚠ Oversized |
| .claude/rules/assess.md | 86 | 309 | 231 | ✓ Good |
| .claude/rules/cli.md | 93 | 341 | 255 | ✓ Good |
| .claude/rules/crawl.md | 72 | 259 | 194 | ✓ Good |
| .claude/rules/preprocess.md | 60 | 256 | 192 | ✓ Good |
| .claude/rules/storage.md | 118 | 324 | 243 | ✓ Good |
| .claude/rules/tui.md | 824 | 2,637 | 1,977 | ⚠ Oversized (but architecture-critical) |
| .claude/rules/verify.md | 66 | 252 | 189 | ✓ Good |
| **TOTAL** | **2,976** | **11,524** | **8,643** | |

---

## Key Findings

### 1. Instruction Bloat
- **Root-level files** (CLAUDE.md + copilot-instructions.md + issue-workflow.instructions.md) = **1,657 lines, ~5,358 tokens**
- **Budget violation**: Should be <600 lines combined; currently 2.76× over budget
- **Impact**: LLM instruction-following degrades after 150–200 total system instructions

### 2. Redundancy
**Setup/Quick Start sections overlap:**
- CLAUDE.md Setup: `uv sync`, `spacy download`, `playwright install`, `.env`, `db init`
- copilot-instructions.md Quick Start: Same commands + extra examples
- **Overlap**: ~40% of Setup section repeated

**Phase-specific rules:**
- Phase context embedded in copilot-instructions.md (examples: "Crawl Phase", "Preprocess Phase", "Verification Phase")
- Phase-specific .claude/rules/ files exist but not referenced by copilot-instructions.md
- **Redundancy**: Phase logic documented twice (inline + linked files)

### 3. Missing Enforcement Layer
- `.claude/settings.json` exists but lacks:
  - Model tier pinning
  - claudeMdExcludes configuration
  - Agent role mappings
  - maxSteps (infinite loop prevention)
  - Tool-level permission boundaries (autoApprove/requireApproval)

### 4. Missing Progressive Disclosure
- Heavy architecture docs embedded in copilot-instructions.md
- No links to docs/ARCHITECTURE.md, docs/DESIGN.md, docs/COMPATIBILITY.md
- New developers must parse inline content instead of following links

### 5. No Multi-Agent Governance
- No AGENTS.md file defining agent roles, boundaries, handover protocol
- No escalation rules (Three-Strike Rule, state locking)
- No explicit permission matrix for agents

### 6. Inconsistent Path Scoping
- `.github/instructions/` directory has only issue-workflow.instructions.md
- Missing: cli-usage.instructions.md, code-patterns.instructions.md
- Missing: .claude/rules/multi-agent.md (phase-specific agent coordination)

---

## Redundant Content Map

| Content | Location 1 | Location 2 | Reduction Strategy |
|---------|-----------|-----------|-------------------|
| Setup commands | CLAUDE.md (30 lines) | copilot-instructions.md (~40 lines) | Keep in CLAUDE.md, link from copilot-instructions.md |
| Phase examples | copilot-instructions.md (~200 lines) | .claude/rules/* (existing) | Delete from copilot-instructions.md, reference .claude/rules/ |
| Tech stack list | CLAUDE.md (10 lines) | N/A | Keep in CLAUDE.md only |
| Verification commands | CLAUDE.md (20 lines) | copilot-instructions.md (~30 lines) | Keep in CLAUDE.md, link from copilot-instructions.md |
| Project structure | copilot-instructions.md (~80 lines) | DESIGN.md (linked) | Remove from copilot-instructions.md, link to DESIGN.md |

---

## Extraction Targets

### Phase 2 Actions

**1. Create AGENTS.md** (~250 lines)
- Define 3 roles: Architect/Planner, Coder/Implementer, Reviewer/Tester
- Handover protocol: Architect → tasks.md → Coder → tests → Reviewer
- Three-Strike Rule, state locking, permission matrix

**2. Enhance .claude/settings.json**
- Add `models`: map task types to Claude versions
- Add `claudeMdExcludes`: ["**/vendor/**", "**/node_modules/**"]
- Add `agents`: role mappings (architect, coder, reviewer)
- Add `maxSteps`: 10 (prevent infinite loops)
- Add `permissions`: autoApprove [read, view], requireApproval [write, execute, git]

**3. Trim .github/copilot-instructions.md** (<400 lines)
- Remove Setup section (link to CLAUDE.md § Setup)
- Remove Phase examples (link to .claude/rules/)
- Remove Project Structure (link to DESIGN.md)
- Remove embedded troubleshooting (link to docs/COMPATIBILITY.md)
- Keep: Quick Start (3 commands), Architecture Overview (high-level), Module Reference (quick lookup), Key Conventions

**4. Create .github/instructions/cli-usage.instructions.md** (~200 lines)
- CLI command reference, common flags, examples

**5. Create .github/instructions/code-patterns.instructions.md** (~150 lines)
- Pydantic schemas, Typer patterns, async patterns

**6. Create .claude/rules/multi-agent.md** (~100 lines)
- Phase-specific agent coordination (crawl, preprocess, assess, export)

---

## Success Criteria (Phase 1 ✓)

- [x] Line counts measured for all 10 files
- [x] Token estimates calculated
- [x] Redundancy identified (Setup, Phase examples, Project Structure)
- [x] Audit doc created
- [x] Extraction targets mapped
- [ ] Proceed to Phase 2: Extract & Organize

---

## Next Step

Phase 2: Extract & Organize (90 min)
- Create AGENTS.md, enhance settings.json, trim copilot-instructions.md, create topic-scoped files
