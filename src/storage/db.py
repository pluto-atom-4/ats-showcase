"""SQLite database initialization and schema."""

import logging
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class Database:
    """SQLite database manager for ATS Showcase."""

    def __init__(self, db_path: str = "data/ats_playground.db"):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        """Connect to database, creating if needed."""
        # TODO: Implement connection with proper config
        logger.info(f"Connecting to database: {self.db_path}")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def initialize_schema(self) -> None:
        """Create all tables if they don't exist."""
        # TODO: Implement schema creation
        logger.info("Initializing database schema")
        self._create_tables()

    def _create_tables(self) -> None:
        """Create all necessary tables."""
        # TODO: Implement table creation from SQL schema
        # Tables needed:
        # - jobs (job postings)
        # - preprocessed_jobs (cleaned/chunked versions)
        # - assessments (CV match results)
        # - cost_tracking (token and cost logs)
        pass

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def get_cursor(self) -> sqlite3.Cursor:
        """Get database cursor."""
        if not self.conn:
            self.connect()
        assert self.conn is not None, "Database connection failed"
        return self.conn.cursor()

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """
        Execute query with parameters.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Cursor with results
        """
        cursor = self.get_cursor()
        cursor.execute(query, params)
        assert self.conn is not None, "Database connection failed"
        self.conn.commit()
        return cursor


# Schema definitions as SQL strings
SCHEMA = {
    "jobs": """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT,
            url TEXT,
            description TEXT NOT NULL,
            requirements TEXT,
            salary_min REAL,
            salary_max REAL,
            posted_date DATETIME,
            crawled_at DATETIME NOT NULL,
            status TEXT DEFAULT 'pending_review',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(url)
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_jobs_crawled_at ON jobs(crawled_at DESC);
    """,
    "preprocessed_jobs": """
        CREATE TABLE IF NOT EXISTS preprocessed_jobs (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL UNIQUE,
            clean_text TEXT NOT NULL,
            chunks TEXT NOT NULL,
            token_count INTEGER NOT NULL,
            estimated_cost REAL NOT NULL,
            processed_date DATETIME NOT NULL,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        );
    """,
    "assessments": """
        CREATE TABLE IF NOT EXISTS assessments (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL UNIQUE,
            overall_score REAL NOT NULL,
            tech_score REAL NOT NULL,
            seniority_score REAL NOT NULL,
            location_score REAL NOT NULL,
            recommendations TEXT,
            summary TEXT,
            tokens_used INTEGER,
            actual_cost REAL,
            assessed_date DATETIME NOT NULL,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        );
        CREATE INDEX IF NOT EXISTS idx_assessments_score ON assessments(overall_score);
    """,
    "cost_tracking": """
        CREATE TABLE IF NOT EXISTS cost_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            phase TEXT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cost REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        );
        CREATE INDEX IF NOT EXISTS idx_cost_phase ON cost_tracking(phase);
    """,
}
