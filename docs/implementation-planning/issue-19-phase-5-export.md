# Issue #19 Phase 5: Results Export & Analytics 📊

**Issue:** [#19 - Agentic ATS Playground POC](https://github.com/pluto-atom-4/ats-playground/issues/19)

**Objective:** Implement complete results export pipeline with markdown reports, analytics, and search functionality. Enable users to review assessed jobs with cost/token tracking and actionable recommendations.

**Phase Dependencies:**
- ✅ Phase 1: Crawl job postings (complete)
- ✅ Phase 2: Preprocess HTML (complete)
- ✅ Phase 3: User verification (complete)
- ✅ Phase 4: LLM assessment (complete)
- 🔄 **Phase 5: Export & analytics** (this phase)

**Timeline Estimate:** 30-40 minutes planning, 40-50 minutes implementation

---

## Phase Overview

Phase 5 completes the POC by enabling users to export, search, and analyze assessed jobs. Users will:
1. Run `export-results` to generate markdown report
2. Search jobs by keyword/score range
3. View analytics: top matches, score distribution, cost summary
4. Share results as markdown documentation

**Key Design Principles:**
- **No new API calls** (all data from Phase 4 assessments already in DB)
- **Markdown-first** (human-readable, shareable, version-control friendly)
- **Rich analytics** (cost breakdown, score distribution, rankings)
- **Fast search** (FTS5 index on job titles, companies, descriptions)
- **Production-ready** (comprehensive testing, error handling)

---

## Task Breakdown

### Task 5.1: Export Report Generator (380 lines)

**Goal:** Create `src/storage/export.py` with markdown report generation.

**Components:**
- `ExportConfig` class:
  - `include_recommendations` (bool): Include LLM recommendations per job
  - `min_score` (int): Filter jobs by minimum score (0-100)
  - `sort_by` (str): "score" (desc), "company" (asc), "location" (asc)
  - `template_style` (str): "detailed" or "summary"

- `MarkdownExporter` class:
  - `__init__(db_path, config)`: Initialize with assessment store & config
  - `generate_report()` → str: Full markdown report
  - `generate_summary()` → str: Executive summary (top 10 matches)
  - `_render_job_card(job, assessment)` → str: Single job markdown block
  - `_render_statistics()` → str: Cost & score analytics
  - `_render_recommendations()` → str: Consolidated recommendations

- **Report Format:**
  ```
  # Job Assessment Report
  Generated: 2025-01-15 10:30 AM
  Total Jobs: 42 | Assessed: 40 | Filtered: 35 (score ≥ 75)
  Cost: $0.12 (input) + $0.01 (output) = $0.13 total

  ## Top 5 Matches by Score
  1. Senior Engineer @ Acme (Score: 92)
  2. ...

  ## Job Details
  ### [1] Senior Engineer @ Acme
  - Score: 92 | Tech: 95 | Seniority: 88 | Location: 80
  - URL: https://...
  - Description: [first 200 chars]
  - Recommendations: Learn Kubernetes, ...

  ## Analytics
  - Average Score: 76
  - Score Distribution: [histogram]
  - Cost Breakdown: Input 92%, Output 8%

  ## Search Tips
  Use `query --keyword "python" --min-score 75` to refine results.
  ```

**Acceptance Criteria:**
- [ ] `ExportConfig` stores all export preferences
- [ ] `MarkdownExporter` generates valid markdown (passable by markdown validator)
- [ ] `generate_report()` includes all 5 sections (header, top matches, details, analytics, tips)
- [ ] Filtering works: `min_score=75` excludes jobs with score < 75
- [ ] Sorting works: "score" descending, "company" alphabetical
- [ ] Report includes timestamps, cost breakdown, assessment counts
- [ ] Recommendations per job (if enabled) are formatted as bullet list
- [ ] Report size is reasonable: < 500KB for 1000 jobs
- [ ] No N+1 queries: single AssessmentStore query with joins

**Database Queries:**
- FTS5 search + filtering: `SELECT ... FROM job_assessments WHERE overall_score >= :min_score ORDER BY overall_score DESC`
- Cost analytics: `SUM(input_tokens * price_per_token), SUM(output_tokens * price_per_token)`
- Score stats: `AVG(overall_score), MIN, MAX, COUNT`

---

### Task 5.2: Search & Filter Engine (240 lines)

**Goal:** Enhance `AssessmentStore` with rich search & filtering.

**New Methods in `AssessmentStore`:**

- `search_by_keyword(keyword, min_score=0, max_score=100)` → List[Dict]
  - FTS5 search on job title, company, description, recommendations
  - Filter by score range
  - Return top 100 results sorted by relevance + score

- `get_score_ranges()` → Dict[str, List[int]]
  - Return job counts for score buckets: [0-25], [25-50], [50-75], [75-100]
  - Used for histogram in analytics

- `get_top_keywords()` → List[Tuple[str, int]]
  - Extract top 20 keywords from job descriptions using FTS5
  - Return (keyword, frequency) pairs
  - Used for search suggestions

- `get_recommendations_summary()` → Dict[str, int]
  - Aggregate recommendations across all assessments
  - Count frequency: {"Learn AWS": 12, "Improve Python": 8, ...}
  - Used for "Common Skills to Develop" section

- `export_to_dict()` → Dict
  - Full dataset as dict (for JSON export in future)
  - Includes assessments, cost tracking, metadata

**FTS5 Index Updates:**
```sql
-- Ensure index covers all searchable fields
CREATE VIRTUAL TABLE job_assessments_fts USING fts5(
  job_title,
  company,
  description,
  recommendations,
  content='job_assessments',
  content_rowid='id'
);
```

**Acceptance Criteria:**
- [ ] `search_by_keyword()` returns results sorted by relevance (FTS5 rank)
- [ ] Score filtering works: min/max bounds respected
- [ ] `get_score_ranges()` returns 4 buckets with counts
- [ ] `get_top_keywords()` returns 20 keywords (or fewer if DB has < 20 unique)
- [ ] `get_recommendations_summary()` groups by recommendation text
- [ ] FTS5 search handles special characters (-, +, ", *, etc.)
- [ ] Query performance: < 100ms for 1000 jobs with all filters

**Test Coverage:**
- Search for multi-word keywords ("machine learning")
- Search with score filtering (keyword + min_score=75)
- Empty results (no matches) return empty list
- Score ranges sum to total assessment count
- Recommendations deduplicated correctly

---

### Task 5.3: CLI Export Command (180 lines)

**Goal:** Implement `export-results` CLI command in `src/cli.py`.

**Command Signature:**
```bash
uv run python -m src.cli export-results \
  --output data/assessments/report.md \
  --min-score 75 \
  --sort-by score \
  --template detailed \
  --include-recommendations
```

**Parameters:**
- `--output` (Path, required): Markdown file to write
- `--min-score` (int, default=0): Filter jobs by minimum score
- `--max-score` (int, default=100): Filter jobs by maximum score
- `--sort-by` (str, default="score"): "score", "company", "location", "date"
- `--template` (str, default="detailed"): "detailed" or "summary"
- `--include-recommendations` (bool, default=True): Include LLM recommendations
- `--show-stats` (bool, default=True): Include analytics section
- `--output-json` (bool, default=False): Also export as JSON

**Workflow:**
1. Load assessment store from DB
2. Validate parameters (min/max score ranges, output path writable)
3. Create `ExportConfig` from parameters
4. Instantiate `MarkdownExporter`
5. Generate report via `generate_report()`
6. Write to file
7. Display summary: "✓ Exported 35/40 jobs (score ≥ 75) to report.md (142 KB)"

**Edge Cases:**
- Output file already exists: prompt for overwrite (or use `--force`)
- No matching jobs: show warning, export empty report with header
- Database locked: retry 3x with backoff, then error
- Output directory doesn't exist: create it

**Acceptance Criteria:**
- [ ] Command parses all parameters correctly
- [ ] Report written to specified path with UTF-8 encoding
- [ ] File size reported accurately
- [ ] Exit code 0 on success, 1 on error
- [ ] Help text (`--help`) displays all options
- [ ] Validation errors are user-friendly ("min-score must be 0-100")
- [ ] Performance: < 5 seconds for 1000 jobs
- [ ] Concurrent exports possible (no database locks)

**Tests:**
- Export with min_score filter
- Export summary vs. detailed template
- Export with and without recommendations
- Export to non-existent directory (should fail gracefully)
- JSON export (if implemented)

---

### Task 5.4: Search CLI Command (140 lines)

**Goal:** Implement `query` CLI command for interactive job search.

**Command Signature:**
```bash
uv run python -m src.cli query \
  --keyword "python" \
  --min-score 75 \
  --max-score 90 \
  --limit 20
```

**Parameters:**
- `--keyword` (str, required): Search term (supports wildcards: python*, *aws*)
- `--min-score` (int, default=0): Minimum score filter
- `--max-score` (int, default=100): Maximum score filter
- `--limit` (int, default=10): Max results to show
- `--json` (bool, default=False): JSON output
- `--show-stats` (bool, default=True): Show search stats

**Output Format (table):**
```
Search Results: "python" (score 75-100)
Found 12 matches. Showing top 10:

Rank | Company  | Title            | Score | Match
-----|----------|------------------|-------|-------
  1  | Acme     | Senior Engineer  |  92   | ★★★★★ (title, description)
  2  | TechCorp | Python Developer |  88   | ★★★★★ (title, description)
  3  | StartUp  | Backend Engineer |  79   | ★★★☆☆ (description)

Top Keywords: python (8), AWS (5), Kubernetes (3)
Avg Score in Results: 85
Cost Included in Report: Yes
```

**Workflow:**
1. Parse keyword and filters
2. Call `AssessmentStore.search_by_keyword()`
3. Format results as table with relevance stars
4. Display search stats: matches, avg score, top keywords
5. Suggest related searches

**Search Features:**
- Fuzzy matching on company/title (e.g., "amaz" finds Amazon)
- Multi-word keywords (phrases in quotes: `"machine learning"`)
- Boolean operators (AND/OR, future enhancement)
- Wildcard support: `python*` matches "python", "pythonic", etc.

**Acceptance Criteria:**
- [ ] Keyword search returns results in relevance order
- [ ] Score filtering honored
- [ ] Result count limited correctly
- [ ] Table formatting readable (aligned columns)
- [ ] Relevance stars accurate (0-5)
- [ ] Related search suggestions helpful
- [ ] Performance: < 200ms for 1000 jobs with filters
- [ ] No results returns helpful message

**Tests:**
- Search for single-word keyword
- Search with multi-word phrase
- Search with score range filters
- Empty search results
- Limit results to N
- JSON output format

---

### Task 5.5: Comprehensive Testing (320 lines)

**Goal:** Create `tests/test_export.py` with full test coverage.

**Test Classes:**

**TestExportConfig (40 lines)**
- `test_default_values()`: Check defaults (min_score=0, sort="score", etc.)
- `test_invalid_score_range()`: min > max raises ValueError
- `test_template_validation()`: Invalid template raises error
- `test_config_to_dict()`: Serialization works

**TestMarkdownExporter (180 lines)**
- `test_generate_report()`: Full report generated
  - Check header includes timestamp, totals, costs
  - Check top matches section
  - Check details section with ≥ 3 jobs
  - Check analytics with score distribution
- `test_filter_min_score()`: Only jobs with score ≥ min_score included
- `test_sort_by_score()`: Jobs ordered descending by score
- `test_sort_by_company()`: Jobs ordered ascending by company name
- `test_template_summary()`: Summary includes only top 10 jobs
- `test_template_detailed()`: Detailed includes all jobs + recommendations
- `test_empty_results()`: Report generated even with no matching jobs
- `test_markdown_valid()`: Output passes markdown validator (no syntax errors)
- `test_render_job_card()`: Single job formatted correctly with all fields
- `test_render_statistics()`: Stats section includes all metrics

**TestAssessmentStoreSearch (100 lines)**
- `test_search_by_keyword()`: Finds jobs with keyword in title/description
- `test_search_with_score_filter()`: Combined keyword + score filtering
- `test_search_multi_word()`: Phrase search works ("machine learning")
- `test_search_wildcard()`: Wildcard patterns supported
- `test_search_no_results()`: Empty list returned
- `test_get_score_ranges()`: 4 buckets with correct counts
- `test_get_top_keywords()`: Top 20 keywords with frequencies
- `test_get_recommendations_summary()`: Recommendations deduplicated & counted
- `test_search_performance()`: Query completes in < 100ms with 1000 jobs

**TestExportCLI (60 lines)**
- `test_export_command()`: Markdown file created at specified path
- `test_export_with_filters()`: min_score filter applied
- `test_export_nonexistent_dir()`: Directory created if needed
- `test_export_file_overwrite()`: Prompt or --force flag respected
- `test_export_summary_template()`: Summary template smaller than detailed
- `test_export_stats()`: File size reported in output

**TestSearchCLI (40 lines)**
- `test_query_command()`: Search results displayed
- `test_query_with_filters()`: Score range applied
- `test_query_limit()`: Results limited to N
- `test_query_no_results()`: Helpful message shown
- `test_query_json_output()`: JSON format valid

**Fixtures:**
- `sample_assessments` (15 jobs with varying scores 50-98)
- `export_config` (default config)
- `markdown_exporter` (initialized with config)
- `temp_export_dir` (temporary directory for test files)

**Acceptance Criteria:**
- [ ] 40+ tests covering all 3 classes
- [ ] All tests passing
- [ ] Code coverage ≥ 90% for export module
- [ ] Mocks used for file I/O (no temp files on disk)
- [ ] Edge cases tested: empty DB, no results, large datasets
- [ ] Performance tests verify < 100ms queries
- [ ] Tests are isolated & independent

---

## Database Schema (Phase 5 Additions)

**No new tables required.** Phase 5 uses existing `job_assessments` table with enhanced queries:

```sql
-- Enhanced FTS5 index (already created in Phase 4)
CREATE VIRTUAL TABLE IF NOT EXISTS job_assessments_fts USING fts5(
  job_title,
  company,
  description,
  recommendations,
  content='job_assessments',
  content_rowid='id'
);

-- Analytics query
SELECT
  overall_score,
  COUNT(*) as count,
  AVG(actual_cost) as avg_cost,
  SUM(input_tokens) as total_input_tokens
FROM job_assessments
WHERE overall_score >= :min_score
GROUP BY overall_score
ORDER BY overall_score DESC;

-- Search query
SELECT
  ja.id,
  ja.job_title,
  ja.company,
  ja.overall_score,
  ja.recommendations
FROM job_assessments ja
WHERE ja.id IN (
  SELECT content_rowid FROM job_assessments_fts
  WHERE job_assessments_fts MATCH :keyword
)
AND ja.overall_score BETWEEN :min_score AND :max_score
ORDER BY rank, overall_score DESC
LIMIT :limit;
```

---

## Cost & Performance Analysis

### Token Usage (Phase 5 Adds No LLM Calls)
- Export report generation: 0 tokens (data already in DB)
- Search queries: 0 tokens (local FTS5 queries)
- **Total Phase 5 cost: $0.00** (no new API calls)

### Query Performance Targets
| Operation | 100 Jobs | 1000 Jobs | Target |
|-----------|----------|-----------|--------|
| Export report | 200ms | 1000ms | <2s |
| FTS5 search | 50ms | 200ms | <200ms |
| Score ranges | 30ms | 100ms | <100ms |
| Top keywords | 80ms | 300ms | <300ms |

### Report Size Estimates
- Detailed template: ~2-3 KB per job (title, score, recommendations)
- Summary template: ~500 bytes per job
- Analytics section: ~2 KB (fixed)
- Total for 100 jobs detailed: ~300-350 KB
- Total for 1000 jobs detailed: ~3 MB

---

## Error Handling & Edge Cases

| Scenario | Handling |
|----------|----------|
| No matching jobs | Generate report with header + "0 jobs found" message |
| Output file exists | Prompt for overwrite (unless `--force`) |
| Output directory missing | Create directory with `mkdir -p` |
| Database locked | Retry 3x with 1s backoff, then error |
| Invalid score range | Error: "min_score must be ≤ max_score" |
| FTS5 special chars | Escape or quote in search query |
| Large dataset (10k jobs) | Paginate results, stream to file |
| Malformed recommendations | Gracefully skip or truncate |

---

## Success Criteria

✅ **Phase 5 Complete When:**

1. **Export Report Generator** (Task 5.1)
   - `ExportConfig` & `MarkdownExporter` classes created
   - `generate_report()` produces valid markdown
   - Filtering, sorting, templating all functional
   - Report includes header, top matches, details, analytics

2. **Search & Filter Engine** (Task 5.2)
   - `search_by_keyword()`, `get_score_ranges()`, `get_top_keywords()` implemented
   - FTS5 search verified
   - Performance targets met

3. **Export CLI** (Task 5.3)
   - `export-results` command functional
   - All parameters parsed correctly
   - Output file created successfully
   - Edge cases handled

4. **Search CLI** (Task 5.4)
   - `query` command functional
   - Results displayed in readable table
   - Filters & limits working

5. **Testing** (Task 5.5)
   - 40+ tests written
   - All tests passing
   - Coverage ≥ 90%

6. **Quality Assurance**
   - Black formatting applied
   - ruff linting (0 issues)
   - All 50+ tests passing (existing + new)
   - No regressions in Phase 1-4 functionality

7. **Commit**
   - All changes committed to `feat/issue-19` branch
   - Detailed commit message with task breakdown

---

## Implementation Order

1. **Task 5.1** → Create `src/storage/export.py` (export report generator)
2. **Task 5.2** → Enhance `AssessmentStore` (search methods)
3. **Task 5.3** → Add `export-results` CLI command
4. **Task 5.4** → Add `query` CLI command
5. **Task 5.5** → Create `tests/test_export.py` (comprehensive tests)
6. **Format & Lint** → Black + ruff
7. **Final Testing** → All 50+ tests passing
8. **Commit** → Detailed commit message

---

## Known Constraints & Assumptions

**Constraints:**
- Phase 5 assumes all assessments are complete (Phase 4 done)
- No new API calls (Phase 5 is local-only)
- Single database file (no distributed queries)
- Markdown output only (JSON future enhancement)

**Assumptions:**
- Users have Python 3.11+ and all Phase 1-4 dependencies installed
- Database file is accessible and not locked
- FTS5 extension available in SQLite (standard in modern versions)
- Recommendation text is reasonably formatted (no extreme special chars)

**Future Enhancements (Out of Scope):**
- HTML report export (Phase 5+ enhancement)
- PDF export (requires external library)
- Interactive web dashboard
- Email report delivery
- Slack integration

---

## References

**Related Issues:**
- [Issue #19: Full POC Workflow](https://github.com/pluto-atom-4/ats-playground/issues/19)
- [Issue #7: NLP Setup](https://github.com/pluto-atom-4/ats-playground/issues/7)
- [Issue #6: Storage & Database](https://github.com/pluto-atom-4/ats-playground/issues/6)

**Prior Phase Documentation:**
- Phase 1: Crawling (docs/CRAWL.md)
- Phase 2: Preprocessing (docs/PREPROCESS.md)
- Phase 3: Verification (docs/VERIFY.md)
- Phase 4: Assessment (docs/ASSESS.md)
- Phase 5: Export (this document)

**Code References:**
- `src/storage/assessment_store.py` (Phase 4)
- `src/cli.py` (all phases)
- `tests/test_*.py` (all phases)

---

## Sign-Off

**Planning Date:** 2026-01-15
**Author:** GitHub Copilot
**Status:** 🔄 Ready for Implementation
**Estimated Effort:** 40-50 minutes implementation + testing
**Phase 5 Unblocked By:** Phase 4 completion (✅ done)

Next: Proceed with Task 5.1 implementation.
