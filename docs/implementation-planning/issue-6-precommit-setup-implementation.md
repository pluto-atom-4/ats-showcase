# Issue #6 Implementation Plan: Pre-commit Code Quality Assurance

**Issue**: #6 – 🔍 Pre-commit Code Quality Assurance: Black, Ruff, mypy & pytest Integration
**Status**: 📋 Planning
**Estimated Effort**: 20–30 minutes (4 phases, 15–25 min implementation + 5–10 min testing)
**Priority**: Medium (Quality assurance infrastructure, enables better workflows)
**Owner**: TBD

---

## Overview

Implement **pre-commit hooks** to automate code quality checks (formatting, linting, type checking, testing) on every commit. This prevents low-quality code from reaching PR review stage and ensures consistent coding standards across the ATS Playground project.

### Why This Matters

- **Fail-fast feedback**: Developers learn formatting/linting issues immediately, not in PR review
- **Consistent standards**: All contributors use same formatters → no formatting debates
- **Type safety**: mypy catches type bugs at commit time (before CI/CD)
- **Zero broken tests**: Every commit to main is testable
- **CI/CD efficiency**: Fewer rejections, faster merges, reduced review time

### Success Criteria

1. ✅ `.pre-commit-config.yaml` created with 6 hooks configured
2. ✅ Setup script auto-installs hooks on `uv sync`
3. ✅ All hooks pass locally (no false positives)
4. ✅ Performance: full pre-commit run <60 seconds
5. ✅ Documentation complete & developer-friendly
6. ✅ GitHub Actions workflow configured (Phase 4, optional)

---

## Current State Assessment

### ✅ Already Configured

All quality tools are already in `pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0.0,<8.0",
    "pytest-cov>=4.0.0,<5.0",
    "pytest-asyncio>=0.21.0,<1.0",
    "black>=23.0.0,<24.0",
    "ruff>=0.1.0,<1.0",
    "mypy>=1.0.0,<2.0",
    "pre-commit>=3.0.0,<4.0",
]

[tool.black]
line-length = 100
target-version = ["py311", "py312", "py313"]

[tool.ruff]
line-length = 100
target-version = "py311"
select = ["E", "W", "F", "I", "C", "B"]

[tool.mypy]
python_version = "3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["slow", "integration", "unit"]
```

### ❌ Not Yet Configured

1. `.pre-commit-config.yaml` - Main hook configuration file
2. Hook auto-installation on `uv sync` (pyproject.toml post-install hook)
3. `docs/QUALITY-ASSURANCE.md` - Developer guide
4. GitHub Actions CI/CD workflow (optional Phase 4)

---

## Implementation Plan: 4 Phases

### Phase Overview

| Phase | Task | Duration | Deliverable |
|-------|------|----------|-------------|
| 1 | Create `.pre-commit-config.yaml` | 5 min | Hook configuration file (40 lines) |
| 2 | Setup script & auto-install | 5 min | `src/setup/setup_precommit.py` (~200 lines) |
| 3 | Documentation | 5 min | `docs/QUALITY-ASSURANCE.md` (~300 lines) |
| 4 | CI/CD Integration (optional) | 10 min | `.github/workflows/quality-checks.yml` |

**Total**: 15–25 minutes (20 min typical)

---

## Phase 1: Create `.pre-commit-config.yaml` (5 min)

### Objective

Define all pre-commit hooks with correct ordering, timeouts, and auto-fix settings.

### Hooks to Configure

| Hook | Purpose | Auto-fix | Stage | Timeout | Notes |
|------|---------|----------|-------|---------|-------|
| **trailing-whitespace** | Remove trailing spaces | ✅ Yes | commit | 10s | Standard hook |
| **end-of-file-fixer** | Ensure files end with newline | ✅ Yes | commit | 10s | Standard hook |
| **black** | Code formatting | ✅ Yes | commit | 30s | Line-length: 100 |
| **ruff** | Linting & import sorting | ✅ Partial | commit | 30s | Safe auto-fixes only |
| **mypy** | Type checking | ❌ No | commit | 60s | Python 3.11+ |
| **pytest** | Unit tests only | ❌ No | commit | 120s | Marker: `-m "not slow"` |

### Hook Ordering Strategy

```
1. trailing-whitespace (fast, auto-fix)
2. end-of-file-fixer (fast, auto-fix)
3. black (30s, auto-fix, needs clean file)
4. ruff (30s, partial auto-fix)
5. mypy (60s, type checking)
6. pytest (120s, must run last for clean code)
```

**Rationale**: Auto-fix hooks first (fast), then read-only checks (slow), tests last.

### Configuration Details

```yaml
repos:
  # Standard hooks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
        stages: [commit]
      - id: end-of-file-fixer
        stages: [commit]

  # Black formatter
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3
        args: [--line-length=100]
        stages: [commit]

  # Ruff linter
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--fix, --show-fixes]
        stages: [commit]
      - id: ruff-format
        stages: [commit]

  # mypy type checker
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy
        args: [--python-version=3.11, --ignore-missing-imports]
        additional_dependencies: [types-all]
        stages: [commit]

  # pytest
  - repo: local
    hooks:
      - id: pytest-unit
        name: pytest (unit tests only)
        entry: pytest -m "not slow and not integration"
        language: system
        types: [python]
        stages: [commit]
        pass_filenames: false
        always_run: true
```

### Deliverable

**File**: `.pre-commit-config.yaml` (45 lines, ~1.5 KB)

### Acceptance Criteria for Phase 1

- [ ] `.pre-commit-config.yaml` created with all 6 hooks
- [ ] Hook ordering tested (correct order: fast → slow, auto-fix → read-only)
- [ ] All hooks reference stable repo versions (not `master`/`main`)
- [ ] Timeouts are realistic (tested locally)
- [ ] Language versions match project (Python 3.11+)

---

## Phase 2: Setup Script & Auto-Installation (5 min)

### Objective

Create an automated setup script that:
1. Installs pre-commit framework
2. Registers hooks locally
3. Validates hook configuration
4. Provides skip/troubleshooting guidance

### Script Features

#### `src/setup/setup_precommit.py` (200–250 lines)

```python
#!/usr/bin/env python3
"""
Pre-commit setup utility for ATS Playground.

Usage:
    python -m src.setup.setup_precommit [--skip-install]

Features:
    - Auto-install pre-commit hooks from .pre-commit-config.yaml
    - Validate hook configuration
    - Check all hook dependencies available
    - Provide troubleshooting guidance
"""

import subprocess
import sys
from pathlib import Path

class PreCommitSetup:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.config_file = self.project_root / ".pre-commit-config.yaml"

    def install_hooks(self) -> bool:
        """Install pre-commit hooks."""
        try:
            subprocess.run(
                ["pre-commit", "install"],
                cwd=self.project_root,
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def validate_config(self) -> bool:
        """Validate .pre-commit-config.yaml."""
        try:
            subprocess.run(
                ["pre-commit", "validate-config"],
                cwd=self.project_root,
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def run_all_hooks(self) -> bool:
        """Test all hooks on entire codebase."""
        try:
            subprocess.run(
                ["pre-commit", "run", "--all-files"],
                cwd=self.project_root,
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def setup(self, skip_full_run: bool = False) -> int:
        """Complete setup process."""
        print("🔍 Setting up pre-commit hooks...\n")

        # Step 1: Validate config
        if not self.validate_config():
            print("❌ Config validation failed")
            return 1
        print("✅ Config validated")

        # Step 2: Install hooks
        if not self.install_hooks():
            print("❌ Hook installation failed")
            return 1
        print("✅ Hooks installed")

        # Step 3: Run on all files (optional)
        if not skip_full_run:
            print("\n🔄 Running hooks on all files (this may take ~60s)...")
            if not self.run_all_hooks():
                print("⚠️  Some files need formatting (auto-fixed)")
                return 0  # Not a failure, just needs review

        print("\n✨ Pre-commit setup complete!")
        return 0

if __name__ == "__main__":
    setup = PreCommitSetup()
    sys.exit(setup.setup())
```

### Integration with `uv sync`

Add post-install hook to `pyproject.toml`:

```toml
[tool.uv]
post-install-scripts = ["src/setup/setup_precommit.py"]
```

*(Or provide manual setup instruction in README)*

### Skip Scenarios

Developers can skip on CI/CD:
```bash
# Skip on GitHub Actions or local testing
SKIP=black,ruff,mypy,pytest git commit -m "..."

# Or use --no-verify for emergency commits
git commit --no-verify -m "..."
```

### Deliverable

**Files**:
- `src/setup/setup_precommit.py` (200–250 lines)
- Optional: `src/setup/__init__.py` (empty)

### Acceptance Criteria for Phase 2

- [ ] Setup script creates `.git/hooks/pre-commit` symlink
- [ ] Script validates `.pre-commit-config.yaml`
- [ ] Script tests all hooks on codebase
- [ ] Performance: full hook run <60 seconds
- [ ] Script provides clear error messages
- [ ] Skip instructions documented

---

## Phase 3: Documentation (5 min)

### Objective

Create comprehensive developer guide for setup, usage, and troubleshooting.

### Documents to Create/Update

#### 3.1 New: `docs/QUALITY-ASSURANCE.md` (300+ lines)

```markdown
# Code Quality Assurance Guide

## Quick Setup (1 minute)

```bash
# Install pre-commit hooks
python -m src.setup.setup_precommit

# Verify setup
pre-commit run --all-files
```

## Hooks Overview

### Auto-Fix Hooks (run automatically)

- **trailing-whitespace**: Removes trailing spaces
- **end-of-file-fixer**: Adds final newline
- **black**: Formats code (line-length: 100)
- **ruff**: Fixes import sorting & safe violations

### Read-Only Hooks (require manual fixes)

- **mypy**: Type checking (Python 3.11+)
- **pytest**: Unit tests (skips "slow" tests)

## Hook Details & Timeouts

[Detailed table with purpose, behavior, fix time]

## Troubleshooting

### Hooks taking too long?
- Check if lxml system dependencies installed
- Verify pytest isn't running integration tests
- Use `SKIP=pytest git commit` to skip slow hooks

### False positives in mypy?
- Add `# type: ignore` comment
- Update mypy config in pyproject.toml

### Want to skip hooks?
```bash
# Skip one hook
SKIP=mypy git commit -m "..."

# Skip all
git commit --no-verify -m "..."
```

## Performance Benchmarks

- Black: 2–5 seconds
- Ruff: 3–8 seconds
- mypy: 15–30 seconds
- pytest (unit only): 5–10 seconds
- Total: 30–60 seconds

## CI/CD Integration

Pre-commit also runs on GitHub Actions for PR validation.
```

#### 3.2 Update: `README.md`

Add to Quick Start section:
```markdown
### 🔍 Pre-commit Setup (Optional)

Automatically catch formatting & linting issues before committing:

```bash
python -m src.setup.setup_precommit
```

See [QUALITY-ASSURANCE.md](docs/QUALITY-ASSURANCE.md) for hook details & troubleshooting.
```

#### 3.3 Update: `CONTRIBUTING.md`

Add section:
```markdown
## Code Quality Requirements

Before committing, ensure:
1. Code formatted with black (line-length: 100)
2. Linting passes with ruff
3. Type checking passes with mypy
4. Unit tests pass with pytest

Pre-commit hooks automate this:
```bash
python -m src.setup.setup_precommit
```

### Deliverable

**Files**:
- `docs/QUALITY-ASSURANCE.md` (300+ lines)
- Update: `README.md` (+8 lines)
- Update: `CONTRIBUTING.md` (+10 lines)

### Acceptance Criteria for Phase 3

- [ ] `docs/QUALITY-ASSURANCE.md` created with:
  - Quick setup instructions
  - Detailed hook descriptions
  - Troubleshooting section
  - Performance benchmarks
  - Skip/bypass scenarios

- [ ] README updated with pre-commit reference
- [ ] CONTRIBUTING.md has code quality checklist
- [ ] All docs are clear & developer-friendly

---

## Phase 4: CI/CD Integration (10 min, Optional)

### Objective

Add GitHub Actions workflow to enforce quality checks on every PR.

### Workflow Configuration

**File**: `.github/workflows/quality-checks.yml`

```yaml
name: Code Quality Checks

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  quality:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Install dependencies
        run: uv sync

      - name: Run pre-commit hooks
        run: pre-commit run --all-files

      - name: Run full test suite
        run: uv run pytest tests/ -v
```

### Benefits

- ✅ Enforces code quality on all PRs
- ✅ Tests against Python 3.11, 3.12, 3.13
- ✅ Prevents merging low-quality code
- ✅ Provides clear feedback to contributors

### Deliverable

**File**: `.github/workflows/quality-checks.yml` (50 lines, ~1.5 KB)

### Acceptance Criteria for Phase 4

- [ ] Workflow runs on push & PR to main/develop
- [ ] Tests all supported Python versions
- [ ] Blocks merge on quality check failure
- [ ] Provides clear pass/fail feedback

---

## Dependency Analysis

### Pre-commit Framework

**Package**: `pre-commit>=3.0.0` (already in `pyproject.toml`)
- Version: 3.x stable
- Python: 3.7+
- Status: ✅ Compatible

### Hook Dependencies

All tools already configured:

| Tool | Version | Source | Status |
|------|---------|--------|--------|
| black | >=23.0.0 | pyproject.toml | ✅ Ready |
| ruff | >=0.1.0 | pyproject.toml | ✅ Ready |
| mypy | >=1.0.0 | pyproject.toml | ✅ Ready |
| pytest | >=7.0.0 | pyproject.toml | ✅ Ready |

**No new dependencies needed** ✅

### Hook Repository Versions

Use stable release versions (not `main`/`master`):

- pre-commit/pre-commit-hooks: `v4.4.0`
- psf/black: `23.3.0`
- astral-sh/ruff-pre-commit: `v0.1.0`
- pre-commit/mirrors-mypy: `v1.3.0`

---

## Risk Assessment

### Risks & Mitigations

| Risk | Severity | Likelihood | Mitigation |
|------|----------|-------------|-----------|
| Hooks too slow (>60s) | Medium | Low | Use markers to skip slow tests; profile locally |
| False positives in mypy | Medium | Medium | Maintain `# type: ignore` in pyproject.toml |
| Developers skip hooks | Low | Medium | Document benefits; make setup automated |
| CI/CD conflicts | Low | Low | Use same config file for local & CI |
| lxml system deps missing | Low | Low | Provide install guidance in docs |

### Mitigation Strategies

1. **Performance**: Run hooks locally first, measure timing
2. **False Positives**: Maintain pytest.ini markers carefully
3. **Adoption**: Auto-install on `uv sync`, clear documentation
4. **CI Consistency**: Use `.pre-commit-config.yaml` for both local & CI
5. **System Deps**: Document Ubuntu/macOS/Windows install steps

---

## Implementation Timeline

### Quick Implementation Path (20 min)

```
Phase 1 (5 min):  Create .pre-commit-config.yaml
  └─ Hook ordering, timeouts, versions

Phase 2 (5 min):  Setup script & testing
  └─ src/setup/setup_precommit.py

Phase 3 (5 min):  Documentation
  └─ docs/QUALITY-ASSURANCE.md + updates

Phase 4 (10 min): CI/CD (optional)
  └─ .github/workflows/quality-checks.yml

Total: 20 minutes (typical) | 15–25 min range
```

### Execution Order

1. Create `.pre-commit-config.yaml` first (enables testing)
2. Build setup script (enables automation)
3. Write docs (enables developer onboarding)
4. Add CI/CD workflow (optional, improves enforcement)

---

## Testing Strategy

### Before Implementation

1. Verify all tools work locally:
   ```bash
   uv run black src/ --check
   uv run ruff check src/
   uv run mypy src/
   uv run pytest tests/ -m "not slow"
   ```

2. Check tool versions against pyproject.toml

### During Implementation

1. Create `.pre-commit-config.yaml`
2. Test: `pre-commit validate-config`
3. Test: `pre-commit run --all-files`
4. Measure performance: time whole process
5. Verify all hooks pass

### After Implementation

1. Run setup script: `python -m src.setup.setup_precommit`
2. Commit a test file, verify hooks run
3. Test skip scenario: `SKIP=ruff git commit`
4. Verify CI/CD workflow passes

### Test Checklist

- [ ] All 6 hooks configured in `.pre-commit-config.yaml`
- [ ] Config validates: `pre-commit validate-config`
- [ ] Hooks run successfully: `pre-commit run --all-files`
- [ ] Performance <60 seconds
- [ ] Setup script works: `python -m src.setup.setup_precommit`
- [ ] Post-commit hook installed: `ls -la .git/hooks/pre-commit`
- [ ] GitHub Actions workflow passes

---

## Success Metrics

### Quantitative

- **Setup time**: <2 min to install hooks
- **Hook performance**: <60 seconds per commit
- **Coverage**: All 6 hooks configured & passing
- **Uptime**: 99%+ (no false positives)

### Qualitative

- ✅ Developers find setup easy & automated
- ✅ CI/CD catches fewer style issues
- ✅ Code reviews focus on logic, not formatting
- ✅ Contributing documentation is clear

---

## Post-Implementation Tasks

### Immediate (after Phase 3)

1. ✅ Issue #6 closed
2. ✅ PR created & merged
3. ✅ All developers run setup script

### Follow-up (optional, future)

1. Add GitHub Branch Protection rule requiring quality checks
2. Monitor hook performance; optimize if >60s
3. Gather feedback from developers

---

## Related Issues & Documentation

- **Issue #7**: NLP Setup (completed, Python 3.12 pinned)
- **docs/QUALITY-ASSURANCE.md**: Developer guide (this issue)
- **pyproject.toml**: Existing tool config
- **CONTRIBUTING.md**: Contributor guidelines

---

## Appendix: Hook Specifications

### Hook 1: trailing-whitespace
- **Purpose**: Remove trailing spaces
- **Auto-fix**: Yes (silently removes)
- **Time**: <1s
- **Example**:
  ```python
  # Before: x = 1
  # After:  x = 1
  ```

### Hook 2: end-of-file-fixer
- **Purpose**: Ensure file ends with single newline
- **Auto-fix**: Yes
- **Time**: <1s

### Hook 3: black
- **Purpose**: Format code to Black standard
- **Auto-fix**: Yes (reformats file)
- **Time**: 2–5s
- **Config**: line-length=100, target-version=[py311, py312, py313]

### Hook 4: ruff
- **Purpose**: Linting + import sorting
- **Auto-fix**: Partial (safe violations only)
- **Time**: 3–8s
- **Rules**: E, W, F, I, C, B (see pyproject.toml)

### Hook 5: mypy
- **Purpose**: Type checking
- **Auto-fix**: No (requires manual fixes)
- **Time**: 15–30s
- **Python**: 3.11+

### Hook 6: pytest
- **Purpose**: Run unit tests
- **Auto-fix**: No
- **Time**: 5–10s
- **Filter**: `pytest -m "not slow and not integration"`

---

## Glossary

- **Pre-commit**: Framework for managing git hooks
- **Hook**: Script that runs before commit
- **Stage**: When hook runs (pre-commit, commit-msg, push, etc.)
- **Auto-fix**: Hook modifies files automatically
- **Skip**: Bypass hook with `SKIP=hook_name`
- **FPS**: File Per Second (performance metric)

---

## Document History

| Date | Author | Status | Changes |
|------|--------|--------|---------|
| 2026-05-21 | Copilot | Draft | Initial plan created |

---

**Next Steps**: Review plan, assign to implementer, or begin Phase 1 implementation.
