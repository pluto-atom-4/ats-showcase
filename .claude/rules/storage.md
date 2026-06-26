# Storage Phase Rules

SQLite schema, FTS5 full-text search, markdown export, query patterns.

## SQLite Schema

**Main tables:**

```sql
-- Jobs with extracted data
CREATE TABLE jobs (
  job_id TEXT PRIMARY KEY,
  company TEXT,
  title TEXT,
  location TEXT,
  raw_html TEXT,
  clean_text TEXT,
  status TEXT, -- pending_review, confirmed, rejected
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- Assessment results
CREATE TABLE assessments (
  assessment_id TEXT PRIMARY KEY,
  job_id TEXT FOREIGN KEY,
  cv_id TEXT,
  match_score INT,
  categories JSONB, -- {tech_skills: 85, seniority: 90, ...}
  reasoning TEXT,
  created_at TIMESTAMP,
  FOREIGN KEY(job_id) REFERENCES jobs(job_id)
);

-- Cost tracking (for analytics)
CREATE TABLE cost_tracking (
  cost_id TEXT PRIMARY KEY,
  job_id TEXT,
  estimated_tokens INT,
  actual_tokens INT,
  estimated_cost FLOAT,
  actual_cost FLOAT,
  api_call_time_ms INT,
  created_at TIMESTAMP,
  FOREIGN KEY(job_id) REFERENCES jobs(job_id)
);
```

**FTS5 index (full-text search):**
```sql
CREATE VIRTUAL TABLE jobs_fts USING fts5(
  title, location, clean_text
);
```

Queries complete in <100ms even with 1000+ jobs.

## Database Access Pattern

**Always use JobStore for queries:**

```python
from src.storage.db import JobStore

store = JobStore("data/ats_playground.db")

# Query by keyword
results = store.query_by_keyword("python", min_score=75)

# Get assessment for job
assessment = store.get_assessment(job_id)

# Update job status
store.update_job_status(job_id, "confirmed")
```

**Never write raw SQL.** Use JobStore methods.

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

```bash
# Initialize database
uv run python src/storage/db.py --init

# Export markdown report
uv run python -m src.cli export --output data/assessments/report.md

# Query database
uv run python -m src.cli query --keyword "python" --min-score 75

# Show stats (job count, avg score)
uv run python -m src.cli stats --show-token-usage
```

## Important Notes

- **SQLite is single-writer**: Don't run multiple assessment processes concurrently on same DB. Use a queue or single-process pattern.
- **FTS5 requires SQLite 3.9.0+**: Check version: `sqlite3 --version`
- **Backup before bulk operations**: `cp data/ats_playground.db data/ats_playground.db.bak`
