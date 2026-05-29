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
        self, min_score: float = 70, max_score: float = 100
    ) -> List[Dict[str, Any]]:
        """Get all assessments within score range."""
        if not self.conn:
            return []

        cursor = self.conn.cursor()
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
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Search assessments by keyword with score filtering.

        Args:
            keyword: Search term
            min_score: Minimum score filter
            max_score: Maximum score filter
            limit: Maximum results to return

        Returns:
            List of matching assessments
        """
        if not self.conn or not keyword:
            return []

        cursor = self.conn.cursor()

        try:
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

    def get_top_keywords(self, limit: int = 20) -> List[tuple]:
        """
        Get top keywords from job descriptions.

        Args:
            limit: Maximum keywords to return

        Returns:
            List of (keyword, frequency) tuples
        """
        if not self.conn:
            return []

        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """SELECT COUNT(*) as freq FROM job_assessments
                   GROUP BY title, company
                   ORDER BY freq DESC
                   LIMIT ?""",
                (limit,),
            )

            keywords = []
            for row in cursor.fetchall():
                keywords.append((row["freq"], row["freq"]))

            return keywords
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
