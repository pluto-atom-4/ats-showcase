"""Safe data purging with dry-run capability and transaction support."""

import logging
import sqlite3
from typing import List, Tuple, cast

from src.id_generation import generate_job_id
from src.storage.assessment_store import AssessmentStore

logger = logging.getLogger(__name__)


class DataPurger:
    """Safely delete invalid data with transactional guarantees."""

    def __init__(self, db_path: str = "data/ats_playground.db"):
        """Initialize purger with database path."""
        self.db_path = db_path
        self.store = AssessmentStore(db_path)
        self.conn: sqlite3.Connection = cast(sqlite3.Connection, self.store.conn)

    def purge_orphaned_assessments(
        self, dry_run: bool = True
    ) -> Tuple[int, List[str]]:
        """Delete assessments with job_id not in jobs table."""
        try:
            cursor = self.conn.cursor()

            # Find orphaned records
            query = """
                SELECT a.job_id
                FROM job_assessments a
                LEFT JOIN jobs j ON a.job_id = j.id
                WHERE j.id IS NULL
            """
            cursor.execute(query)
            orphaned = [row[0] for row in cursor.fetchall()]

            if not orphaned:
                logger.info("No orphaned assessments found")
                return 0, []

            if dry_run:
                logger.info(f"[DRY RUN] Would delete {len(orphaned)} orphaned assessments")
                return len(orphaned), orphaned

            # Actual deletion with transaction
            self.conn.execute("BEGIN TRANSACTION")
            try:
                cursor.execute(
                    "DELETE FROM job_assessments WHERE job_id IN ({})".format(
                        ",".join("?" * len(orphaned))
                    ),
                    orphaned,
                )
                self.conn.commit()
                logger.info(f"Deleted {len(orphaned)} orphaned assessments")
                return len(orphaned), orphaned
            except Exception as e:
                self.conn.rollback()
                logger.error(f"Error deleting orphaned assessments: {e}")
                raise
        except Exception as e:
            logger.error(f"Error purging orphaned assessments: {e}")
            return 0, []

    def purge_orphaned_preprocessed(
        self, dry_run: bool = True
    ) -> Tuple[int, List[str]]:
        """Delete preprocessed_jobs with job_id not in jobs table."""
        try:
            cursor = self.conn.cursor()

            query = """
                SELECT p.job_id
                FROM preprocessed_jobs p
                LEFT JOIN jobs j ON p.job_id = j.id
                WHERE j.id IS NULL
            """
            cursor.execute(query)
            orphaned = [row[0] for row in cursor.fetchall()]

            if not orphaned:
                logger.info("No orphaned preprocessed records found")
                return 0, []

            if dry_run:
                logger.info(f"[DRY RUN] Would delete {len(orphaned)} orphaned preprocessed records")
                return len(orphaned), orphaned

            self.conn.execute("BEGIN TRANSACTION")
            try:
                cursor.execute(
                    "DELETE FROM preprocessed_jobs WHERE job_id IN ({})".format(
                        ",".join("?" * len(orphaned))
                    ),
                    orphaned,
                )
                self.conn.commit()
                logger.info(f"Deleted {len(orphaned)} orphaned preprocessed records")
                return len(orphaned), orphaned
            except Exception as e:
                self.conn.rollback()
                logger.error(f"Error deleting orphaned preprocessed: {e}")
                raise
        except Exception as e:
            logger.error(f"Error purging orphaned preprocessed: {e}")
            return 0, []

    def purge_malformed_recommendations(
        self, dry_run: bool = True
    ) -> Tuple[int, List[str]]:
        """Set recommendations to NULL for records with invalid JSON."""
        import json

        try:
            cursor = self.conn.cursor()

            query = """
                SELECT job_id, recommendations
                FROM job_assessments
                WHERE recommendations IS NOT NULL
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            malformed_ids = []
            for job_id, recommendations in rows:
                if isinstance(recommendations, str):
                    try:
                        json.loads(recommendations)
                    except (json.JSONDecodeError, ValueError):
                        malformed_ids.append(job_id)

            if not malformed_ids:
                logger.info("No malformed recommendations found")
                return 0, []

            if dry_run:
                logger.info(
                    f"[DRY RUN] Would set {len(malformed_ids)} malformed recommendations to NULL"
                )
                return len(malformed_ids), malformed_ids

            self.conn.execute("BEGIN TRANSACTION")
            try:
                cursor.execute(
                    "UPDATE job_assessments SET recommendations = NULL WHERE job_id IN ({})".format(
                        ",".join("?" * len(malformed_ids))
                    ),
                    malformed_ids,
                )
                self.conn.commit()
                logger.info(f"Set {len(malformed_ids)} malformed recommendations to NULL")
                return len(malformed_ids), malformed_ids
            except Exception as e:
                self.conn.rollback()
                logger.error(f"Error updating malformed recommendations: {e}")
                raise
        except Exception as e:
            logger.error(f"Error purging malformed recommendations: {e}")
            return 0, []

    def purge_invalid_scores(self, dry_run: bool = True) -> Tuple[int, List[str]]:
        """Delete assessments with scores outside [0, 100]."""
        try:
            cursor = self.conn.cursor()

            query = """
                SELECT job_id
                FROM job_assessments
                WHERE overall_score < 0 OR overall_score > 100
                   OR tech_score < 0 OR tech_score > 100
                   OR seniority_score < 0 OR seniority_score > 100
                   OR location_score < 0 OR location_score > 100
            """
            cursor.execute(query)
            invalid = [row[0] for row in cursor.fetchall()]

            if not invalid:
                logger.info("No invalid scores found")
                return 0, []

            if dry_run:
                logger.info(f"[DRY RUN] Would delete {len(invalid)} assessments with invalid scores")
                return len(invalid), invalid

            self.conn.execute("BEGIN TRANSACTION")
            try:
                cursor.execute(
                    "DELETE FROM job_assessments WHERE job_id IN ({})".format(
                        ",".join("?" * len(invalid))
                    ),
                    invalid,
                )
                self.conn.commit()
                logger.info(f"Deleted {len(invalid)} assessments with invalid scores")
                return len(invalid), invalid
            except Exception as e:
                self.conn.rollback()
                logger.error(f"Error deleting invalid scores: {e}")
                raise
        except Exception as e:
            logger.error(f"Error purging invalid scores: {e}")
            return 0, []

    def purge_fts_orphans(self, dry_run: bool = True) -> Tuple[int, List[str]]:
        """Delete orphaned FTS5 entries and rebuild index."""
        try:
            cursor = self.conn.cursor()

            # Count orphaned FTS entries
            query = """
                SELECT COUNT(*)
                FROM job_assessments_fts f
                LEFT JOIN job_assessments a ON f.rowid = a.rowid
                WHERE a.rowid IS NULL
            """
            cursor.execute(query)
            orphan_count = cursor.fetchone()[0]

            if orphan_count == 0:
                logger.info("No FTS orphans found")
                return 0, []

            if dry_run:
                logger.info(
                    f"[DRY RUN] Would delete {orphan_count} orphaned FTS entries "
                    f"and rebuild index"
                )
                return orphan_count, []

            self.conn.execute("BEGIN TRANSACTION")
            try:
                # Delete orphaned FTS entries
                cursor.execute(
                    """
                    DELETE FROM job_assessments_fts
                    WHERE rowid NOT IN (SELECT rowid FROM job_assessments)
                    """
                )
                deleted_count = cursor.rowcount

                # Rebuild FTS index to optimize
                cursor.execute("REINDEX job_assessments_fts")

                self.conn.commit()

                # Vacuum to reclaim space (must be outside transaction)
                self.conn.execute("VACUUM")

                logger.info(
                    f"Deleted {deleted_count} orphaned FTS entries and rebuilt index"
                )
                return deleted_count, []
            except Exception as e:
                self.conn.rollback()
                logger.error(f"Error purging FTS orphans: {e}")
                raise
        except Exception as e:
            logger.error(f"Error purging FTS orphans: {e}")
            return 0, []

    def cascade_delete_job(
        self, job_id: str, dry_run: bool = True
    ) -> Tuple[int, List[str]]:
        """Delete job and all related records (assessments, preprocessed, cost_tracking, reviews)."""
        try:
            cursor = self.conn.cursor()

            # Verify job exists
            cursor.execute("SELECT id FROM jobs WHERE id = ?", (job_id,))
            if not cursor.fetchone():
                logger.warning(f"Job {job_id} does not exist")
                return 0, []

            if dry_run:
                # Count affected records
                cursor.execute("SELECT COUNT(*) FROM job_assessments WHERE job_id = ?", (job_id,))
                assessments = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM preprocessed_jobs WHERE job_id = ?", (job_id,))
                preprocessed = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM cost_tracking WHERE job_id = ?", (job_id,))
                cost = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM job_reviews WHERE job_id = ?", (job_id,))
                reviews = cursor.fetchone()[0]

                total = 1 + assessments + preprocessed + cost + reviews
                logger.info(
                    f"[DRY RUN] Would delete {total} records (1 job + {assessments} assessments + "
                    f"{preprocessed} preprocessed + {cost} cost_tracking + {reviews} reviews)"
                )
                return total, [job_id]

            self.conn.execute("BEGIN TRANSACTION")
            try:
                # Delete in order of foreign key dependencies and count
                total = 0
                cursor.execute("DELETE FROM job_assessments WHERE job_id = ?", (job_id,))
                total += cursor.rowcount
                cursor.execute("DELETE FROM preprocessed_jobs WHERE job_id = ?", (job_id,))
                total += cursor.rowcount
                cursor.execute("DELETE FROM cost_tracking WHERE job_id = ?", (job_id,))
                total += cursor.rowcount
                cursor.execute("DELETE FROM job_reviews WHERE job_id = ?", (job_id,))
                total += cursor.rowcount
                cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
                total += cursor.rowcount

                self.conn.commit()
                logger.info(f"Cascade deleted job {job_id} and all related records ({total} records total)")
                return total, [job_id]
            except Exception as e:
                self.conn.rollback()
                logger.error(f"Error cascade deleting job {job_id}: {e}")
                raise
        except Exception as e:
            logger.error(f"Error in cascade_delete_job: {e}")
            return 0, []

    def purge_by_date_range(
        self, start_date: str, end_date: str, dry_run: bool = True
    ) -> Tuple[int, List[str]]:
        """Delete assessments created within date range."""
        try:
            cursor = self.conn.cursor()

            query = """
                SELECT job_id
                FROM job_assessments
                WHERE assessed_date >= ? AND assessed_date <= ?
            """
            cursor.execute(query, (start_date, end_date))
            matching = [row[0] for row in cursor.fetchall()]

            if not matching:
                logger.info(f"No assessments found between {start_date} and {end_date}")
                return 0, []

            if dry_run:
                logger.info(
                    f"[DRY RUN] Would delete {len(matching)} assessments between {start_date} and {end_date}"
                )
                return len(matching), matching

            self.conn.execute("BEGIN TRANSACTION")
            try:
                cursor.execute(
                    "DELETE FROM job_assessments WHERE assessed_date >= ? AND assessed_date <= ?",
                    (start_date, end_date),
                )
                self.conn.commit()
                logger.info(f"Deleted {len(matching)} assessments between {start_date} and {end_date}")
                return len(matching), matching
            except Exception as e:
                self.conn.rollback()
                logger.error(f"Error deleting by date range: {e}")
                raise
        except Exception as e:
            logger.error(f"Error purging by date range: {e}")
            return 0, []

    def purge_orphaned_job_reviews(self, dry_run: bool = True) -> Tuple[int, List[str]]:
        """Delete orphaned job_reviews records (NULL job_id or non-existent job_id)."""
        try:
            cursor = self.conn.cursor()

            # Check if job_reviews table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='job_reviews'"
            )
            if not cursor.fetchone():
                logger.info("job_reviews table not found, nothing to purge")
                return 0, []

            # Find orphaned records
            query = """
                SELECT job_id FROM job_reviews
                WHERE job_id IS NULL
                   OR job_id NOT IN (SELECT DISTINCT job_id FROM job_assessments)
            """
            cursor.execute(query)
            orphaned = [row[0] for row in cursor.fetchall()]

            if not orphaned:
                logger.info("No orphaned job_reviews found")
                return 0, []

            if dry_run:
                logger.info(
                    f"[DRY RUN] Would delete {len(orphaned)} orphaned job_reviews"
                )
                return len(orphaned), orphaned

            self.conn.execute("BEGIN TRANSACTION")
            try:
                cursor.execute(
                    "DELETE FROM job_reviews WHERE job_id IS NULL OR job_id NOT IN "
                    "(SELECT DISTINCT job_id FROM job_assessments)"
                )
                self.conn.commit()
                logger.info(f"Deleted {len(orphaned)} orphaned job_reviews")
                return len(orphaned), orphaned
            except Exception as e:
                self.conn.rollback()
                logger.error(f"Error deleting orphaned job_reviews: {e}")
                raise
        except Exception as e:
            logger.error(f"Error purging orphaned job_reviews: {e}")
            return 0, []

    def rebuild_fts_index(self, dry_run: bool = True) -> Tuple[int, List[str]]:
        """Rebuild FTS5 index to refresh indexed content from main table.

        Deletes all FTS entries and repopulates from job_assessments.
        """
        try:
            cursor = self.conn.cursor()

            # Count current entries
            cursor.execute("SELECT COUNT(*) FROM job_assessments")
            total_count = cursor.fetchone()[0]

            if dry_run:
                logger.info(f"[DRY RUN] Would rebuild FTS5 index for {total_count} entries")
                return total_count, []

            self.conn.execute("BEGIN TRANSACTION")
            try:
                # Delete all FTS entries
                cursor.execute("DELETE FROM job_assessments_fts")

                # Re-populate from main table
                cursor.execute(
                    """
                    INSERT INTO job_assessments_fts
                    (rowid, job_id, title, company, summary, recommendations)
                    SELECT rowid, job_id, title, company, summary, recommendations
                    FROM job_assessments
                    """
                )

                # Optimize FTS index
                cursor.execute("REINDEX job_assessments_fts")

                self.conn.commit()
                logger.info(f"Rebuilt FTS5 index for {total_count} entries")
                return total_count, []
            except Exception as e:
                self.conn.rollback()
                logger.error(f"Error rebuilding FTS index: {e}")
                raise
        except Exception as e:
            logger.error(f"Error in rebuild_fts_index: {e}")
            return 0, []

    def regenerate_null_job_ids(self, dry_run: bool = True) -> Tuple[int, List[str]]:
        """Regenerate job_id for assessments with NULL job_id using title/company/location.

        First removes duplicate assessments (keeping first/best), then regenerates job_ids.
        """
        try:
            cursor = self.conn.cursor()

            # Find assessments with NULL job_id
            query = """
                SELECT rowid, title, company, location
                FROM job_assessments
                WHERE job_id IS NULL
                ORDER BY rowid
            """
            cursor.execute(query)
            null_records = cursor.fetchall()

            if not null_records:
                logger.info("No assessments with NULL job_id found")
                return 0, []

            # Group by title/company/location to find duplicates
            seen_jobs = {}  # (title, company, location) -> rowid
            duplicates = []
            for rowid, title, company, location in null_records:
                key = (title, company, location)
                if key in seen_jobs:
                    duplicates.append(rowid)
                else:
                    seen_jobs[key] = rowid

            if dry_run:
                logger.info(
                    f"[DRY RUN] Would delete {len(duplicates)} duplicate assessments "
                    f"and regenerate job_id for {len(seen_jobs)} unique assessments"
                )
                return len(null_records), []

            self.conn.execute("BEGIN TRANSACTION")
            try:
                updated_count = 0

                # First, delete duplicate assessments
                if duplicates:
                    cursor.execute(
                        "DELETE FROM job_assessments WHERE rowid IN ({})".format(
                            ",".join("?" * len(duplicates))
                        ),
                        duplicates,
                    )
                    logger.info(f"Deleted {len(duplicates)} duplicate assessments")

                # Then, regenerate job_id for unique assessments
                for (title, company, location), rowid in seen_jobs.items():
                    new_job_id = generate_job_id(
                        company=company or "Unknown",
                        title=title or "Unknown",
                        location=location or "Not specified",
                        url=None,
                    )
                    cursor.execute(
                        "UPDATE job_assessments SET job_id = ? WHERE rowid = ?",
                        (new_job_id, rowid),
                    )
                    updated_count += cursor.rowcount

                self.conn.commit()
                logger.info(
                    f"Deleted {len(duplicates)} duplicates and regenerated job_id for {updated_count} assessments"
                )
                return len(null_records), []
            except Exception as e:
                self.conn.rollback()
                logger.error(f"Error regenerating job_ids: {e}")
                raise
        except Exception as e:
            logger.error(f"Error in regenerate_null_job_ids: {e}")
            return 0, []
