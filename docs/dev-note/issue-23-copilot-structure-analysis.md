# GitHub Copilot Custom Instructions: Official Structure Analysis

**Status:** ✅ Verified Against Official GitHub Documentation (May 2026)

---

## TL;DR - Your Repository

| File | Status | Notes |
|------|--------|-------|
| `.github/copilot-instructions.md` | ✅ OFFICIAL | Repository-wide instructions (correct location) |
| `.github/copilot-issue-workflow.md` | ✅ VALID | Documentation file (non-instruction, no conflict) |
| `.github/instructions/` | 📋 AVAILABLE | For future path-specific rules |

**Recommendation:** Current structure is valid. No changes required. Expand with path-specific instructions if needed in future.

---

## Official GitHub Copilot File Structure (2026)

### ✅ Officially Supported Patterns

**1. Repository-wide Custom Instructions:**
```
.github/copilot-instructions.md
```
- **Applies to:** All Copilot requests in repository
- **Format:** Natural language Markdown
- **Supported by:** Copilot Chat, Cloud Agent, Code Review
- **Priority:** 2nd (after personal, before organization)

**2. Path-specific Custom Instructions:**
```
.github/instructions/
├── backend.instructions.md           # ---applyTo: "backend/**"---
├── frontend.instructions.md          # ---applyTo: "frontend/**"---
└── tests/testing.instructions.md     # ---applyTo: "tests/**"---
```
- **Applies to:** Specific files/directories (glob patterns)
- **Requires:** `applyTo` YAML frontmatter
- **Supported by:** Cloud Agent, Code Review ONLY
- **File extension:** Must end with `.instructions.md`

**3. Agent-specific Instructions (Optional):**
```
AGENTS.md          # At root level (repo-wide precedence)
CLAUDE.md          # Alternative at root (for Claude agents)
GEMINI.md          # Alternative at root (for Gemini agents)
```
- **Location:** Root of repository (NOT in `.github/`)
- **Spec:** Follows [agentsmd/agents.md](https://github.com/agentsmd/agents.md)
- **Precedence:** Closest file in directory tree wins

---

## ❌ NOT in Official Documentation

The structure you referenced includes these **non-official patterns:**

```
.github/
├── AGENTS.md                    # ❌ Should be at root, not .github/
├── prompts/                     # ❌ Not an official instruction type
│   └── *.prompt.md              # ❌ Not a recognized file extension
└── agents/                      # ❌ No standardized directory structure
    └── *.agent.md               # ❌ Not a recognized pattern
```

**Why Not Official:**
- GitHub's specification defines 3 instruction types, none of them "prompts" or "agents" directories
- `.github/` is reserved for workflows, settings, and instruction files (`.md` only)
- Non-instruction Markdown in `.github/` is allowed but should be documented separately

---

## Current State of ATS Playground ✅

Your repository **already follows best practices:**

```
.github/
├── copilot-instructions.md          ✅ OFFICIAL - Repository-wide guidance
├── copilot-issue-workflow.md        ✅ VALID - Development documentation (non-instruction)
└── workflows/
    └── quality-checks.yml           ✅ GitHub Actions (separate system)
```

**Analysis:**
1. `.github/copilot-instructions.md` — Correct location, properly formatted
2. `.github/copilot-issue-workflow.md` — Valid documentation file (does not conflict with instruction system)
3. No non-official patterns present

---

## Recommended Future Enhancements

### If You Want to Add Path-Specific Rules:

**Create `.github/instructions/` structure:**

```
.github/
├── copilot-instructions.md
├── instructions/
│   ├── src-style.instructions.md        # All files in src/
│   ├── tests-style.instructions.md      # All files in tests/
│   └── cli/commands.instructions.md     # Specific to CLI
└── workflows/
```

**Example Path-Specific File:**

```markdown
---
applyTo: "src/**/*.py"
excludeAgent: "code-review"
---

# Source Code Guidelines

All Python files in src/ should:
- Use absolute imports: `from src.models.job import JobPosting`
- Include type hints on all functions
- Run pre-commit before commit: `pre-commit run --all-files`
```

### If You Want to Add Agent-Specific Guidance:

**Create `CLAUDE.md` at root:**

```markdown
# Claude Agent Instructions for ATS Playground

## Architecture
[Detailed architecture for Claude agents]

## Build Steps
[Step-by-step commands Claude should run]

## Known Issues
[Workarounds and pitfalls]
```

---

## Validation Result

| Aspect | Finding |
|--------|---------|
| Current `.github/copilot-instructions.md` | ✅ Fully compliant |
| Current `.github/copilot-issue-workflow.md` | ✅ Valid documentation |
| Path-specific instructions | 📋 Available but not yet used |
| Agent instructions (CLAUDE.md) | 📋 Available but not yet used |
| Non-official patterns | ✅ None detected |

---

## Key Insights

1. **Your current structure is valid and follows GitHub standards**
2. **Both files in `.github/` serve their purpose correctly:**
   - `copilot-instructions.md` = Copilot instruction rules
   - `copilot-issue-workflow.md` = Developer documentation
3. **No migration or refactoring needed**
4. **You have official paths available for future expansion:**
   - `.github/instructions/*.instructions.md` for path-specific rules
   - `CLAUDE.md` at root for agent guidance

---

## When to Use Additional Instruction Files

| Situation | Use | Location |
|-----------|-----|----------|
| Global Copilot rules (exists) | Repository-wide | `.github/copilot-instructions.md` ✅ |
| Rules for src/ only | Path-specific | `.github/instructions/src.instructions.md` |
| Rules for tests/ only | Path-specific | `.github/instructions/tests.instructions.md` |
| Claude agent guidance | Agent instructions | `CLAUDE.md` (root) |
| Development workflow (exists) | Documentation | `.github/copilot-issue-workflow.md` ✅ |

---

## Reference

**Official Source:** https://docs.github.com/en/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot

**Last Verified:** May 29, 2026

**Current Status:** ✅ All information verified against latest GitHub Copilot documentation
