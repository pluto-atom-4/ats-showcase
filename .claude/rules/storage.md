---
paths:
  - "src/storage/**"
  - "tests/storage/**"
---

# Storage Phase Rules

SQLite schema, FTS5 full-text search, markdown export, query patterns.

## SQLite Schema

**Main tables** (authoritative DDL: `src/storage/schema.py`):

| Table | Constant | Holds |
|-------|----------|-------|
| `job_reviews` | `JOBS_TABLE_SQL` | Crawled jobs: status, tokens, `estimated_cost`, `preprocessing_version` |
| `job_assessments` | `ASSESSMENT_TABLE_SQL` | Scores, summary, token counts, `actual_cost`; `preprocessing_version`, `preprocessing_quality_check`, `previous_assessment_score`, `score_delta` and `model` (#809) are added by `_run_migrations` in `assessment_store.py` |
| `cost_tracking` | `COST_TRACKING_TABLE_SQL` | Per-phase tokens and cost, v1.0 vs v2.0 re-preprocessing deltas |
| `quality_tracking` | `QUALITY_TRACKING_TABLE_SQL` | Score deltas per job between preprocessing versions (history rows; `job_assessments.score_delta` holds only the latest) |

**FTS5 index (full-text search):** `job_assessments_fts` over `job_id, title, company, summary, recommendations` (`ASSESSMENT_FTS_SQL`).

Queries complete in <100ms even with 1000+ jobs.

**Preprocessing Version Tracking (Issue #230 Phase 2 – IMPLEMENTED):**
- `v1.0` – Legacy pipeline (no boilerplate removal via clean_html)
- `v2.0` – New pipeline (70+ boilerplate patterns removed, 3-tier fallback chain for robustness)

Old jobs (v1.0): `clean_text` may contain legal disclaimers, navigation links, company taglines
New jobs (v2.0): `clean_text` cleaned with 7 boilerplate categories removed (legal, headers, company, time, salary, formatting, navigation); robust 3-tier fallback (MarkItDown → BeautifulSoup → Original) ensures preprocessing never fails

**Supported Workflows:**
1. **Selective re-preprocessing**: Query `WHERE preprocessing_version = 'v1.0'` and update to v2.0
2. **Cost analysis**: Compare token usage between pipeline versions
3. **Graceful fallback**: Revert to v1.0 if v2.0 causes quality issues
4. **Version stats**: Track job counts and cost by preprocessing version

## Database Access Pattern

See [_common.md](_common.md#database-access-pattern) for detailed pattern.

## Markdown Export

**Generate reports from assessments:**

```python
from src.storage.export import export_markdown

export_markdown(
  store=store,
  output_file="data/assessments/report.md",
  min_score=75
)
```

**Report includes:**
- Summary (total jobs, avg score)
- Jobs sorted by match_score descending
- Each job: title, company, score, reasoning excerpt

## Verification Commands

See [Database Commands](./_common.md#database) for init, export, query, and stats commands.

## Important Notes

- **SQLite is single-writer**: Don't run multiple assessment processes concurrently on same DB. Use a queue or single-process pattern.
- **FTS5 requires SQLite 3.9.0+**: Check version: `sqlite3 --version`
- **Backup before bulk operations**: `cp data/ats_playground.db data/ats_playground.db.bak`
