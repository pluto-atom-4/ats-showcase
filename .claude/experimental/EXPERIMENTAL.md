# Experimental Features

This directory tracks experimental branches and code that are not yet production-ready.

---

## NLP Module (Branch: feat/issue-XXX-requirement-filtering)

**Status:** EXPERIMENTAL – Not merged to main branch

**Description:**
NLP-based requirement extraction from job descriptions. Extracts structured data (skills, seniority levels, locations) using Named Entity Recognition (NER) and rule-based patterns.

**Scope:**
- 1,989 lines of Python code across 9 modules
- 6-phase progression pipeline:
  1. **Raw text** → Job description input
  2. **Normalization** → Standardize company names, location formats
  3. **NER extraction** → Extract entities (skills, roles, locations, domains)
  4. **Pattern matching** → Rule-based requirement identification
  5. **Confidence scoring** → Assign confidence metrics
  6. **Export** → Structured JSON output

**Performance (Prototypes Only):**
- High F1 scores in prototype experiments (0.75–0.92 across datasets)
- 540+ test cases in prototyping phase
- Multi-company evaluation completed
- Semantic matching with fuzzy distance algorithms

---

## Blockers: Production Readiness

Before merging to main, resolve:

### 1. Test Coverage (CRITICAL)
- ❌ **0% coverage in production test suite** (`tests/`)
- ✅ Extensive prototyping tests in `.claude/prototypes/` (not integrated to pytest)
- **Blocker:** Move all valid prototype tests to `tests/test_nlp_*.py`
- **Effort:** ~4–6 hours to integrate and refactor

### 2. Type Safety (BLOCKING)
- ❌ **11 mypy --strict errors** in `src/nlp/ner.py`
  - Missing type arguments for `tuple`, `dict`
  - Untyped function parameters
- **Blocker:** Resolve all type errors before merge
- **Effort:** ~2–3 hours

### 3. CLI Integration (MISSING)
- ❌ **No CLI commands** to invoke NLP extraction
- ❌ **No database schema** to store extracted requirements
- ❌ **No LLM assessment integration** (assess phase ignores extracted requirements)
- **Blocker:** Design CLI interface, update schema, integrate with assess phase
- **Effort:** ~8–10 hours

### 4. Production Validation (UNVERIFIED)
- ❌ **Prototypes only:** Tests run on small datasets, not production-scale jobs
- ❌ **No error handling:** Network failures, spaCy model issues not handled
- ❌ **No logging:** Production debug visibility missing
- **Blocker:** Run E2E tests on 100+ real jobs; verify accuracy drop vs prototypes
- **Effort:** ~4–6 hours

---

## Decision

### Keep Experimental
- Branch remains on remote for reference and future work
- Not imported into production code
- Not exposed via CLI or tests

### Next Steps (Future PRs)
1. **PR 1:** Integrate pytest tests from prototypes
2. **PR 2:** Resolve mypy type errors
3. **PR 3:** Add CLI commands (`extract-requirements`, `show-extraction-report`)
4. **PR 4:** Production validation & error handling
5. **PR 5:** Merge to main (after blockers cleared)

---

## Related Files

- **Branch:** `feat/issue-XXX-requirement-filtering`
- **Issue:** #162 (Requirement Filtering & Extraction)
- **Prototypes:** `.claude/prototypes/test_requirement_extraction_*.py`
- **Code:** `src/nlp/`
- **NLP Module Docstring:** `src/nlp/__init__.py` (marked experimental)

---

## Archive Note

This documentation serves as a decision log. When unblocking requirements are met, move this file to `.claude/archive/EXPERIMENTAL_RESOLVED.md` and merge the branch.

**Last Updated:** 2026-08-01
**Status:** Waiting for production readiness work
