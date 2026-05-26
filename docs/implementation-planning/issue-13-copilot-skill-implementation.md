# Issue #13: Add GitHub Copilot Skills - Implementation Plan

**Issue**: https://github.com/pluto-atom-4/ats-playground/issues/13
**Status**: 🚀 **IN PROGRESS** (Phase A Complete, Phase B Ready)
**Date Created**: 2026-05-23
**Completion Target**: 2026-05-23 (40 minutes)
**Author**: Implementation Planning
**Related PRs**: None yet (to be created)

---

## Executive Summary

This document provides a detailed implementation roadmap for Issue #13: "Add GitHub Copilot Skills." The goal is to make ATS Playground skills available in GitHub Copilot CLI sessions through a dedicated plugin repository.

**Key Achievement**: This issue depends on Issue #12 (Claude Code Settings), which has been successfully resolved (PR #16 merged).

**Scope**: Create a public GitHub plugin repository (`copilot-plugin-ats-playground`) with skill definitions and comprehensive documentation.

**Timeline**: 40 minutes across 4 implementation tasks.

---

## Phase A: Diagnostic & Architecture Review ✅ COMPLETE

### Current State Analysis

| System | Skill Access | Configuration | Status |
|--------|--------------|----------------|--------|
| **Claude Code** | ✅ YES | `.claude/settings.json` | ✅ Working (Issue #12) |
| **GitHub Copilot CLI** | ❌ NO | Plugin system (separate) | ⏳ This issue |

### Root Cause Identified

GitHub Copilot CLI and Claude Code use **completely separate** skill registration systems:

1. **Claude Code** (claude.ai/code)
   - Skills defined in `.claude/settings.json`
   - Auto-load when file is present
   - No manual installation needed
   - Status: ✅ COMPLETE (Issue #12)

2. **GitHub Copilot CLI** (gh copilot)
   - Skills delivered via **plugin system**
   - Requires: `gh copilot -- plugin install <repo>`
   - Manual installation per developer
   - Status: ⏳ This issue

### Key Insight

> `.claude/settings.json` skills **do not** auto-magically appear in GitHub Copilot CLI. The plugin system is entirely separate and requires explicit installation.

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Developer Workspace (ats-playground)                       │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────────┐  ┌────────────────────────────┐   │
│  │  Claude Code         │  │  GitHub Copilot CLI (gh)   │   │
│  │  (claude.ai/code)    │  │                             │   │
│  ├──────────────────────┤  ├────────────────────────────┤   │
│  │ .claude/settings.json│  │ Requires: Plugin System    │   │
│  │ skillOverrides: [    │  │                             │   │
│  │  ats-playground      │  │ copilot plugin install     │   │
│  │ ]                    │  │ copilot plugin list        │   │
│  ├──────────────────────┤  ├────────────────────────────┤   │
│  │ ✅ Skills available  │  │ ❌ No plugins (yet)        │   │
│  │   automatically      │  │    Needs plugin install    │   │
│  │ for Code sessions    │  │    for CLI sessions        │   │
│  └──────────────────────┘  └────────────────────────────┘   │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## Phase B: Implementation Plan ⏳ READY TO START

### Overview

Four sequential tasks totaling **40 minutes**:

| Task | Duration | Status | Dependencies |
|------|----------|--------|--------------|
| B.1: Update CLAUDE.md | 5 min | ⏳ Pending | Phase A ✅ |
| B.2: Create plugin repository | 20 min | ⏳ Pending | B.1 |
| B.3: Test plugin installation | 5 min | ⏳ Pending | B.2 |
| B.4: Update CONTRIBUTING.md | 5 min | ⏳ Pending | B.3 |
| **Total** | **40 min** | ⏳ **Pending** | **All phases** |

---

## Task B.1: Update CLAUDE.md (5 min)

### Objective
Document the GitHub Copilot CLI plugin model in CLAUDE.md to explain the two-system architecture.

### File Details
- **File**: `CLAUDE.md`
- **Location**: Repository root
- **Current Lines**: ~560 (approximate)
- **New Lines to Add**: ~50 lines
- **Target Section**: After "Quick Commands" section

### Content to Add

Insert a new section titled "GitHub Copilot CLI Plugin Model" with:

```markdown
## GitHub Copilot CLI Plugin Model

Unlike Claude Code (which uses `.claude/settings.json`), GitHub Copilot CLI
requires skills to be installed as **plugins** via the CLI plugin system.

### Two-System Architecture

1. **Claude Code Skills** (claude.ai/code)
   - Defined in: `.claude/settings.json`
   - Registration: `skillOverrides` array
   - Installation: Automatic (file-based)
   - When available: During Code sessions

2. **GitHub Copilot CLI Skills** (gh copilot)
   - Delivered via: GitHub plugin repositories
   - Installation: Manual (`gh copilot -- plugin install`)
   - Prerequisites: GitHub Copilot CLI installed + authenticated
   - When available: During CLI sessions

### Installing ATS Playground Plugin

To enable ATS Playground skills in GitHub Copilot CLI sessions:

```bash
# Install the plugin
gh copilot -- plugin install pluto-atom-4/copilot-plugin-ats-playground

# Verify installation
gh copilot -- plugin list

# Start a session
gh copilot

# In the session, use skills:
> /ats-preprocessing --help
> /ats-assessment --cv data/cv.json
> /ats-nlp-setup --model en_core_web_md
```

### Plugin Repository

The `copilot-plugin-ats-playground` repository contains:
- Plugin manifest (`plugin.json`)
- Skill definitions for:
  - `ats-nlp-setup`: Configure NLP models
  - `ats-preprocessing`: Preprocess job postings
  - `ats-assessment`: Assess job matches
- Usage examples and troubleshooting
- Full documentation

See: https://github.com/pluto-atom-4/copilot-plugin-ats-playground

### Important Note

This is separate from Claude Code configuration. Both systems can work together:
- **Claude Code**: Use skills defined in `.claude/settings.json`
- **GitHub Copilot CLI**: Use skills installed as plugins
```

### Success Criteria
- [ ] Section added to CLAUDE.md
- [ ] Two-system architecture clearly explained
- [ ] Installation commands documented
- [ ] Plugin repository linked
- [ ] Examples provided

### Verification Steps
```bash
# Verify CLAUDE.md is valid markdown
grep -n "GitHub Copilot CLI Plugin Model" CLAUDE.md

# Verify structure looks correct
head -20 CLAUDE.md | grep -i copilot
```

---

## Task B.2: Create Plugin Repository (20 min)

### Objective
Create a public GitHub repository (`copilot-plugin-ats-playground`) with plugin manifest, skill definitions, and documentation.

### Repository Details

**Repository Name**: `copilot-plugin-ats-playground`
**Location**: https://github.com/pluto-atom-4/copilot-plugin-ats-playground
**Visibility**: Public (for discoverability)
**Description**: "GitHub Copilot CLI plugin for ATS Playground skills (NLP setup, preprocessing, job assessment)"

### Repository Structure

```
copilot-plugin-ats-playground/
├── README.md (200+ lines)
│   ├── Installation prerequisites
│   ├── Step-by-step installation guide
│   ├── Quick start examples
│   ├── Skill usage documentation
│   ├── Configuration options
│   ├── Troubleshooting section
│   └── Support/links
│
├── plugin.json (30+ lines)
│   ├── Plugin metadata
│   ├── Skill definitions (3 skills)
│   ├── Version information
│   └── CLI compatibility settings
│
├── copilot.yml (40+ lines)
│   └── Alternative manifest format (for reference)
│
├── skills/
│   ├── ats-nlp-setup.md (80+ lines)
│   │   ├── Description
│   │   ├── Input/output format
│   │   ├── Configuration options
│   │   ├── Examples
│   │   └── Troubleshooting
│   │
│   ├── ats-preprocessing.md (80+ lines)
│   │   ├── Description
│   │   ├── Preprocessing workflow
│   │   ├── Token counting explanation
│   │   ├── Cost estimation
│   │   ├── Examples
│   │   └── Best practices
│   │
│   ├── ats-assessment.md (80+ lines)
│   │   ├── Description
│   │   ├── Assessment criteria
│   │   ├── Output format
│   │   ├── Examples
│   │   └── Cost tracking
│   │
│   └── resources/
│       ├── nlp-setup-template.md (NLP model selection guide)
│       ├── preprocessing-guide.md (Detailed chunking strategy)
│       └── assessment-examples.md (Real-world examples)
│
├── examples/
│   ├── interactive-mode.md (Using `gh copilot`)
│   ├── non-interactive-mode.md (Using `gh copilot -p`)
│   └── workflow-examples.md (End-to-end workflows)
│
├── LICENSE (MIT)
├── .gitignore (Standard Python patterns)
└── .github/
    └── README.md (Contributing guide)
```

### Files to Create

#### 1. plugin.json (CLI Manifest)

**Purpose**: Tells GitHub Copilot CLI what this plugin provides

**Content**:
```json
{
  "name": "ats-playground",
  "version": "1.0.0",
  "description": "ATS Playground skills for job assessment automation with local preprocessing",
  "author": "pluto-atom-4",
  "homepage": "https://github.com/pluto-atom-4/copilot-plugin-ats-playground",
  "repository": {
    "type": "git",
    "url": "https://github.com/pluto-atom-4/copilot-plugin-ats-playground"
  },
  "license": "MIT",
  "skills": [
    {
      "name": "ats-nlp-setup",
      "description": "Configure NLP models and spaCy environment for preprocessing",
      "usage": "/ats-nlp-setup [--model MODEL] [--validate]",
      "tags": ["nlp", "setup", "configuration"],
      "category": "setup"
    },
    {
      "name": "ats-preprocessing",
      "description": "Preprocess job postings with MarkItDown, spaCy, and token counting",
      "usage": "/ats-preprocessing [--source SOURCE] [--show-estimates] [--interactive]",
      "tags": ["preprocessing", "tokenization", "cost-estimation"],
      "category": "processing"
    },
    {
      "name": "ats-assessment",
      "description": "Assess job matches using Claude with local preprocessing (80-90% cost savings)",
      "usage": "/ats-assessment [--cv CV_FILE] [--jobs JOB_LIST] [--min-score MIN_SCORE]",
      "tags": ["assessment", "scoring", "job-matching"],
      "category": "analysis"
    }
  ],
  "requiredVersion": ">=1.0.0",
  "permissions": ["read:user", "repo"],
  "keywords": ["ats", "job-assessment", "nlp", "preprocessing", "cost-optimization"]
}
```

#### 2. README.md (Documentation)

**Purpose**: Installation guide and usage documentation

**Sections**:
1. Introduction (what this plugin does)
2. Prerequisites (GitHub Copilot CLI, authentication, Python 3.11+)
3. Installation (step-by-step)
4. Quick Start (basic examples)
5. Skill Usage (detailed for each skill)
6. Configuration (options and examples)
7. Troubleshooting (common issues)
8. Support (links and resources)

#### 3. skills/ats-nlp-setup.md

**Purpose**: Define the NLP setup skill

**Content Structure**:
```markdown
# Skill: ats-nlp-setup

## Description
Guides NLP model setup and validation for ATS Playground

## Usage
\`\`\`bash
/ats-nlp-setup [--model MODEL] [--validate] [--list-models]
\`\`\`

## Parameters
- `--model`: Model name (default: en_core_web_md)
- `--validate`: Verify model is installed and working
- `--list-models`: Show available models

## Examples
\`\`\`
/ats-nlp-setup --list-models
/ats-nlp-setup --model en_core_web_lg
/ats-nlp-setup --validate
\`\`\`

## Output
- Model status
- Version information
- Validation results
- Recommended next steps

## Configuration
- Model selection (tiny, small, medium, large)
- Custom model paths
- Performance vs accuracy trade-offs

## Troubleshooting
- Model not found
- Memory issues with large models
- Version compatibility
```

#### 4. skills/ats-preprocessing.md

**Purpose**: Define the preprocessing skill

**Key Features**:
- Local HTML to text conversion (MarkItDown)
- Semantic chunking (spaCy)
- Token counting (tiktoken)
- Cost estimation before LLM calls

#### 5. skills/ats-assessment.md

**Purpose**: Define the assessment skill

**Key Features**:
- CV-job matching scores
- Category breakdowns (tech, seniority, location)
- Cost tracking (actual vs estimated)
- 80-90% cost savings through preprocessing

### Implementation Steps

**Step 1**: Create repository on GitHub
```bash
# Via GitHub CLI
gh repo create copilot-plugin-ats-playground \
  --public \
  --description "GitHub Copilot CLI plugin for ATS Playground skills"
```

**Step 2**: Initialize repository locally
```bash
git clone https://github.com/pluto-atom-4/copilot-plugin-ats-playground
cd copilot-plugin-ats-playground

# Create initial files
echo "# ATS Playground Plugin" > README.md
echo "{}" > plugin.json
mkdir -p skills examples resources
touch LICENSE .gitignore
```

**Step 3**: Create plugin.json manifest
```bash
# Copy plugin.json content (from above) to plugin.json file
cat > plugin.json << 'EOF'
{...plugin.json content...}
EOF
```

**Step 4**: Create skill definition files
```bash
# Create each skill definition in skills/ directory
touch skills/ats-nlp-setup.md
touch skills/ats-preprocessing.md
touch skills/ats-assessment.md
```

**Step 5**: Create comprehensive README.md
```bash
# Write full documentation (200+ lines)
# Include installation, usage examples, troubleshooting
```

**Step 6**: Create example files
```bash
touch examples/interactive-mode.md
touch examples/non-interactive-mode.md
touch examples/workflow-examples.md
```

**Step 7**: Add MIT LICENSE
```bash
cat > LICENSE << 'EOF'
MIT License

Copyright (c) 2026 pluto-atom-4

Permission is hereby granted...
EOF
```

**Step 8**: Commit and push
```bash
git add .
git commit -m "feat: Initial ATS Playground plugin setup

- Add plugin.json manifest for GitHub Copilot CLI
- Add 3 skill definitions (NLP, preprocessing, assessment)
- Add comprehensive README and usage examples
- Add MIT LICENSE
- Add .gitignore for standard patterns"

git push origin main
```

### Success Criteria
- [ ] Repository created and accessible
- [ ] plugin.json manifest valid
- [ ] 3 skill definitions documented
- [ ] README.md comprehensive (200+ lines)
- [ ] Examples provided
- [ ] LICENSE added
- [ ] Repository appears public on GitHub

### Verification Steps
```bash
# Verify repository exists
gh repo view pluto-atom-4/copilot-plugin-ats-playground

# Verify files present
gh repo view pluto-atom-4/copilot-plugin-ats-playground \
  --json files -q '.files[].path'

# Verify README has sufficient content
wc -l README.md  # Should be 200+
```

---

## Task B.3: Test Plugin Installation (5 min)

### Objective
Verify that the plugin can be installed and used in GitHub Copilot CLI.

### Prerequisites
- GitHub Copilot CLI installed (`gh copilot --version`)
- Authenticated to GitHub (`gh auth status`)
- Plugin repository created and public

### Test Commands

**Test 1**: Install plugin
```bash
gh copilot -- plugin install pluto-atom-4/copilot-plugin-ats-playground
```

**Expected Output**: Plugin installed successfully

**Test 2**: List installed plugins
```bash
gh copilot -- plugin list
```

**Expected Output**: Should show `ats-playground` plugin listed

**Test 3**: Start interactive session
```bash
gh copilot
```

**Expected Behavior**: CLI starts, skills available

**Test 4**: Test skill invocation (in interactive session)
```
> /ats-nlp-setup --help
> /ats-preprocessing --help
> /ats-assessment --help
```

**Expected Output**: Help text for each skill

**Test 5**: Test skill with example
```bash
gh copilot -p "Using /ats-preprocessing skill, help me understand job preprocessing" \
  --allow-all-tools
```

**Expected Output**: Skill executes and provides response

### Success Criteria
- [ ] Plugin installs without errors
- [ ] `gh copilot -- plugin list` shows plugin
- [ ] CLI starts and recognizes skills
- [ ] `/ats-*` commands are available
- [ ] Skills execute when invoked

### Possible Issues & Troubleshooting

**Issue**: "Plugin not found" error
- **Cause**: Repository is private or doesn't exist
- **Solution**: Verify repository is public and accessible

**Issue**: "Invalid plugin format" error
- **Cause**: plugin.json malformed
- **Solution**: Validate JSON syntax, check GitHub docs

**Issue**: "CLI version incompatible" error
- **Cause**: GitHub Copilot CLI version mismatch
- **Solution**: Update CLI (`gh extension upgrade copilot`)

**Issue**: Skills not showing up
- **Cause**: Plugin installed but skills not registered
- **Solution**: Restart CLI session, check plugin.json

### Documentation

Document all test results in commit message:
```bash
git commit -m "test: Plugin installation and skill verification

- Tested: gh copilot -- plugin install pluto-atom-4/copilot-plugin-ats-playground
- Status: ✅ Installation successful
- Verified: gh copilot -- plugin list shows plugin
- Skills: All 3 skills available (/ats-nlp-setup, /ats-preprocessing, /ats-assessment)
- Testing: Interactive and non-interactive modes work
- Result: Ready for CONTRIBUTING.md documentation"
```

---

## Task B.4: Update CONTRIBUTING.md (5 min)

### Objective
Add GitHub Copilot CLI setup instructions for new contributors.

### File Details
- **File**: `CONTRIBUTING.md`
- **Current Location**: Repository root
- **New Section**: "GitHub Copilot CLI Setup"
- **Target Position**: After "Development Environment" section
- **Lines to Add**: ~50 lines

### Content to Add

Insert a new section titled "GitHub Copilot CLI Setup" with:

```markdown
## GitHub Copilot CLI Setup

### Prerequisites

Before setting up GitHub Copilot CLI for ATS Playground development:

1. **GitHub Copilot Subscription**
   - Active GitHub Copilot subscription (CLI feature)
   - See: https://github.com/copilot/cli

2. **GitHub Copilot CLI Installed**
   ```bash
   gh extension install github/gh-copilot
   ```

3. **Authenticated to GitHub**
   ```bash
   gh auth status
   ```

4. **GitHub CLI Updated** (version 2.55+)
   ```bash
   gh version
   ```

### Installation

Install the ATS Playground plugin for GitHub Copilot CLI:

```bash
# Install plugin
gh copilot -- plugin install pluto-atom-4/copilot-plugin-ats-playground

# Verify installation
gh copilot -- plugin list
```

### Usage

Start an interactive session:

```bash
gh copilot
```

In the session, use ATS Playground skills:

```
# Get skill help
> /ats-nlp-setup --help
> /ats-preprocessing --help
> /ats-assessment --help

# Use skills
> /ats-nlp-setup --list-models
> /ats-preprocessing --source careers.example.com
> /ats-assessment --cv data/cv.json --min-score 75
```

### Non-Interactive Mode

Use skills without starting interactive session:

```bash
# Describe what you want to do with a skill
gh copilot -p "Using /ats-preprocessing skill, analyze these 5 job postings and estimate token counts" \
  --allow-all-tools
```

### Troubleshooting

**Q: Plugin not found after installation**
- A: Ensure repository is public and verify with `gh copilot -- plugin list`

**Q: Skills don't show up in session**
- A: Restart the CLI session or reload plugin with `gh copilot -- plugin reload`

**Q: Getting "authentication failed" error**
- A: Run `gh auth login` and ensure you have CLI access to the plugin repository

**Q: Want to uninstall the plugin?**
- A: Run `gh copilot -- plugin remove pluto-atom-4/copilot-plugin-ats-playground`

### Two Systems: Claude Code vs GitHub Copilot CLI

**Important**: ATS Playground skills are available in TWO different systems:

1. **Claude Code** (claude.ai/code)
   - Skills configured in `.claude/settings.json`
   - No installation needed
   - Auto-available in Code sessions

2. **GitHub Copilot CLI** (gh copilot)
   - Skills installed as plugins
   - Manual installation needed
   - Available in CLI sessions

See [CLAUDE.md](./CLAUDE.md#github-copilot-cli-plugin-model) for architecture details.

### Support & Documentation

- **Plugin Repository**: https://github.com/pluto-atom-4/copilot-plugin-ats-playground
- **GitHub Copilot CLI Docs**: https://docs.github.com/copilot/how-tos/copilot-cli
- **Plugin System**: https://docs.github.com/copilot/concepts/agents/copilot-cli/about-cli-plugins
```

### Success Criteria
- [ ] Section added to CONTRIBUTING.md
- [ ] Installation steps documented
- [ ] Usage examples provided
- [ ] Troubleshooting section included
- [ ] Links to plugin repository
- [ ] Two-system explanation referenced

### Verification Steps
```bash
# Verify section exists
grep -n "GitHub Copilot CLI Setup" CONTRIBUTING.md

# Verify content structure
grep -E "^##|^###" CONTRIBUTING.md | tail -20
```

---

## Summary of Changes

### New Files Created
1. **copilot-plugin-ats-playground** (new public GitHub repository)
   - plugin.json (30+ lines)
   - README.md (200+ lines)
   - copilot.yml (40+ lines)
   - skills/ (3 skill definition files)
   - examples/ (3 example files)
   - LICENSE (MIT)

### Modified Files
1. **CLAUDE.md** (+50 lines)
   - New section: "GitHub Copilot CLI Plugin Model"
   - Architecture explanation
   - Installation commands
   - Plugin repository link

2. **CONTRIBUTING.md** (+50 lines)
   - New section: "GitHub Copilot CLI Setup"
   - Prerequisites and installation
   - Usage examples
   - Troubleshooting
   - Two-system explanation

### Total Effort
| Task | Duration | Total |
|------|----------|-------|
| B.1: CLAUDE.md | 5 min | 5 min |
| B.2: Plugin repo | 20 min | 25 min |
| B.3: Testing | 5 min | 30 min |
| B.4: CONTRIBUTING.md | 5 min | 35 min |
| **Overhead** | 5 min | **40 min** |

---

## Success Criteria & Verification

### Phase B Success Criteria

| Criterion | Target | Status |
|-----------|--------|--------|
| CLAUDE.md updated with CLI architecture | ✅ Required | ⏳ Pending |
| Plugin repository created (public) | ✅ Required | ⏳ Pending |
| plugin.json manifest valid | ✅ Required | ⏳ Pending |
| 3 skills documented (NLP, preprocessing, assessment) | ✅ Required | ⏳ Pending |
| README.md comprehensive (200+ lines) | ✅ Required | ⏳ Pending |
| Examples provided (interactive + non-interactive) | ✅ Required | ⏳ Pending |
| Plugin installs successfully | ✅ Required | ⏳ Pending |
| Skills callable from `gh copilot` CLI | ✅ Required | ⏳ Pending |
| CONTRIBUTING.md includes CLI setup | ✅ Required | ⏳ Pending |
| Feature branch created | ✅ Required | ⏳ Pending |
| PR created for main repository | ✅ Required | ⏳ Pending |

---

## Post-Implementation Steps

### Step 1: Create Feature Branch
```bash
git checkout -b feat/issue-13-copilot-skill
```

### Step 2: Commit Changes
```bash
git add CLAUDE.md CONTRIBUTING.md
git commit -m "feat(#13): Add GitHub Copilot CLI plugin model documentation

- Add 'GitHub Copilot CLI Plugin Model' section to CLAUDE.md
- Explain two-system architecture (Claude Code vs CLI)
- Document plugin installation commands
- Add 'GitHub Copilot CLI Setup' section to CONTRIBUTING.md
- Include prerequisites, installation, and usage examples
- Add troubleshooting guide
- Link to plugin repository

Plugin repository: https://github.com/pluto-atom-4/copilot-plugin-ats-playground"
```

### Step 3: Push Changes
```bash
git push origin feat/issue-13-copilot-skill
```

### Step 4: Create Pull Request
```bash
gh pr create \
  --title "feat(#13): Add GitHub Copilot CLI plugin documentation" \
  --body "## Changes

- Adds GitHub Copilot CLI plugin model documentation
- Explains two-system architecture
- Includes CLI setup instructions for developers
- References plugin repository

Closes #13

See docs/implementation-planning/issue-13-copilot-skill-implementation.md for details."
```

### Step 5: Verify & Merge
- Wait for GitHub Actions CI/CD to pass
- Request review if needed
- Merge PR to main
- Close Issue #13

---

## Rollback Plan

If plugin integration has issues:

1. **Keep Claude Code skills active** — `.claude/settings.json` skills still work
2. **Remove plugin repository link** — Delete reference from documentation
3. **Revert CLAUDE.md & CONTRIBUTING.md** — Use git reset
4. **Alternative approach** — Document manual skill invocation via prompts

---

## References

- **Issue #13**: https://github.com/pluto-atom-4/ats-playground/issues/13
- **Issue #12**: Claude Code Settings (Prerequisite, MERGED PR #16)
- **GitHub Copilot CLI**: https://docs.github.com/copilot/how-tos/copilot-cli
- **Plugin System**: https://docs.github.com/copilot/concepts/agents/copilot-cli/about-cli-plugins
- **ng-graphql-playground Issue #16**: Implementation inspiration source

---

## Notes

- **Phase A** (Diagnostic): ✅ COMPLETE
  - Architecture understood
  - Decision made (Option A: Custom Plugin)
  - Dependency (Issue #12): ✅ RESOLVED

- **Phase B** (Implementation): ⏳ READY TO START
  - All tasks planned and documented
  - Time estimates: 40 minutes total
  - Ready to execute when user commands

- **Plugin Repository**: Will be public for discoverability and contributions

- **Documentation Quality**: Comprehensive, with examples and troubleshooting

---

## Implementation Checklist

### Pre-Implementation
- [ ] Read and understand this plan
- [ ] Ensure Issue #12 (PR #16) is merged
- [ ] Create feat/issue-13-copilot-skill branch

### Task B.1
- [ ] Add "GitHub Copilot CLI Plugin Model" to CLAUDE.md
- [ ] Document two-system architecture
- [ ] Include installation examples
- [ ] Link to plugin repository

### Task B.2
- [ ] Create copilot-plugin-ats-playground repository
- [ ] Create plugin.json manifest (3 skills)
- [ ] Create README.md (200+ lines)
- [ ] Create 3 skill definition files
- [ ] Create example files
- [ ] Add MIT LICENSE
- [ ] Push to GitHub

### Task B.3
- [ ] Test plugin installation
- [ ] Verify `gh copilot -- plugin list` works
- [ ] Test skill invocation
- [ ] Document findings

### Task B.4
- [ ] Add "GitHub Copilot CLI Setup" to CONTRIBUTING.md
- [ ] Document prerequisites
- [ ] Include usage examples
- [ ] Add troubleshooting section

### Post-Implementation
- [ ] Commit changes to feature branch
- [ ] Create PR for main repository
- [ ] Wait for GitHub Actions
- [ ] Merge PR
- [ ] Close Issue #13

---

**Status**: Ready for Phase B execution
**Last Updated**: 2026-05-23
**Duration Estimate**: 40 minutes
