# STORAGE Phase: Data Persistence, Querying, and Export

## Overview

The STORAGE phase manages all job assessment data, enabling:

1. **Persistent storage** - SQLite database with atomic transactions
2. **Full-text search** - FTS5 indexing for fast queries (job title, skills, requirements)
3. **Rich metadata** - Token counts, costs, verification status, assessment scores
4. **Markdown export** - Generate shareable reports grouped by match score
5. **Data lifecycle** - Archive old data, purge sensitive fields, maintain data quality
6. **Cost tracking** - Monitor cumulative spend per company, per candidate

## Architecture

### Data Flow

```
ASSESS Phase Output
(assessment results, costs)
        ↓
┌──────────────────────────────┐
│  Transform & Validate Data   │
│ - Normalize field values     │
│ - Validate relationships     │
│ - Calculate derived fields   │
└──────────────────────────────┘
        ↓
┌──────────────────────────────┐
│  Insert into SQLite          │
│ - Jobs table (deduplicated) │
│ - Assessments table         │
│ - Update FTS5 index         │
└──────────────────────────────┘
        ↓
┌──────────────────────────────┐
│  Query Interface             │
│ - SQL queries (direct)       │
│ - Keyword search (FTS5)      │
│ - Filter by score/date/status│
└──────────────────────────────┘
        ↓
┌──────────────────────────────┐
│  Export Options              │
│ - Markdown (grouped by score)│
│ - CSV (raw data)             │
│ - JSON (API export)          │
└──────────────────────────────┘
```

## SQLite Schema

### Core Tables

```sql
-- Jobs metadata (from CRAWL + PREPROCESS phases)
CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    title TEXT NOT NULL,
    requirements TEXT,
    responsibilities TEXT,
    benefits TEXT,
    salary TEXT,
    posting_url TEXT,

    -- Preprocessing metadata
    raw_html_tokens INT,
    cleaned_text_tokens INT,
    chunks_count INT,
    preprocessing_latency_ms REAL,

    -- Verification status
    verified BOOLEAN DEFAULT 0,
    verified_by TEXT,
    verified_at TIMESTAMP,

    -- Extraction metadata
    crawled_at TIMESTAMP NOT NULL,
    extracted_at TIMESTAMP NOT NULL,

    -- Deduplication
    content_hash TEXT UNIQUE,  -- SHA256 of normalized text
    duplicate_of_job_id TEXT,  -- Reference if duplicate

    -- Status tracking
    status TEXT DEFAULT 'pending',  -- pending|confirmed|rejected|archived

    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Assessment results (from ASSESS phase)
CREATE TABLE assessments (
    assessment_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    cv_id TEXT NOT NULL,

    -- Assessment output
    match_score REAL NOT NULL,  -- 0.0-1.0
    recommendation TEXT NOT NULL,  -- strong_match|moderate_match|weak_match
    reasoning TEXT,
    strengths TEXT,  -- JSON array
    gaps TEXT,  -- JSON array

    -- Cost tracking
    input_tokens INT NOT NULL,
    output_tokens INT NOT NULL,
    model TEXT DEFAULT 'claude-3-5-sonnet-20241022',
    cost_usd REAL,  -- Calculated: (input/1M)*3.00 + (output/1M)*15.00

    -- Performance
    latency_ms REAL,
    retry_count INT DEFAULT 0,

    -- Status
    status TEXT DEFAULT 'completed',  -- completed|failed|incomplete
    error_message TEXT,

    -- Audit
    assessed_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (job_id) REFERENCES jobs (job_id)
);

-- CV references (user-provided data)
CREATE TABLE cvs (
    cv_id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,

    -- Preprocessing metadata
    raw_text_tokens INT,
    cleaned_text_tokens INT,

    -- CV content (summarized)
    summary TEXT,
    skills TEXT,  -- JSON array
    experience_years INT,

    -- Status
    status TEXT DEFAULT 'active',  -- active|archived

    -- Audit
    uploaded_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cost tracking (summary for reporting)
CREATE TABLE cost_tracking (
    tracking_id INTEGER PRIMARY KEY AUTOINCREMENT,

    company_name TEXT,
    cv_id TEXT,

    -- Aggregates
    total_jobs INT,
    total_assessments INT,
    total_input_tokens INT,
    total_output_tokens INT,
    total_cost_usd REAL,

    avg_match_score REAL,

    -- Time period
    period_start TIMESTAMP,
    period_end TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (cv_id) REFERENCES cvs (cv_id)
);
```

### FTS5 Full-Text Search Index

```sql
-- Enable FTS5 extension
PRAGMA compile_options;  -- Verify FTS5 support

-- Create FTS5 virtual table for job search
CREATE VIRTUAL TABLE jobs_fts USING fts5(
    -- Indexed fields
    title,
    requirements,
    responsibilities,
    benefits,

    -- Metadata (not indexed, but stored)
    company_name UNINDEXED,
    job_id UNINDEXED,

    -- Options
    content='jobs',
    content_rowid='rowid',
    tokenize='porter'  -- Stemming: "testing" matches "test"
);

-- Trigger to keep FTS5 index in sync with jobs table
CREATE TRIGGER jobs_ai AFTER INSERT ON jobs BEGIN
  INSERT INTO jobs_fts(rowid, title, requirements, responsibilities, benefits, company_name, job_id)
  VALUES (new.rowid, new.title, new.requirements, new.responsibilities, new.benefits, new.company_name, new.job_id);
END;

CREATE TRIGGER jobs_ad AFTER DELETE ON jobs BEGIN
  DELETE FROM jobs_fts WHERE rowid = old.rowid;
END;

CREATE TRIGGER jobs_au AFTER UPDATE ON jobs BEGIN
  DELETE FROM jobs_fts WHERE rowid = old.rowid;
  INSERT INTO jobs_fts(rowid, title, requirements, responsibilities, benefits, company_name, job_id)
  VALUES (new.rowid, new.title, new.requirements, new.responsibilities, new.benefits, new.company_name, new.job_id);
END;
```

## Implementation: Database Client

```python
import sqlite3
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import asdict
import hashlib

class StorageClient:
    """SQLite database client with FTS5 support."""

    def __init__(self, db_path: str = "data/ats_playground.db"):
        self.db_path = db_path
        self.conn = None
        self._connect()

    def _connect(self):
        """Initialize database connection with FTS5."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # Enable column-based access

        # Enable FTS5 if available
        try:
            self.conn.execute("PRAGMA compile_options;")
            self.conn.enable_load_extension(True)
        except Exception as e:
            print(f"Warning: Could not enable FTS5: {e}")

    def init_schema(self):
        """Create all tables and indexes."""
        cursor = self.conn.cursor()

        # Jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                company_name TEXT NOT NULL,
                title TEXT NOT NULL,
                requirements TEXT,
                responsibilities TEXT,
                benefits TEXT,
                salary TEXT,
                posting_url TEXT,
                raw_html_tokens INT,
                cleaned_text_tokens INT,
                chunks_count INT,
                preprocessing_latency_ms REAL,
                verified BOOLEAN DEFAULT 0,
                verified_by TEXT,
                verified_at TIMESTAMP,
                crawled_at TIMESTAMP NOT NULL,
                extracted_at TIMESTAMP NOT NULL,
                content_hash TEXT UNIQUE,
                duplicate_of_job_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Assessments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS assessments (
                assessment_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                cv_id TEXT NOT NULL,
                match_score REAL NOT NULL,
                recommendation TEXT NOT NULL,
                reasoning TEXT,
                strengths TEXT,
                gaps TEXT,
                input_tokens INT NOT NULL,
                output_tokens INT NOT NULL,
                model TEXT DEFAULT 'claude-3-5-sonnet-20241022',
                cost_usd REAL,
                latency_ms REAL,
                retry_count INT DEFAULT 0,
                status TEXT DEFAULT 'completed',
                error_message TEXT,
                assessed_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES jobs (job_id)
            );
        """)

        # CVs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cvs (
                cv_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                raw_text_tokens INT,
                cleaned_text_tokens INT,
                summary TEXT,
                skills TEXT,
                experience_years INT,
                status TEXT DEFAULT 'active',
                uploaded_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Cost tracking table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cost_tracking (
                tracking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT,
                cv_id TEXT,
                total_jobs INT,
                total_assessments INT,
                total_input_tokens INT,
                total_output_tokens INT,
                total_cost_usd REAL,
                avg_match_score REAL,
                period_start TIMESTAMP,
                period_end TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cv_id) REFERENCES cvs (cv_id)
            );
        """)

        # Indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_company
            ON jobs(company_name);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_status
            ON jobs(status);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_assessments_job
            ON assessments(job_id);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_assessments_cv
            ON assessments(cv_id);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_assessments_score
            ON assessments(match_score DESC);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_assessments_date
            ON assessments(assessed_at DESC);
        """)

        self.conn.commit()
        print(f"✓ Database initialized: {self.db_path}")

    def insert_job(self, job: dict) -> str:
        """Insert job and return job_id."""
        content_hash = hashlib.sha256(
            f"{job['title']}|{job['requirements']}".encode()
        ).hexdigest()

        cursor = self.conn.cursor()
        job_id = job.get('job_id') or f"job_{content_hash[:12]}"

        try:
            cursor.execute("""
                INSERT INTO jobs (
                    job_id, company_name, title, requirements, responsibilities,
                    benefits, salary, posting_url, raw_html_tokens, cleaned_text_tokens,
                    chunks_count, preprocessing_latency_ms, crawled_at, extracted_at,
                    content_hash, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id, job['company_name'], job['title'],
                job.get('requirements'), job.get('responsibilities'),
                job.get('benefits'), job.get('salary'), job.get('posting_url'),
                job.get('raw_html_tokens', 0), job.get('cleaned_text_tokens', 0),
                job.get('chunks_count', 0), job.get('preprocessing_latency_ms', 0),
                job['crawled_at'], job['extracted_at'],
                content_hash, job.get('status', 'pending')
            ))
            self.conn.commit()
            return job_id

        except sqlite3.IntegrityError as e:
            print(f"Job already exists or duplicate: {e}")
            return job_id

    def insert_assessment(self, assessment: dict) -> str:
        """Insert assessment result."""
        cursor = self.conn.cursor()
        assessment_id = assessment.get('assessment_id') or \
                       f"assess_{assessment['job_id']}_{assessment['cv_id']}"

        cursor.execute("""
            INSERT INTO assessments (
                assessment_id, job_id, cv_id, match_score, recommendation,
                reasoning, strengths, gaps, input_tokens, output_tokens,
                model, cost_usd, latency_ms, retry_count, status, error_message,
                assessed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            assessment_id, assessment['job_id'], assessment['cv_id'],
            assessment['match_score'], assessment['recommendation'],
            assessment.get('reasoning'),
            json.dumps(assessment.get('strengths', [])),
            json.dumps(assessment.get('gaps', [])),
            assessment['input_tokens'], assessment['output_tokens'],
            assessment.get('model', 'claude-3-5-sonnet-20241022'),
            assessment.get('cost_usd'), assessment.get('latency_ms'),
            assessment.get('retry_count', 0), assessment.get('status', 'completed'),
            assessment.get('error_message'), assessment['assessed_at']
        ))
        self.conn.commit()
        return assessment_id

    def search_jobs(self, query: str, limit: int = 50) -> List[Dict]:
        """Full-text search jobs by keywords."""
        cursor = self.conn.cursor()

        # FTS5 query (if available) or fallback to LIKE
        try:
            cursor.execute("""
                SELECT j.* FROM jobs j
                JOIN jobs_fts fts ON j.rowid = fts.rowid
                WHERE jobs_fts MATCH ?
                LIMIT ?
            """, (query, limit))
        except sqlite3.OperationalError:
            # Fallback to LIKE search if FTS5 not available
            query_pattern = f"%{query}%"
            cursor.execute("""
                SELECT * FROM jobs WHERE
                title LIKE ? OR requirements LIKE ? OR
                responsibilities LIKE ? OR benefits LIKE ?
                LIMIT ?
            """, (query_pattern, query_pattern, query_pattern, query_pattern, limit))

        return [dict(row) for row in cursor.fetchall()]

    def get_best_matches(
        self,
        cv_id: str,
        min_score: float = 0.7,
        limit: int = 20,
    ) -> List[Dict]:
        """Get top-scoring job matches for a CV."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                a.assessment_id,
                a.job_id,
                a.match_score,
                a.recommendation,
                a.reasoning,
                j.title,
                j.company_name,
                j.salary,
                j.posting_url,
                a.assessed_at
            FROM assessments a
            JOIN jobs j ON a.job_id = j.job_id
            WHERE a.cv_id = ? AND a.match_score >= ?
            ORDER BY a.match_score DESC
            LIMIT ?
        """, (cv_id, min_score, limit))

        return [dict(row) for row in cursor.fetchall()]

    def get_cost_summary(
        self,
        company_name: Optional[str] = None,
        cv_id: Optional[str] = None,
        days: Optional[int] = None,
    ) -> Dict:
        """Get cost summary for reporting."""
        cursor = self.conn.cursor()

        query = "SELECT * FROM assessments WHERE 1=1"
        params = []

        if company_name:
            query += """ AND job_id IN (
                SELECT job_id FROM jobs WHERE company_name = ?
            )"""
            params.append(company_name)

        if cv_id:
            query += " AND cv_id = ?"
            params.append(cv_id)

        if days:
            cutoff_date = datetime.now() - timedelta(days=days)
            query += " AND assessed_at > ?"
            params.append(cutoff_date.isoformat())

        cursor.execute(query)
        assessments = cursor.fetchall()

        total_input = sum(a['input_tokens'] for a in assessments)
        total_output = sum(a['output_tokens'] for a in assessments)
        total_cost = sum(a['cost_usd'] for a in assessments if a['cost_usd'])

        return {
            "total_assessments": len(assessments),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cost_usd": round(total_cost, 2),
            "avg_cost_per_assessment": round(total_cost / max(len(assessments), 1), 6),
            "avg_match_score": sum(a['match_score'] for a in assessments) / max(len(assessments), 1),
        }
```

## Querying Patterns

### Common Queries

```python
# Find strong matches (score >= 0.85)
def get_strong_matches(storage: StorageClient, cv_id: str) -> List[Dict]:
    return storage.get_best_matches(cv_id, min_score=0.85, limit=10)

# Search by keyword (e.g., "MES" or "Python")
def search_by_skill(storage: StorageClient, skill: str) -> List[Dict]:
    return storage.search_jobs(skill, limit=50)

# Get jobs from specific company
def get_company_jobs(storage: StorageClient, company: str) -> List[Dict]:
    cursor = storage.conn.cursor()
    cursor.execute("""
        SELECT j.*, COUNT(a.assessment_id) as assessment_count
        FROM jobs j
        LEFT JOIN assessments a ON j.job_id = a.job_id
        WHERE j.company_name = ?
        GROUP BY j.job_id
    """, (company,))
    return [dict(row) for row in cursor.fetchall()]

# Calculate match distribution
def get_match_distribution(storage: StorageClient, cv_id: str) -> Dict:
    cursor = storage.conn.cursor()
    cursor.execute("""
        SELECT
            recommendation,
            COUNT(*) as count,
            ROUND(AVG(match_score), 2) as avg_score
        FROM assessments
        WHERE cv_id = ?
        GROUP BY recommendation
        ORDER BY avg_score DESC
    """, (cv_id,))

    return {row['recommendation']: {
        'count': row['count'],
        'avg_score': row['avg_score']
    } for row in cursor.fetchall()}

# Find duplicate jobs
def find_duplicates(storage: StorageClient, company: str) -> List[Tuple]:
    cursor = storage.conn.cursor()
    cursor.execute("""
        SELECT j1.job_id, j2.job_id, j1.title
        FROM jobs j1
        JOIN jobs j2 ON j1.content_hash = j2.content_hash
            AND j1.company_name = ?
            AND j2.company_name = ?
            AND j1.job_id < j2.job_id
    """, (company, company))
    return cursor.fetchall()

# Get recent assessments with cost
def get_recent_assessments(storage: StorageClient, days: int = 7) -> List[Dict]:
    cursor = storage.conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    cursor.execute("""
        SELECT
            a.assessment_id,
            j.title,
            j.company_name,
            a.match_score,
            a.recommendation,
            a.input_tokens,
            a.output_tokens,
            a.cost_usd,
            a.assessed_at
        FROM assessments a
        JOIN jobs j ON a.job_id = j.job_id
        WHERE a.assessed_at > ?
        ORDER BY a.assessed_at DESC
    """, (cutoff,))

    return [dict(row) for row in cursor.fetchall()]
```

### Date Range Filtering

Filter assessments by date range for targeted exports and analysis:

```python
from storage.export import parse_date_str, ExportConfig, MarkdownExporter

# Parse date strings (ISO 8601 format: YYYY-MM-DD)
date_from = parse_date_str("2025-06-01")
date_to = parse_date_str("2025-12-31")

# Create config with date filters
config = ExportConfig(
    date_from=date_from,
    date_to=date_to,
    min_score=75,
    max_score=95
)

# Generate filtered report
exporter = MarkdownExporter(store, config)
report = exporter.generate_report()

# Date filtering semantics:
# - date_from: Include assessments on or after this date (inclusive)
# - date_to: Include assessments on or before this date (inclusive)
# - Both can be used together for a precise date range
# - Filters applied after score filtering
```

## Data Lifecycle: Purging Old Assessments

Purge old assessments by date range with safety features:

```python
from storage.assessment_store import AssessmentStore

store = AssessmentStore()

# Preview what would be deleted (dry-run mode is default)
result = store.purge_by_date(before_date="2025-04-01", dry_run=True)
print(f"Would delete {result['count']} assessments")
# Output: {'count': 42, 'dry_run': True, 'before_date': '2025-04-01', 'after_date': None}

# Actually delete assessments (requires dry_run=False explicitly)
result = store.purge_by_date(before_date="2025-04-01", dry_run=False)
print(f"Deleted {result['count']} assessments")
# Output: {'count': 42, 'dry_run': False, 'before_date': '2025-04-01', 'after_date': None}

# Purge with date range (delete assessments between two dates)
result = store.purge_by_date(
    after_date="2025-01-01",
    before_date="2025-03-31",
    dry_run=False
)
print(f"Deleted {result['count']} assessments from Q1 2025")

# Purge semantics:
# - before_date: Delete assessments with assessed_date < date
# - after_date: Delete assessments with assessed_date > date
# - Combines with AND logic for precise range control
# - Dates in ISO 8601 format: YYYY-MM-DD
# - Cleans up both main table and FTS5 index atomically
```

### Safety Features

Default behaviors prevent accidental deletion:

```python
# Safe by default: dry_run=True (preview only)
result = store.purge_by_date(before_date="2025-04-01")
# Returns count but DOES NOT delete

# Requires explicit flag for deletion
result = store.purge_by_date(before_date="2025-04-01", dry_run=False)
# Now actually deletes

# CLI enforces dual-flag requirement
# Must provide BOTH: --no-dry-run AND --confirm
# If only one provided, operation fails safely
```

## Export to Markdown

```python
class MarkdownExporter:
    """Export assessments to markdown reports."""

    def __init__(self, storage: StorageClient):
        self.storage = storage

    def export_by_score(
        self,
        cv_id: str,
        output_file: str = "assessments_report.md",
    ):
        """Export matches grouped by score tier."""
        cursor = self.storage.conn.cursor()
        cursor.execute("""
            SELECT
                a.assessment_id,
                a.match_score,
                a.recommendation,
                a.reasoning,
                a.strengths,
                a.gaps,
                j.title,
                j.company_name,
                j.requirements,
                j.salary,
                j.posting_url
            FROM assessments a
            JOIN jobs j ON a.job_id = j.job_id
            WHERE a.cv_id = ?
            ORDER BY a.match_score DESC
        """, (cv_id,))

        assessments = cursor.fetchall()

        with open(output_file, 'w') as f:
            f.write(f"# Job Assessment Report\n\n")
            f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Total matches**: {len(assessments)}\n\n")

            # Strong matches (0.8-1.0)
            strong = [a for a in assessments if a['match_score'] >= 0.8]
            self._write_section(f, "🟢 Strong Matches", strong)

            # Moderate matches (0.5-0.8)
            moderate = [a for a in assessments
                       if 0.5 <= a['match_score'] < 0.8]
            self._write_section(f, "🟡 Moderate Matches", moderate)

            # Weak matches (0.0-0.5)
            weak = [a for a in assessments if a['match_score'] < 0.5]
            self._write_section(f, "🔴 Weak Matches", weak)

        print(f"✓ Report exported: {output_file}")

    def _write_section(self, f, title: str, assessments: List[sqlite3.Row]):
        """Write section with assessments."""
        f.write(f"\n## {title}\n\n")
        f.write(f"**Count**: {len(assessments)}\n\n")

        for assessment in assessments:
            f.write(f"### {assessment['title']} @ {assessment['company_name']}\n\n")
            f.write(f"**Score**: {assessment['match_score']:.1%}\n\n")
            f.write(f"**Recommendation**: {assessment['recommendation']}\n\n")
            f.write(f"**Reasoning**: {assessment['reasoning']}\n\n")

            if assessment['salary']:
                f.write(f"**Salary**: {assessment['salary']}\n\n")

            if assessment['requirements']:
                f.write(f"**Requirements**: {assessment['requirements']}\n\n")

            strengths = json.loads(assessment['strengths'] or '[]')
            if strengths:
                f.write(f"**Strengths**:\n")
                for s in strengths:
                    f.write(f"- {s}\n")
                f.write("\n")

            gaps = json.loads(assessment['gaps'] or '[]')
            if gaps:
                f.write(f"**Gaps**:\n")
                for g in gaps:
                    f.write(f"- {g}\n")
                f.write("\n")

            if assessment['posting_url']:
                f.write(f"[View Posting]({assessment['posting_url']})\n\n")

            f.write("---\n\n")
```

## Data Lifecycle Management

```python
class DataLifecycleManager:
    """Handle archival, purge, and retention policies."""

    def __init__(self, storage: StorageClient):
        self.storage = storage

    def archive_old_data(self, days: int = 90):
        """Archive assessments older than N days."""
        cursor = self.storage.conn.cursor()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        cursor.execute("""
            UPDATE assessments
            SET status = 'archived'
            WHERE assessed_at < ? AND status != 'archived'
        """, (cutoff,))

        archived_count = cursor.rowcount
        self.storage.conn.commit()

        print(f"✓ Archived {archived_count} old assessments")

    def delete_sensitive_data(self, cv_id: str):
        """Purge CV and associated assessment details."""
        cursor = self.storage.conn.cursor()

        # Delete CV content
        cursor.execute("""
            UPDATE cvs
            SET summary = NULL, skills = NULL
            WHERE cv_id = ?
        """, (cv_id,))

        # Redact assessment reasoning (GDPR compliance)
        cursor.execute("""
            UPDATE assessments
            SET reasoning = '[redacted]', strengths = '[]', gaps = '[]'
            WHERE cv_id = ?
        """, (cv_id,))

        self.storage.conn.commit()
        print(f"✓ Purged sensitive data for CV {cv_id}")

    def generate_retention_report(self) -> Dict:
        """Report on data retention status."""
        cursor = self.storage.conn.cursor()

        cursor.execute("""
            SELECT
                status,
                COUNT(*) as count,
                MIN(assessed_at) as oldest,
                MAX(assessed_at) as newest
            FROM assessments
            GROUP BY status
        """)

        return {
            row['status']: {
                'count': row['count'],
                'oldest': row['oldest'],
                'newest': row['newest']
            } for row in cursor.fetchall()
        }
```

## Performance Optimization

### Indexes Strategy

| Query Pattern | Index | Impact |
|---------------|-------|--------|
| Filter by company | `idx_jobs_company` | 100-500x for large datasets |
| Filter by status | `idx_jobs_status` | 50-100x for status queries |
| Top N by score | `idx_assessments_score` | 10-50x for ranking queries |
| Recent assessments | `idx_assessments_date` | 10-100x for time-based queries |
| FTS keyword search | `jobs_fts (FTS5)` | 5-50x for text search |

### Query Optimization Tips

```python
# ❌ BAD: Loads all assessments then filters in Python
assessments = cursor.execute("SELECT * FROM assessments").fetchall()
strong = [a for a in assessments if a['match_score'] >= 0.8]  # Slow!

# ✅ GOOD: Filter at database level (uses index)
cursor.execute("""
    SELECT * FROM assessments
    WHERE match_score >= 0.8
    ORDER BY match_score DESC
    LIMIT 10
""")  # Fast!

# ❌ BAD: Multiple joins without indexes
# ✅ GOOD: Ensure indexes on foreign keys (job_id, cv_id)
CREATE INDEX idx_assessments_job ON assessments(job_id);
CREATE INDEX idx_assessments_cv ON assessments(cv_id);
```

## Deployment Checklist

- [ ] **Database setup**:
  - [ ] Create `data/` directory
  - [ ] Run `StorageClient().init_schema()`
  - [ ] Verify `ats_playground.db` created

- [ ] **Migration** (if upgrading from old schema):
  - [ ] Backup existing database: `cp ats_playground.db ats_playground.db.backup`
  - [ ] Run migration scripts (if any)
  - [ ] Verify data integrity: `PRAGMA integrity_check;`

- [ ] **Testing**:
  - [ ] Insert 100+ test jobs
  - [ ] Run FTS5 search queries (verify speed <100ms)
  - [ ] Export markdown report
  - [ ] Verify cost calculations

- [ ] **Monitoring**:
  - [ ] Log all write operations
  - [ ] Alert if database exceeds 1 GB
  - [ ] Archive data older than 90 days monthly

- [ ] **Backup**:
  - [ ] Daily automated backup to S3/cloud storage
  - [ ] Test restore procedure
  - [ ] Retention policy: keep 30-day rolling backup

## Integration with Other Phases

### Input from ASSESS Phase
- Assessment results (match_score, recommendation, reasoning)
- Token counts and costs
- Error logs for failed assessments
- Metadata (latency, model, timestamps)

### Output to CLI Phase
- Query results (for `python main.py query` command)
- Markdown exports (for `python main.py export` command)
- Cost summaries (for `python main.py stats` command)

## Next Steps

1. **Migration strategy**: Plan upgrade path for existing data
2. **Backup automation**: Set up daily backups (cloud-agnostic)
3. **Export formats**: Add CSV, JSON, PDF export options
4. **Analytics dashboard**: Query interface for cost/performance trends
5. **Data warehouse**: Consider DuckDB or Parquet for larger datasets (1M+ rows)

---

**Related Documentation**:
- [ASSESS.md](./ASSESS.md) - Assessment data source
- [VERIFY.md](./VERIFY.md) - Job verification data
- [CLI.md](./CLI.md) - Query/export commands
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System data flow
- [COMPATIBILITY.md](./COMPATIBILITY.md) - SQLite version compatibility
