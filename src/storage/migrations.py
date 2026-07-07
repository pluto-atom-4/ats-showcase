"""Database migrations for schema evolution."""

import logging
import sqlite3

logger = logging.getLogger(__name__)


def migrate_jobs_table_add_crawled_at(conn: sqlite3.Connection) -> bool:
    """
    Migrate jobs table: rename crawled_date to crawled_at.

    Handles existing databases by adding crawled_at column and copying data.
    Creates index for query performance.

    Args:
        conn: Database connection

    Returns:
        True if migration succeeded, False if already applied or error
    """
    cursor = conn.cursor()

    # Check if crawled_at already exists
    cursor.execute("PRAGMA table_info(jobs)")
    columns = {row[1] for row in cursor.fetchall()}

    if "crawled_at" in columns:
        logger.info("Migration: crawled_at already exists in jobs table")
        return False

    if "crawled_date" not in columns:
        logger.warning("Migration: neither crawled_at nor crawled_date found in jobs table")
        return False

    try:
        # Add crawled_at column (allow NULL temporarily)
        cursor.execute("ALTER TABLE jobs ADD COLUMN crawled_at DATETIME")

        # Copy data from crawled_date
        cursor.execute("UPDATE jobs SET crawled_at = crawled_date WHERE crawled_at IS NULL")

        # Create index on crawled_at for query performance
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_crawled_at ON jobs(crawled_at DESC)"
        )

        conn.commit()
        logger.info("Migration: successfully added crawled_at to jobs table")
        return True

    except sqlite3.OperationalError as e:
        logger.error(f"Migration failed: {e}")
        conn.rollback()
        return False


def run_migrations(conn: sqlite3.Connection) -> None:
    """
    Run all pending migrations.

    Args:
        conn: Database connection
    """
    logger.info("Running database migrations")
    migrate_jobs_table_add_crawled_at(conn)
    logger.info("Migrations complete")
