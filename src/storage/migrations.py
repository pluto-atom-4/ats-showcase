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

    cursor.execute("PRAGMA table_info(jobs)")
    columns = {row[1] for row in cursor.fetchall()}

    if "crawled_at" in columns:
        logger.info("Migration: crawled_at already exists in jobs table")
        return False

    if "crawled_date" not in columns:
        logger.warning("Migration: neither crawled_at nor crawled_date found in jobs table")
        return False

    try:
        cursor.execute("ALTER TABLE jobs ADD COLUMN crawled_at DATETIME")

        cursor.execute("UPDATE jobs SET crawled_at = crawled_date WHERE crawled_at IS NULL")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_crawled_at ON jobs(crawled_at DESC)")

        conn.commit()
        logger.info("Migration: successfully added crawled_at to jobs table")
        return True

    except sqlite3.OperationalError as e:
        logger.error(f"Migration failed: {e}")
        conn.rollback()
        return False


def migrate_cost_tracking_add_reprocessing_columns(conn: sqlite3.Connection) -> bool:
    """
    Migrate cost_tracking table: Add before/after columns for re-preprocessing tracking.

    Phase 3A: Extend cost_tracking with preprocessing version tracking and token delta metrics.

    New columns:
    - preprocessing_version_before: v1.0 or v2.0 before re-preprocess
    - preprocessing_version_after: v2.0 after re-preprocess
    - tokens_before: Token count before re-preprocessing
    - tokens_after: Token count after re-preprocessing
    - estimated_cost_before: Cost estimate before re-preprocessing
    - estimated_cost_after: Cost estimate after re-preprocessing
    - is_re_preprocessing: Boolean flag for re-preprocessing runs

    Args:
        conn: Database connection

    Returns:
        True if migration succeeded, False if already applied or error
    """
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(cost_tracking)")
    columns = {row[1] for row in cursor.fetchall()}

    if "is_re_preprocessing" in columns:
        logger.info("Migration: cost_tracking re-preprocessing columns already exist")
        return False

    try:
        cursor.execute("ALTER TABLE cost_tracking ADD COLUMN preprocessing_version_before TEXT")
        cursor.execute("ALTER TABLE cost_tracking ADD COLUMN preprocessing_version_after TEXT")
        cursor.execute("ALTER TABLE cost_tracking ADD COLUMN tokens_before INTEGER")
        cursor.execute("ALTER TABLE cost_tracking ADD COLUMN tokens_after INTEGER")
        cursor.execute("ALTER TABLE cost_tracking ADD COLUMN estimated_cost_before REAL")
        cursor.execute("ALTER TABLE cost_tracking ADD COLUMN estimated_cost_after REAL")
        cursor.execute("ALTER TABLE cost_tracking ADD COLUMN is_re_preprocessing BOOLEAN DEFAULT FALSE")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cost_reprocessing ON cost_tracking(is_re_preprocessing)")

        conn.commit()
        logger.info("Migration: successfully added re-preprocessing columns to cost_tracking")
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
    migrate_cost_tracking_add_reprocessing_columns(conn)
    logger.info("Migrations complete")
