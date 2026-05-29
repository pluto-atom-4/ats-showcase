# Issue #19: POC Crawl Workflow - Implementation Tracking

**GitHub Issue**: [#19 - Test Crawl Workflow on Real Career Page](https://github.com/pluto-atom-4/ats-playground/issues/19)
**Target Company**: Carbon Robotics (Greenhouse Job Board)
**Project**: End-to-end ATS Playground POC validation
**Status**: Phase 2 In Progress

---

## Overview

This document tracks the implementation status of Issue #19 across all 5 phases. Each phase represents a major workflow step in the ATS Playground system:

```
CRAWL → PREPROCESS → VERIFY → ASSESS → STORE → EXPORT
```

---

## Phase Status Dashboard

| Phase | Name | Status | Completion | Tasks | Files |
|-------|------|--------|-----------|-------|-------|
| **1** | Configuration & Crawl Setup | ✅ COMPLETE | 100% | 4/4 | `issue-19-poc-crawl-automation.md` |
| **2** | Preprocessing & Cost Analysis | 📋 PLANNING | 0% | 0/5 | `issue-19-phase-2-preprocessing.md` |
| **3** | User Verification | ⏳ QUEUED | 0% | — | — |
| **4** | CV-Based Assessment | ⏳ QUEUED | 0% | — | — |
| **5** | Results Storage & Export | ⏳ QUEUED | 0% | — | — |

---

## Phase 1: Configuration & Crawl Setup ✅ COMPLETE

**Planning Doc**: `issue-19-poc-crawl-automation.md`
**Commits**:
- `d747ed7` - docs: Add POC implementation plan for Carbon Robotics crawl workflow
- `6546559` - feat(#19): Implement Playwright crawler with Carbon Robotics extraction

### Summary
Successfully implemented browser-based crawler using Playwright and CSS selector extraction. Validated on Carbon Robotics Greenhouse job board.

### Deliverables
- ✅ Playwright Crawler class with async browser automation
- ✅ CSS selector discovery and configuration
- ✅ CLI `crawl-companies` command
- ✅ Job extraction and JSON storage
- ✅ 26 jobs successfully extracted from Carbon Robotics
- ✅ All tests passing (16/16)
- ✅ Code quality: Black formatted, ruff lint passing

### Key Files
- `src/browser/crawler.py` - Crawler implementation
- `src/cli.py` - crawl-companies command
- `config/companies.json` - Carbon Robotics selectors
- `data/extracted_jobs/carbonrobotics_jobs.json` - Extracted jobs (26)

### Metrics
- **Jobs Extracted**: 26
- **Locations**: 9 unique
- **Processing Time**: ~30 seconds
- **Success Rate**: 100%

---

## Phase 2: Preprocessing & Cost Analysis 📋 PLANNING

**Planning Doc**: `issue-19-phase-2-preprocessing.md`
**Target Completion**: ~30–45 minutes

### Objective
Transform extracted job data into clean, semantic chunks with token counts and cost estimates. Validate 80–90% token reduction vs raw HTML.

### Tasks Breakdown

#### Task 2.1: HTML Cleaning ⏳ PENDING
- **Tool**: MarkItDown (primary), BeautifulSoup (fallback)
- **Module**: `src/parsers/html.py`
- **Function**: `clean_html(raw_html: str) -> str`
- **Deliverable**: Cleaned text without markup

#### Task 2.2: Semantic Chunking ⏳ PENDING
- **Tool**: spaCy NLP (`en_core_web_md`)
- **Module**: `src/tokenization/chunking.py`
- **Function**: `chunk_by_sentences(text: str, target_size: int) -> List[str]`
- **Approach**: Split at sentence boundaries, target ~400 tokens/chunk
- **Deliverable**: Meaningful semantic chunks

#### Task 2.3: Token Counting & Cost Estimation ⏳ PENDING
- **Tool**: tiktoken (Claude-compatible tokenizer)
- **Module**: `src/tokenization/counter.py`
- **Functions**: `count_tokens()`, `estimate_cost()`
- **Pricing**: Claude 3.5 Sonnet @ $0.003/1M input tokens
- **Deliverable**: Token counts and cost estimates per job

#### Task 2.4: CLI Preprocess Command ⏳ PENDING
- **Command**: `uv run python -m src.cli preprocess preprocess-jobs`
- **Options**: `--batch-size`, `--show-estimates`
- **Output**: Preprocessing metrics, token reduction %, cost breakdown
- **Deliverable**: Functional CLI command with error handling

#### Task 2.5: Validation & Testing ⏳ PENDING
- **Unit Tests**: `test_tokenization.py`, `test_preprocessor.py`
- **Integration Test**: Run on all 26 Carbon Robotics jobs
- **Success Criteria**:
  - All 26 jobs processed successfully
  - Token reduction 80–90% verified
  - Processing time <5 seconds
  - All tests passing
- **Deliverable**: Validation report + passing tests

### Success Criteria
- ✅ All 26 jobs preprocessed without errors
- ✅ Token reduction verified (80–90% target)
- ✅ Semantic chunks have meaningful boundaries
- ✅ CLI command working end-to-end
- ✅ Unit tests passing (100%)
- ✅ Code formatted + linting passes
- ✅ Documentation complete

### Cost Savings Projection
- **Raw HTML**: 6,000 tokens/job × $0.003/1M = $0.018/job
- **Preprocessed**: 700 tokens/job × $0.003/1M = $0.0021/job
- **Savings per job**: 87% reduction
- **Savings per 100 jobs**: $1.59 (88% cut)

### Known Limitations
1. **Empty Job Descriptions**: Phase 1 extracted only title + location
   - Impact: Preprocessing will work with available data
   - Mitigation: Fetch full descriptions in Phase 3 if needed

2. **Token Variation**: tiktoken estimates vs actual Claude tokens may differ
   - Impact: Estimates ~5–10% variance expected
   - Mitigation: Track actual tokens in Phase 4, compare metrics

3. **Performance Unknown**: Scaling from 26 to 100+ jobs untested
   - Impact: Unknown if <5sec target achievable at scale
   - Mitigation: Test and extrapolate during Task 2.5

---

## Phase 3: User Verification ⏳ QUEUED

**Planning**: To be created
**Target**: After Phase 2 complete

### Objective
Interactive user review of extracted/preprocessed jobs before expensive LLM calls. Confirm or reject each job.

### Planned Tasks
- Load preprocessed jobs from Phase 2
- Display job preview (title, location, estimated cost)
- Prompt user: Confirm / Reject / Edit
- Save user decisions to database
- Mark approved jobs as "confirmed"

### Expected Output
- Interactive CLI with 26 job reviews
- User decisions persisted
- Cost transparency displayed upfront

---

## Phase 4: CV-Based Assessment ⏳ QUEUED

**Planning**: To be created
**Target**: After Phase 3 complete

### Objective
Score each confirmed job against user's CV using Claude 3.5 Sonnet. Generate match scores and recommendations.

### Planned Tasks
- Load user CV
- Load confirmed jobs from Phase 3
- Send preprocessed chunks to Claude with custom prompt
- Parse response: overall_score, tech_score, seniority_score, location_score, recommendations
- Track actual tokens used vs estimates
- Store assessments in database

### Expected Output
- Assessment scores (0–100 scale)
- Category breakdowns (tech, seniority, location)
- Recommendations for gaps
- Actual token usage + cost per job

---

## Phase 5: Results Storage & Export ⏳ QUEUED

**Planning**: To be created
**Target**: After Phase 4 complete

### Objective
Persist all data (crawled, preprocessed, reviewed, assessed) to database and export as Markdown reports.

### Planned Tasks
- Create SQLite schema with FTS5 full-text search
- Store jobs, assessments, cost metrics
- Implement search functionality (keyword, score filter)
- Generate Markdown report with sorted results
- Export to file or display in CLI

### Expected Output
- SQLite database with indexed jobs
- Markdown report with sorted matches
- Cost breakdown and statistics

---

## Implementation Checklist

### Phase 1 ✅
- [x] HTML structure analysis (Greenhouse discovery)
- [x] CSS selector discovery (job_container, title, location, link)
- [x] Configuration entry (Carbon Robotics in config/companies.json)
- [x] Crawler implementation (Playwright browser automation)
- [x] CLI crawl command (crawl-companies)
- [x] Validation (26 jobs extracted successfully)
- [x] Tests passing (16/16)
- [x] Code quality (Black + ruff passing)
- [x] Commit to feature branch

### Phase 2 (CURRENT) 📋
- [ ] Task 2.1: HTML cleaning module (clean_html)
- [ ] Task 2.2: Semantic chunking module (chunk_by_sentences)
- [ ] Task 2.3: Token counter module (count_tokens, estimate_cost)
- [ ] Task 2.4: CLI preprocess command (preprocess-jobs)
- [ ] Task 2.5: Validation & tests
- [ ] Code quality checks
- [ ] Commit to feature branch

### Phase 3–5 ⏳
- [ ] (Planned after Phase 2 complete)

---

## Branch Strategy

**Current Branch**: `feat/issue-19-1`
**Status**: Phase 1 Complete + Phase 2 Planning

**Next Steps**:
1. ✅ Created Phase 2 planning doc (`issue-19-phase-2-preprocessing.md`)
2. ⏳ Create feature branch `feat/issue-19-phase-2-preprocess`
3. ⏳ Implement Phase 2 tasks (2.1–2.5)
4. ⏳ Commit with test results
5. ⏳ Push and create PR for Phase 2

---

## File Structure

```
docs/implementation-planning/
├── issue-19-poc-crawl-automation.md          ✅ Phase 1-5 overview
├── issue-19-phase-2-preprocessing.md         ✅ Phase 2 detailed plan
└── issue-19-implementation-tracking.md       ✅ THIS FILE (status tracker)

src/
├── browser/
│   └── crawler.py                            ✅ Implemented
├── parsers/
│   └── html.py                               ⏳ Phase 2 Task 2.1
├── tokenization/
│   ├── chunking.py                           ⏳ Phase 2 Task 2.2
│   └── counter.py                            ⏳ Phase 2 Task 2.3
└── cli.py                                    ✅ crawl-companies, ⏳ preprocess-jobs

data/
└── extracted_jobs/
    └── carbonrobotics_jobs.json              ✅ 26 jobs extracted

config/
└── companies.json                            ✅ Carbon Robotics config
```

---

## Key Metrics & Targets

| Metric | Phase 1 Actual | Phase 2 Target | Notes |
|--------|----------------|----------------|-------|
| **Jobs Extracted** | 26/26 | 26/26 | Success! |
| **Token Reduction** | N/A | 80–90% | vs raw HTML |
| **Cost Savings** | N/A | 87% | per job |
| **Processing Time** | 30s crawl | <5s preprocess | Per 26 jobs |
| **Tests Passing** | 16/16 | 18+/18+ | Adding 2+ new tests |
| **Code Coverage** | TBD | 80%+ | Target in Phase 2 |

---

## Contact & References

- **GitHub Issue**: https://github.com/pluto-atom-4/ats-playground/issues/19
- **Related Docs**:
  - `docs/PREPROCESS.md` - Deep dive on preprocessing
  - `docs/ARCHITECTURE.md` - System design
  - `docs/CLI.md` - Command reference
- **Slack/Discord**: #ats-playground (if applicable)

---

## Notes

- Phase 1 validation complete: Selectors work, crawler extracts jobs correctly
- Phase 2 ready to implement: All planning done, clear task breakdown
- Cost savings projection: 87% token reduction achievable via preprocessing
- Performance target: All phases should complete in <2 minutes for 26 jobs

**Last Updated**: 2026-05-27
**Updated By**: Copilot
**Status**: Ready for Phase 2 Implementation
