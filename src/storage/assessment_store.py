"""Assessment storage and database operations."""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AssessmentStore:
    """SQLite storage for job assessments."""

    ASSESSMENT_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS job_assessments (
        job_id TEXT PRIMARY KEY,
        title TEXT,
        company TEXT,
        location TEXT,
        overall_score REAL,
        tech_score REAL,
        seniority_score REAL,
        location_score REAL,
        recommendations TEXT,
        summary TEXT,
        tokens_used INTEGER,
        input_tokens INTEGER DEFAULT 0,
        output_tokens INTEGER DEFAULT 0,
        actual_cost REAL,
        assessed_date TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES job_reviews(job_id)
    )
    """

    ASSESSMENT_FTS_SQL = """
    CREATE VIRTUAL TABLE IF NOT EXISTS job_assessments_fts USING fts5(
        job_id, title, company, summary, recommendations
    )
    """

    def __init__(self, db_path: str = "data/ats_playground.db"):
        """Initialize assessment store."""
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._initialize_db()

    def _initialize_db(self) -> None:
        """Initialize database and schema."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

        cursor = self.conn.cursor()

        # Create main table
        cursor.execute(self.ASSESSMENT_TABLE_SQL)

        # Create FTS table
        cursor.execute(self.ASSESSMENT_FTS_SQL)

        # Create indices
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_job_assessments_score "
            "ON job_assessments(overall_score DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_job_assessments_job_id " "ON job_assessments(job_id)"
        )

        self.conn.commit()
        logger.info("Initialized assessment database")

    def _close_db(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def save_assessment(
        self,
        job_id: str,
        title: str,
        company: Optional[str],
        location: Optional[str],
        overall_score: float,
        tech_score: float,
        seniority_score: float,
        location_score: float,
        recommendations: List[str],
        summary: str,
        tokens_used: int,
        actual_cost: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """Save assessment to database."""
        if not self.conn:
            return

        cursor = self.conn.cursor()

        # Save to main table
        cursor.execute(
            """INSERT OR REPLACE INTO job_assessments
               (job_id, title, company, location, overall_score, tech_score,
                seniority_score, location_score, recommendations, summary,
                tokens_used, input_tokens, output_tokens, actual_cost, assessed_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                job_id,
                title,
                company,
                location,
                overall_score,
                tech_score,
                seniority_score,
                location_score,
                json.dumps(recommendations),
                summary,
                tokens_used,
                input_tokens,
                output_tokens,
                actual_cost,
            ),
        )

        # Update FTS index
        cursor.execute(
            """INSERT OR REPLACE INTO job_assessments_fts
               (job_id, title, company, summary, recommendations)
               VALUES (?, ?, ?, ?, ?)""",
            (job_id, title, company or "", summary, " ".join(recommendations)),
        )

        self.conn.commit()
        logger.debug(f"Saved assessment for job {job_id}")

    def get_assessment_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get assessment by job ID."""
        if not self.conn:
            return None

        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM job_assessments WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()

        if not row:
            return None

        result = dict(row)
        if result.get("recommendations"):
            result["recommendations"] = json.loads(result["recommendations"])

        return result

    def get_top_matches(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top-scoring assessments."""
        if not self.conn:
            return []

        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT * FROM job_assessments
               ORDER BY overall_score DESC LIMIT ?""",
            (limit,),
        )

        results = []
        for row in cursor.fetchall():
            result = dict(row)
            if result.get("recommendations"):
                result["recommendations"] = json.loads(result["recommendations"])
            results.append(result)

        return results

    def get_assessments_by_score(
        self, min_score: float = 70, max_score: float = 100, company: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get assessments within score range, optionally filtered by company."""
        if not self.conn:
            return []

        cursor = self.conn.cursor()

        if company:
            cursor.execute(
                """SELECT * FROM job_assessments
                   WHERE overall_score >= ? AND overall_score <= ? AND company = ?
                   ORDER BY overall_score DESC""",
                (min_score, max_score, company),
            )
        else:
            cursor.execute(
                """SELECT * FROM job_assessments
                   WHERE overall_score >= ? AND overall_score <= ?
                   ORDER BY overall_score DESC""",
                (min_score, max_score),
            )

        results = []
        for row in cursor.fetchall():
            result = dict(row)
            if result.get("recommendations"):
                result["recommendations"] = json.loads(result["recommendations"])
            results.append(result)

        return results

    def search_assessments(self, query: str) -> List[Dict[str, Any]]:
        """Full-text search assessments."""
        if not self.conn:
            return []

        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """SELECT * FROM job_assessments
                   WHERE job_id IN (
                       SELECT job_id FROM job_assessments_fts
                       WHERE job_assessments_fts MATCH ?
                   )
                   ORDER BY overall_score DESC""",
                (query,),
            )

            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result.get("recommendations"):
                    result["recommendations"] = json.loads(result["recommendations"])
                results.append(result)

            return results
        except sqlite3.OperationalError as e:
            logger.warning(f"FTS search failed: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Get assessment statistics."""
        if not self.conn:
            return {}

        cursor = self.conn.cursor()

        # Total assessments
        cursor.execute("SELECT COUNT(*) as count FROM job_assessments")
        total = cursor.fetchone()["count"]

        if total == 0:
            return {
                "total_assessments": 0,
                "avg_score": 0,
                "max_score": 0,
                "min_score": 0,
                "total_cost": 0,
                "avg_cost": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
            }

        # Scores & tokens
        cursor.execute("""SELECT
               AVG(overall_score) as avg_score,
               MAX(overall_score) as max_score,
               MIN(overall_score) as min_score,
               SUM(actual_cost) as total_cost,
               SUM(COALESCE(input_tokens, 0)) as total_input_tokens,
               SUM(COALESCE(output_tokens, 0)) as total_output_tokens
               FROM job_assessments""")
        row = cursor.fetchone()

        return {
            "total_assessments": total,
            "avg_score": row["avg_score"] or 0,
            "max_score": row["max_score"] or 0,
            "min_score": row["min_score"] or 0,
            "total_cost": row["total_cost"] or 0,
            "avg_cost": (row["total_cost"] or 0) / total if total > 0 else 0,
            "total_input_tokens": row["total_input_tokens"] or 0,
            "total_output_tokens": row["total_output_tokens"] or 0,
        }

    def get_score_distribution(self) -> Dict[str, int]:
        """Get distribution of scores by range."""
        if not self.conn:
            return {}

        cursor = self.conn.cursor()

        ranges = {
            "0-50": (0, 50),
            "50-70": (50, 70),
            "70-85": (70, 85),
            "85-100": (85, 100),
        }

        distribution = {}
        for label, (min_score, max_score) in ranges.items():
            cursor.execute(
                """SELECT COUNT(*) as count FROM job_assessments
                   WHERE overall_score >= ? AND overall_score < ?""",
                (min_score, max_score),
            )
            distribution[label] = cursor.fetchone()["count"]

        return distribution

    def get_score_ranges(self) -> Dict[str, int]:
        """Get job counts by score range (for analytics)."""
        if not self.conn:
            return {}

        cursor = self.conn.cursor()
        ranges = {}

        for range_key in ["0-25", "25-50", "50-75", "75-100"]:
            min_s, max_s = map(int, range_key.split("-"))
            cursor.execute(
                """SELECT COUNT(*) as count FROM job_assessments
                   WHERE overall_score >= ? AND overall_score < ?""",
                (min_s, max_s),
            )
            ranges[range_key] = cursor.fetchone()["count"]

        return ranges

    def search_by_keyword(
        self,
        keyword: str,
        min_score: int = 0,
        max_score: int = 100,
        company: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Search assessments by keyword with optional company and score filters.

        Args:
            keyword: Search term
            min_score: Minimum score filter
            max_score: Maximum score filter
            company: Optional company filter
            limit: Maximum results to return

        Returns:
            List of matching assessments
        """
        if not self.conn or not keyword:
            return []

        cursor = self.conn.cursor()

        try:
            if company:
                cursor.execute(
                    """SELECT ja.* FROM job_assessments ja
                       WHERE ja.job_id IN (
                           SELECT job_id FROM job_assessments_fts
                           WHERE job_assessments_fts MATCH ?
                       )
                       AND ja.overall_score BETWEEN ? AND ?
                       AND ja.company = ?
                       ORDER BY ja.overall_score DESC
                       LIMIT ?""",
                    (keyword, min_score, max_score, company, limit),
                )
            else:
                cursor.execute(
                    """SELECT ja.* FROM job_assessments ja
                       WHERE ja.job_id IN (
                           SELECT job_id FROM job_assessments_fts
                           WHERE job_assessments_fts MATCH ?
                       )
                       AND ja.overall_score BETWEEN ? AND ?
                       ORDER BY ja.overall_score DESC
                       LIMIT ?""",
                    (keyword, min_score, max_score, limit),
                )

            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result.get("recommendations"):
                    result["recommendations"] = json.loads(result["recommendations"])
                results.append(result)

            return results
        except sqlite3.OperationalError as e:
            logger.warning(f"Keyword search failed: {e}")
            return []

    def get_top_keywords(self, limit: int = 20, company: Optional[str] = None) -> List[tuple]:
        """
        Extract top keywords from job titles and summaries.

        Args:
            limit: Maximum keywords to return
            company: Optional company filter

        Returns:
            List of (keyword, frequency) tuples sorted by frequency
        """
        if not self.conn:
            return []

        cursor = self.conn.cursor()

        try:
            # Get all titles and summaries
            if company:
                cursor.execute(
                    """SELECT title, summary FROM job_assessments WHERE company = ?""",
                    (company,),
                )
            else:
                cursor.execute("""SELECT title, summary FROM job_assessments""")

            text = " ".join(
                [
                    (row["title"] or "") + " " + (row["summary"] or "")
                    for row in cursor.fetchall()
                ]
            )

            if not text.strip():
                return []

            # Extract keywords: split by whitespace, filter short words, count
            keywords_freq: Dict[str, int] = {}
            for word in text.lower().split():
                # Remove punctuation and filter short words
                word = word.strip(".,;:!?()-").strip()
                if len(word) > 3 and word not in (
                    "and",
                    "the",
                    "for",
                    "with",
                    "from",
                    "this",
                    "that",
                ):
                    keywords_freq[word] = keywords_freq.get(word, 0) + 1

            # Sort by frequency, return top N
            sorted_keywords = sorted(
                keywords_freq.items(), key=lambda x: x[1], reverse=True
            )
            return sorted_keywords[:limit]
        except sqlite3.OperationalError:
            return []

    def get_recommendations_summary(self) -> Dict[str, int]:
        """
        Get aggregated recommendations with frequency counts.

        Returns:
            Dictionary mapping recommendations to count
        """
        if not self.conn:
            return {}

        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT recommendations FROM job_assessments WHERE recommendations IS NOT NULL"
        )

        recommendations_summary: Dict[str, int] = {}

        for row in cursor.fetchall():
            if row["recommendations"]:
                try:
                    recs = json.loads(row["recommendations"])
                    if isinstance(recs, list):
                        for rec in recs:
                            recommendations_summary[rec] = recommendations_summary.get(rec, 0) + 1
                except (json.JSONDecodeError, TypeError):
                    pass

        # Sort by frequency
        return dict(
            sorted(
                recommendations_summary.items(),
                key=lambda x: x[1],
                reverse=True,
            )
        )

    def count_assessments(self) -> int:
        """Get total assessment count."""
        if not self.conn:
            return 0

        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM job_assessments")
        result = cursor.fetchone()
        return int(result["count"]) if result else 0

    def delete_assessment(self, job_id: str) -> None:
        """Delete assessment by job ID."""
        if not self.conn:
            return

        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM job_assessments WHERE job_id = ?", (job_id,))
        cursor.execute(
            "DELETE FROM job_assessments_fts WHERE job_id = ?",
            (job_id,),
        )
        self.conn.commit()
        logger.debug(f"Deleted assessment for job {job_id}")

    def get_companies(self) -> List[str]:
        """Get list of distinct companies with assessments."""
        if not self.conn:
            return []

        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT company FROM job_assessments WHERE company IS NOT NULL ORDER BY company")
        return [row["company"] for row in cursor.fetchall()]

    def get_company_summary(self) -> List[Dict[str, Any]]:
        """Get aggregated stats per company."""
        if not self.conn:
            return []

        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT
               company,
               COUNT(*) as count,
               ROUND(AVG(overall_score), 2) as avg_score,
               MAX(overall_score) as max_score,
               MIN(overall_score) as min_score,
               ROUND(SUM(actual_cost), 4) as total_cost
               FROM job_assessments
               WHERE company IS NOT NULL
               GROUP BY company
               ORDER BY count DESC"""
        )

        results = []
        for row in cursor.fetchall():
            results.append(
                {
                    "company": row["company"],
                    "count": row["count"],
                    "avg_score": row["avg_score"],
                    "max_score": row["max_score"],
                    "min_score": row["min_score"],
                    "total_cost": row["total_cost"],
                }
            )

        return results

    def get_stats_by_company(self, company: str) -> Dict[str, Any]:
        """Get detailed statistics for a specific company."""
        if not self.conn:
            return {}

        cursor = self.conn.cursor()

        # Count by score range
        cursor.execute(
            """SELECT COUNT(*) as count FROM job_assessments
               WHERE company = ? AND overall_score >= 75""",
            (company,),
        )
        high_score = cursor.fetchone()["count"]

        cursor.execute(
            """SELECT COUNT(*) as count FROM job_assessments
               WHERE company = ? AND overall_score BETWEEN 50 AND 74""",
            (company,),
        )
        mid_score = cursor.fetchone()["count"]

        cursor.execute(
            """SELECT COUNT(*) as count FROM job_assessments
               WHERE company = ? AND overall_score < 50""",
            (company,),
        )
        low_score = cursor.fetchone()["count"]

        cursor.execute(
            """SELECT
               COUNT(*) as total,
               ROUND(AVG(overall_score), 2) as avg_score,
               ROUND(SUM(actual_cost), 4) as total_cost,
               SUM(tokens_used) as total_tokens
               FROM job_assessments WHERE company = ?""",
            (company,),
        )
        stats = dict(cursor.fetchone())

        return {
            "company": company,
            "total_assessments": stats["total"],
            "avg_score": stats["avg_score"],
            "total_cost": stats["total_cost"],
            "total_tokens": stats["total_tokens"],
            "score_distribution": {
                "high (75+)": high_score,
                "medium (50-74)": mid_score,
                "low (<50)": low_score,
            },
        }

    def purge_by_date(
        self,
        before_date: Optional[str] = None,
        after_date: Optional[str] = None,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """
        Purge assessments by date range.

        Args:
            before_date: Delete assessments before this date (YYYY-MM-DD)
            after_date: Delete assessments after this date (YYYY-MM-DD)
            dry_run: If True, don't actually delete (preview only)

        Returns:
            Dictionary with purge results:
                {
                    "count": int (records purged),
                    "dry_run": bool,
                    "before_date": str or None,
                    "after_date": str or None
                }
        """
        if not self.conn:
            return {"count": 0, "dry_run": dry_run, "before_date": before_date, "after_date": after_date}

        cursor = self.conn.cursor()

        # Build WHERE clause
        where_parts = []
        params = []

        if before_date:
            where_parts.append("assessed_date < ?")
            params.append(before_date)

        if after_date:
            where_parts.append("assessed_date > ?")
            params.append(after_date)

        if not where_parts:
            return {"count": 0, "dry_run": dry_run, "before_date": before_date, "after_date": after_date}

        where_clause = " AND ".join(where_parts)

        # Get affected records
        cursor.execute(f"SELECT COUNT(*) as count FROM job_assessments WHERE {where_clause}", params)
        affected_count = cursor.fetchone()["count"]

        if affected_count == 0:
            return {"count": 0, "dry_run": dry_run, "before_date": before_date, "after_date": after_date}

        # Only delete if not dry_run
        if not dry_run:
            cursor.execute(f"DELETE FROM job_assessments WHERE {where_clause}", params)
            cursor.execute(
                f"DELETE FROM job_assessments_fts WHERE job_id IN "
                f"(SELECT job_id FROM job_assessments WHERE {where_clause})",
                params,
            )
            self.conn.commit()
            logger.info(f"Purged {affected_count} assessments (before={before_date}, after={after_date})")

        return {
            "count": affected_count,
            "dry_run": dry_run,
            "before_date": before_date,
            "after_date": after_date,
        }

    def get_assessment_status(self, job_id: str) -> Optional[str]:
        """
        Get assessment status for a job: pending, confirmed, rejected, or assessed.

        Returns:
            Status string or None if job not found
        """
        if not self.conn:
            return None

        cursor = self.conn.cursor()

        # Check if assessed
        cursor.execute("SELECT COUNT(*) as count FROM job_assessments WHERE job_id = ?", (job_id,))
        if cursor.fetchone()["count"] > 0:
            return "assessed"

        # Check job status in job_reviews table if it exists
        try:
            cursor.execute("SELECT status FROM job_reviews WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            if row:
                status = row["status"]
                return str(status) if status else "pending"
        except sqlite3.OperationalError:
            pass

        return "pending"

    def get_jobs_needing_assessment(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get confirmed jobs that have not been assessed yet.

        Joins job_reviews (or jobs table) with assessments to find gaps.

        Args:
            limit: Maximum jobs to return

        Returns:
            List of jobs needing assessment
        """
        if not self.conn:
            return []

        cursor = self.conn.cursor()

        try:
            # Try joining with job_reviews table first
            cursor.execute(
                """SELECT jr.* FROM job_reviews jr
                   LEFT JOIN job_assessments ja ON jr.job_id = ja.job_id
                   WHERE jr.status = 'confirmed' AND ja.job_id IS NULL
                   ORDER BY jr.crawled_at DESC
                   LIMIT ?""",
                (limit,),
            )
        except sqlite3.OperationalError:
            # Fallback to jobs table if job_reviews doesn't exist
            try:
                cursor.execute(
                    """SELECT j.* FROM jobs j
                       LEFT JOIN job_assessments ja ON j.id = ja.job_id
                       WHERE j.status = 'confirmed' AND ja.job_id IS NULL
                       ORDER BY j.crawled_at DESC
                       LIMIT ?""",
                    (limit,),
                )
            except sqlite3.OperationalError:
                return []

        results = []
        for row in cursor.fetchall():
            results.append(dict(row))

        return results

    def get_jobs_by_score_threshold(
        self, min_score: float = 0, max_score: float = 100, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get assessments within score range.

        Args:
            min_score: Minimum score (0-100)
            max_score: Maximum score (0-100)
            limit: Maximum results

        Returns:
            List of assessments
        """
        if not self.conn:
            return []

        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT * FROM job_assessments
               WHERE overall_score >= ? AND overall_score <= ?
               ORDER BY overall_score DESC
               LIMIT ?""",
            (min_score, max_score, limit),
        )

        results = []
        for row in cursor.fetchall():
            result = dict(row)
            if result.get("recommendations"):
                result["recommendations"] = json.loads(result["recommendations"])
            results.append(result)

        return results

    def get_jobs_since(self, crawled_at_date: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get jobs crawled since a specific date.

        Args:
            crawled_at_date: Date string (YYYY-MM-DD or ISO format)
            limit: Maximum results

        Returns:
            List of job data with assessment status
        """
        if not self.conn:
            return []

        cursor = self.conn.cursor()

        try:
            # Try job_reviews table first
            cursor.execute(
                """SELECT jr.* FROM job_reviews jr
                   WHERE jr.crawled_at >= ?
                   ORDER BY jr.crawled_at DESC
                   LIMIT ?""",
                (crawled_at_date, limit),
            )
        except sqlite3.OperationalError:
            # Fallback to jobs table
            try:
                cursor.execute(
                    """SELECT j.* FROM jobs j
                       WHERE j.crawled_at >= ?
                       ORDER BY j.crawled_at DESC
                       LIMIT ?""",
                    (crawled_at_date, limit),
                )
            except sqlite3.OperationalError:
                return []

        results = []
        for row in cursor.fetchall():
            results.append(dict(row))

        return results

    def get_pipeline_stats(self) -> Dict[str, int]:
        """Get job counts by status.

        Returns:
            Dict with keys: pending_review, confirmed, rejected, assessed
        """
        if not self.conn:
            return {}

        cursor = self.conn.cursor()
        stats = {
            "pending_review": 0,
            "confirmed": 0,
            "rejected": 0,
            "assessed": 0,
        }

        try:
            # Try job_reviews table first (has status field)
            cursor.execute(
                "SELECT status, COUNT(*) as count FROM job_reviews GROUP BY status"
            )
            for row in cursor.fetchall():
                status = row["status"]
                count = row["count"]
                if status in stats:
                    stats[status] = count
        except sqlite3.OperationalError:
            logger.debug("job_reviews table not found, pipeline stats unavailable")
            return {}

        # Add count of assessed jobs
        try:
            cursor.execute("SELECT COUNT(*) as count FROM job_assessments")
            row = cursor.fetchone()
            if row:
                stats["assessed"] = row["count"]
        except sqlite3.OperationalError:
            pass

        return stats

    def _fetch_jobs_for_filter_stats(
        self, cursor: sqlite3.Cursor
    ) -> list:
        """Fetch jobs for filter stats, trying multiple query variants."""
        queries = [
            # Try job_reviews.crawled_at first (test fixture schema)
            """SELECT jr.job_id, jr.status, jr.crawled_at,
               CASE WHEN ja.job_id IS NOT NULL THEN 1 ELSE 0 END as is_assessed
               FROM job_reviews jr
               LEFT JOIN job_assessments ja ON jr.job_id = ja.job_id""",
            # Try jobs.crawled_at via join (production schema)
            """SELECT jr.job_id, jr.status, j.crawled_at,
               CASE WHEN ja.job_id IS NOT NULL THEN 1 ELSE 0 END as is_assessed
               FROM job_reviews jr
               LEFT JOIN job_assessments ja ON jr.job_id = ja.job_id
               LEFT JOIN jobs j ON jr.job_id = j.id""",
            # Fallback without crawled_at
            """SELECT jr.job_id, jr.status, NULL as crawled_at,
               CASE WHEN ja.job_id IS NOT NULL THEN 1 ELSE 0 END as is_assessed
               FROM job_reviews jr
               LEFT JOIN job_assessments ja ON jr.job_id = ja.job_id""",
        ]
        for query in queries:
            try:
                cursor.execute(query)
                return cursor.fetchall()
            except sqlite3.OperationalError:
                continue
        return []

    def _should_skip_job(
        self,
        status: str,
        is_assessed: int,
        crawled_at: Optional[str],
        skip_rejected: bool,
        skip_assessed: bool,
        skip_before_date: Optional[str],
    ) -> tuple[bool, Optional[str]]:
        """Determine if job should be skipped based on filters."""
        if skip_rejected and status == "rejected":
            return True, "rejected"
        if skip_assessed and is_assessed:
            return True, "already_assessed"
        if skip_before_date and crawled_at and crawled_at < skip_before_date:
            return True, "crawled_before_date"
        return False, None

    def get_stats_with_filters(
        self,
        skip_rejected: bool = True,
        skip_assessed: bool = True,
        skip_before_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get pipeline stats showing what would be skipped with filters."""
        if not self.conn:
            return {}

        cursor = self.conn.cursor()
        stats: Dict[str, Any] = {
            "total": 0,
            "would_process": 0,
            "would_skip": 0,
            "reasons": {"rejected": 0, "already_assessed": 0, "crawled_before_date": 0},
        }

        try:
            rows = self._fetch_jobs_for_filter_stats(cursor)
            if not rows:
                return {}

            stats["total"] = len(rows)
            for row in rows:
                should_skip, reason = self._should_skip_job(
                    row["status"],
                    row["is_assessed"],
                    row["crawled_at"],
                    skip_rejected,
                    skip_assessed,
                    skip_before_date,
                )
                if should_skip:
                    stats["would_skip"] += 1
                    if reason:
                        stats["reasons"][reason] += 1
                else:
                    stats["would_process"] += 1

        except sqlite3.OperationalError as e:
            logger.debug(f"Error computing filter stats: {e}")
            return {}

        return stats
