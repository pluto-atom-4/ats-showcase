"""Shared database initialization helpers for storage modules."""

import logging
import sqlite3
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


def initialize_db_common(
    db_path: str,
    tables_dict: Dict[str, str],
) -> sqlite3.Connection:
    """Initialize database connection with common setup for all stores.

    This helper consolidates the initialization pattern used by JobStore
    and AssessmentStore to avoid duplication.

    Args:
        db_path: Path to SQLite database file
        tables_dict: Dictionary mapping table names to SQL CREATE statements.
                    Example: {"jobs": "CREATE TABLE IF NOT EXISTS...", ...}

    Returns:
        Initialized sqlite3.Connection with row_factory set

    Raises:
        sqlite3.OperationalError: If table creation fails
    """
    # Create parent directory if needed
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # Connect to database
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Execute all table creation statements
    cursor = conn.cursor()
    for table_name, sql in tables_dict.items():
        try:
            cursor.execute(sql)
            logger.debug(f"Created or verified table: {table_name}")
        except sqlite3.OperationalError as e:
            logger.error(f"Failed to create table {table_name}: {e}")
            raise

    conn.commit()
    logger.info(f"Initialized database at {db_path} with {len(tables_dict)} table(s)")

    return conn
