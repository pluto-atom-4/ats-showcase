"""Database integrity checking and anomaly detection."""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, cast

from src.integrity.models import IntegrityIssue, IntegrityReport
from src.storage.assessment_store import AssessmentStore

logger = logging.getLogger(__name__)


class IntegrityChecker:
    """Run comprehensive integrity checks on assessment database."""

    def __init__(self, db_path: str = "data/ats_playground.db"):
        """Initialize checker with database path."""
        self.db_path = db_path
        self.store = AssessmentStore(db_path)
        self.conn: sqlite3.Connection = cast(sqlite3.Connection, self.store.conn)
        self.issues: List[IntegrityIssue] = []

    def check_orphaned_assessments(self) -> List[IntegrityIssue]:
        """Find assessments with job_id not in jobs table."""
        issues = []
        try:
            cursor = self.conn.cursor()
            query = """
                SELECT a.job_id
                FROM job_assessments a
                LEFT JOIN jobs j ON a.job_id = j.id
                WHERE j.id IS NULL
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            for (job_id,) in rows:
                issues.append(
                    IntegrityIssue(
                        issue_type="orphaned_assessment",
                        severity="error",
                        table="job_assessments",
                        record_id=job_id,
                        details=f"Assessment exists but job_id '{job_id}' not in jobs table",
                        suggested_action="Delete orphaned assessment record",
                    )
                )
            logger.info(f"Found {len(issues)} orphaned assessments")
        except Exception as e:
            logger.error(f"Error checking orphaned assessments: {e}")

        return issues

    def check_orphaned_preprocessed(self) -> List[IntegrityIssue]:
        """Find preprocessed_jobs with job_id not in jobs table."""
        issues = []
        try:
            cursor = self.conn.cursor()
            query = """
                SELECT p.job_id
                FROM preprocessed_jobs p
                LEFT JOIN jobs j ON p.job_id = j.id
                WHERE j.id IS NULL
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            for (job_id,) in rows:
                issues.append(
                    IntegrityIssue(
                        issue_type="orphaned_preprocessed",
                        severity="error",
                        table="preprocessed_jobs",
                        record_id=job_id,
                        details=f"Preprocessed data exists but job_id '{job_id}' not in jobs table",
                        suggested_action="Delete orphaned preprocessed record",
                    )
                )
            logger.info(f"Found {len(issues)} orphaned preprocessed records")
        except Exception as e:
            logger.error(f"Error checking orphaned preprocessed: {e}")

        return issues

    def check_invalid_scores(self) -> List[IntegrityIssue]:
        """Find scores outside [0, 100] range."""
        issues = []
        try:
            cursor = self.conn.cursor()
            query = """
                SELECT job_id, overall_score, tech_score, seniority_score, location_score
                FROM job_assessments
                WHERE overall_score < 0 OR overall_score > 100
                   OR tech_score < 0 OR tech_score > 100
                   OR seniority_score < 0 OR seniority_score > 100
                   OR location_score < 0 OR location_score > 100
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            for job_id, overall, tech, seniority, location in rows:
                bad_scores = []
                if overall < 0 or overall > 100:
                    bad_scores.append(f"overall={overall}")
                if tech < 0 or tech > 100:
                    bad_scores.append(f"tech={tech}")
                if seniority < 0 or seniority > 100:
                    bad_scores.append(f"seniority={seniority}")
                if location < 0 or location > 100:
                    bad_scores.append(f"location={location}")

                issues.append(
                    IntegrityIssue(
                        issue_type="invalid_score",
                        severity="error",
                        table="job_assessments",
                        record_id=job_id,
                        details=f"Invalid scores: {', '.join(bad_scores)}",
                        suggested_action="Delete assessment with invalid scores",
                    )
                )
            logger.info(f"Found {len(issues)} assessments with invalid scores")
        except Exception as e:
            logger.error(f"Error checking invalid scores: {e}")

        return issues

    def check_malformed_recommendations(self) -> List[IntegrityIssue]:
        """Find recommendations that fail JSON parsing."""
        issues = []
        try:
            cursor = self.conn.cursor()
            query = """
                SELECT job_id, recommendations
                FROM job_assessments
                WHERE recommendations IS NOT NULL
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            for job_id, recommendations in rows:
                if isinstance(recommendations, str):
                    try:
                        json.loads(recommendations)
                    except (json.JSONDecodeError, ValueError):
                        issues.append(
                            IntegrityIssue(
                                issue_type="malformed_json",
                                severity="warning",
                                table="job_assessments",
                                record_id=job_id,
                                details="Recommendations field contains invalid JSON",
                                suggested_action="Set recommendations to NULL (soft delete)",
                            )
                        )
            logger.info(f"Found {len(issues)} assessments with malformed JSON")
        except Exception as e:
            logger.error(f"Error checking malformed recommendations: {e}")

        return issues

    def check_missing_preprocessing(self) -> List[IntegrityIssue]:
        """Find assessments without corresponding preprocessed_jobs record."""
        issues = []
        try:
            cursor = self.conn.cursor()
            query = """
                SELECT a.job_id
                FROM job_assessments a
                LEFT JOIN preprocessed_jobs p ON a.job_id = p.job_id
                WHERE p.job_id IS NULL
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            for (job_id,) in rows:
                issues.append(
                    IntegrityIssue(
                        issue_type="missing_preprocessing",
                        severity="warning",
                        table="preprocessed_jobs",
                        record_id=job_id,
                        details=f"Assessment exists but no preprocessing record for job_id '{job_id}'",
                        suggested_action="Review assessment scoring (preprocessed data should exist)",
                    )
                )
            logger.info(f"Found {len(issues)} assessments without preprocessing data")
        except Exception as e:
            logger.error(f"Error checking missing preprocessing: {e}")

        return issues

    def check_fts_orphans(self) -> List[IntegrityIssue]:
        """Find FTS entries not in main job_assessments table."""
        issues = []
        try:
            cursor = self.conn.cursor()
            query = """
                SELECT f.rowid
                FROM job_assessments_fts f
                LEFT JOIN job_assessments a ON f.rowid = a.rowid
                WHERE a.rowid IS NULL
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            if rows:
                issues.append(
                    IntegrityIssue(
                        issue_type="fts_orphan",
                        severity="info",
                        table="job_assessments_fts",
                        record_id=f"{len(rows)} orphaned entries",
                        details=f"Found {len(rows)} orphaned entries in FTS5 index",
                        suggested_action="Delete orphaned entries and rebuild FTS5 index",
                    )
                )
            logger.info(f"Found {len(rows)} orphaned FTS entries")
        except Exception as e:
            logger.error(f"Error checking FTS orphans: {e}")

        return issues

    def check_duplicate_assessments(self) -> List[IntegrityIssue]:
        """Find multiple assessments for the same job_id."""
        issues = []
        try:
            cursor = self.conn.cursor()
            query = """
                SELECT job_id, COUNT(*) as cnt
                FROM job_assessments
                GROUP BY job_id
                HAVING cnt > 1
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            for job_id, count in rows:
                issues.append(
                    IntegrityIssue(
                        issue_type="duplicate_assessment",
                        severity="error",
                        table="job_assessments",
                        record_id=job_id,
                        details=f"Multiple assessments ({count}) for same job_id (should be UNIQUE)",
                        suggested_action="Keep latest assessment, delete older duplicates",
                    )
                )
            logger.info(f"Found {len(issues)} duplicate assessment records")
        except Exception as e:
            logger.error(f"Error checking duplicate assessments: {e}")

        return issues

    def check_status_inconsistencies(self) -> List[IntegrityIssue]:
        """Find mismatched job.status vs job_reviews.status.

        NOTE: jobs table doesn't exist in current schema (job_assessments only).
        This check is deprecated. Kept for backward compatibility.
        """
        issues: List[IntegrityIssue] = []
        try:
            cursor = self.conn.cursor()
            # Check if jobs table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'")
            if not cursor.fetchone():
                logger.info("Skipping status inconsistency check (jobs table not found)")
                return issues

            query = """
                SELECT j.id, j.status, r.status
                FROM jobs j
                LEFT JOIN job_reviews r ON j.id = r.job_id
                WHERE r.status IS NOT NULL AND j.status != r.status
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            for job_id, job_status, review_status in rows:
                issues.append(
                    IntegrityIssue(
                        issue_type="status_inconsistency",
                        severity="warning",
                        table="job_reviews",
                        record_id=job_id,
                        details=(
                            f"Status mismatch: jobs.status='{job_status}' vs job_reviews.status='{review_status}'"
                        ),
                        suggested_action="Update job_reviews.status to match jobs.status",
                    )
                )
            logger.info(f"Found {len(issues)} status inconsistencies")
        except Exception as e:
            logger.error(f"Error checking status inconsistencies: {e}")

        return issues

    def check_job_reviews_anomalies(self) -> List[IntegrityIssue]:
        """Find orphaned or invalid job_reviews records.

        Checks for:
        - NULL job_ids (should reference job_assessments.job_id)
        - Reviews with job_id not in job_assessments
        """
        issues: List[IntegrityIssue] = []
        try:
            cursor = self.conn.cursor()

            # Check if job_reviews table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='job_reviews'")
            if not cursor.fetchone():
                logger.info("job_reviews table not found, skipping anomaly check")
                return issues

            # Check for NULL job_ids
            cursor.execute("SELECT COUNT(*) FROM job_reviews WHERE job_id IS NULL")
            null_count = cursor.fetchone()[0]

            if null_count > 0:
                issues.append(
                    IntegrityIssue(
                        issue_type="orphaned_job_review",
                        severity="error",
                        table="job_reviews",
                        record_id=f"{null_count} reviews with NULL job_id",
                        details=(
                            f"Found {null_count} job_reviews with NULL job_id (should reference job_assessments.job_id)"
                        ),
                        suggested_action=("Purge NULL job_reviews records or migrate to reference job_assessments"),
                    )
                )

            # Check for reviews referencing non-existent job_assessments
            cursor.execute(
                """
                SELECT COUNT(DISTINCT r.job_id)
                FROM job_reviews r
                WHERE r.job_id IS NOT NULL
                AND r.job_id NOT IN (SELECT DISTINCT job_id FROM job_assessments)
                """
            )
            orphan_count = cursor.fetchone()[0]

            if orphan_count > 0:
                issues.append(
                    IntegrityIssue(
                        issue_type="orphaned_job_review",
                        severity="error",
                        table="job_reviews",
                        record_id=f"{orphan_count} reviews with invalid job_id",
                        details=(f"Found {orphan_count} job_reviews with job_id not in job_assessments"),
                        suggested_action="Purge orphaned job_reviews records",
                    )
                )

            logger.info(f"Found {null_count} NULL and {orphan_count} orphaned job_reviews")
        except Exception as e:
            logger.error(f"Error checking job_reviews anomalies: {e}")

        return issues

    def check_missing_cost_tracking(self) -> List[IntegrityIssue]:
        """Find cost_tracking entries with job_id not in jobs table."""
        issues = []
        try:
            cursor = self.conn.cursor()
            query = """
                SELECT c.id, c.job_id
                FROM cost_tracking c
                LEFT JOIN jobs j ON c.job_id = j.id
                WHERE j.id IS NULL
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            for _cost_id, job_id in rows:
                issues.append(
                    IntegrityIssue(
                        issue_type="orphaned_cost_tracking",
                        severity="info",
                        table="cost_tracking",
                        record_id=job_id,
                        details=f"Cost tracking entry for non-existent job_id '{job_id}'",
                        suggested_action="Delete orphaned cost_tracking record",
                    )
                )
            logger.info(f"Found {len(issues)} orphaned cost_tracking entries")
        except Exception as e:
            logger.error(f"Error checking missing cost tracking: {e}")

        return issues

    def check_fts_data_consistency(self) -> List[IntegrityIssue]:
        """Find FTS entries with NULL or mismatched job_id values."""
        issues: List[IntegrityIssue] = []
        try:
            cursor = self.conn.cursor()
            # Check for NULL job_ids in FTS
            query = """
                SELECT COUNT(*)
                FROM job_assessments_fts
                WHERE job_id IS NULL
            """
            cursor.execute(query)
            null_count = cursor.fetchone()[0]

            if null_count > 0:
                issues.append(
                    IntegrityIssue(
                        issue_type="fts_data_mismatch",
                        severity="error",
                        table="job_assessments_fts",
                        record_id=f"{null_count} entries with NULL job_id",
                        details=(
                            f"Found {null_count} FTS entries with NULL job_id (FTS index out of sync with main table)"
                        ),
                        suggested_action=("Rebuild FTS5 index to refresh indexed content from main table"),
                    )
                )
            logger.info(f"Found {null_count} FTS entries with NULL job_id")
        except Exception as e:
            logger.error(f"Error checking FTS data consistency: {e}")

        return issues

    def check_null_job_ids(self) -> List[IntegrityIssue]:
        """Find assessments with NULL job_id."""
        issues: List[IntegrityIssue] = []
        try:
            cursor = self.conn.cursor()
            query = """
                SELECT COUNT(*)
                FROM job_assessments
                WHERE job_id IS NULL
            """
            cursor.execute(query)
            count = cursor.fetchone()[0]

            if count > 0:
                issues.append(
                    IntegrityIssue(
                        issue_type="null_job_id",
                        severity="error",
                        table="job_assessments",
                        record_id=f"{count} assessments with NULL job_id",
                        details=(
                            f"Found {count} assessments with NULL job_id "
                            "(should be generated from title/company/location)"
                        ),
                        suggested_action=(
                            "Regenerate job_id from assessment data or re-run preprocess with fixed ID generation"
                        ),
                    )
                )
            logger.info(f"Found {count} assessments with NULL job_id")
        except Exception as e:
            logger.error(f"Error checking NULL job_ids: {e}")

        return issues

    def run_full_check(self) -> IntegrityReport:
        """Execute all integrity checks and return aggregated report."""
        logger.info("Starting full integrity check")
        self.issues = []

        # Run all checks
        self.issues.extend(self.check_orphaned_assessments())
        self.issues.extend(self.check_orphaned_preprocessed())
        self.issues.extend(self.check_invalid_scores())
        self.issues.extend(self.check_malformed_recommendations())
        self.issues.extend(self.check_missing_preprocessing())
        self.issues.extend(self.check_fts_orphans())
        self.issues.extend(self.check_fts_data_consistency())
        self.issues.extend(self.check_duplicate_assessments())
        self.issues.extend(self.check_status_inconsistencies())
        self.issues.extend(self.check_missing_cost_tracking())
        self.issues.extend(self.check_null_job_ids())
        self.issues.extend(self.check_job_reviews_anomalies())

        # Aggregate results
        summary_by_type: dict[str, int] = {}
        for issue in self.issues:
            summary_by_type[issue.issue_type] = summary_by_type.get(issue.issue_type, 0) + 1

        affected_records = len({issue.record_id for issue in self.issues})

        report = IntegrityReport(
            timestamp=datetime.utcnow(),
            total_checks=12,
            issues_found=self.issues,
            summary_by_type=summary_by_type,
            total_records_affected=affected_records,
            purge_recommendations=self._get_purge_recommendations(),
        )

        logger.info(f"Integrity check complete: {len(self.issues)} issues found in {affected_records} records")
        return report

    def _get_purge_recommendations(self) -> List[str]:
        """Generate suggested purge actions based on issues found."""
        recommendations = []
        issue_types = {issue.issue_type for issue in self.issues}

        if "orphaned_assessment" in issue_types:
            recommendations.append("integrity purge --type orphaned_assessments (high priority)")
        if "orphaned_preprocessed" in issue_types:
            recommendations.append("integrity purge --type orphaned_preprocessed (high priority)")
        if "invalid_score" in issue_types:
            recommendations.append("integrity purge --type invalid_scores (high priority)")
        if "malformed_json" in issue_types:
            recommendations.append("integrity purge --type malformed_recommendations (soft delete)")
        if "fts_orphan" in issue_types:
            recommendations.append("integrity purge --type fts_orphans")
        if "fts_data_mismatch" in issue_types:
            recommendations.append("integrity purge --type fts_data_mismatch")
        if "null_job_id" in issue_types:
            recommendations.append("integrity purge --type null_job_ids or re-run preprocess")
        if "orphaned_job_review" in issue_types:
            recommendations.append("integrity purge --type orphaned_job_reviews")
        if "duplicate_assessment" in issue_types:
            recommendations.append("resolve_duplicate_assessments (manual review required)")

        return recommendations

    # ------------------------------------------------------------------
    # Duplicate inspection (issue #786): read-only, advisory only
    # ------------------------------------------------------------------

    _JOB_LIST_KEYS = ("jobs", "items", "results", "data")

    @classmethod
    def _extract_job_records(cls, payload: Any) -> List[Dict[str, Any]]:
        """Return dict rows from a job-list payload (list, or dict holding a job-list key).

        Non-job shapes return [] so the caller skips them silently.
        """
        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict):
            rows = next((payload[key] for key in cls._JOB_LIST_KEYS if isinstance(payload.get(key), list)), [])
        else:
            return []
        return [row for row in rows if isinstance(row, dict)]

    def scan_json_duplicate_ids(self, json_dir: str = "data/work", pattern: str = "*.json") -> List[IntegrityIssue]:
        """Flag ids that map to more than one distinct url within a single JSON file.

        Exact re-export duplicates (same id AND same url) are out of scope and emit nothing.
        """
        issues: List[IntegrityIssue] = []
        try:
            paths = sorted(Path(json_dir).glob(pattern))
        except (OSError, ValueError) as e:
            logger.error(f"Error listing JSON files in {json_dir}: {e}")
            return issues

        for path in paths:
            if not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError, OSError) as e:
                logger.warning(f"Skipping unreadable JSON file {path.name}: {e}")
                continue

            rows_by_id: Dict[str, List[str]] = {}
            for record in self._extract_job_records(payload):
                record_id = record.get("id")
                if not isinstance(record_id, str) or not record_id:
                    continue
                rows_by_id.setdefault(record_id, []).append(str(record.get("url")))

            for record_id in sorted(rows_by_id):
                row_urls = rows_by_id[record_id]
                distinct_urls = sorted(set(row_urls))
                if len(distinct_urls) <= 1:
                    continue
                issues.append(
                    IntegrityIssue(
                        issue_type="duplicate_id_json",
                        severity="warning",
                        table=path.name,
                        record_id=record_id,
                        details=(
                            f"{len(row_urls)} rows share id '{record_id}' across "
                            f"{len(distinct_urls)} distinct URLs: {distinct_urls}"
                        ),
                        suggested_action=(
                            "Manual review: re-crawl affected URLs to get distinct ids under the post-#774 anchor, "
                            "then purge stale rows."
                        ),
                    )
                )

        logger.info(f"Found {len(issues)} duplicate ids across JSON files in {json_dir}")
        return issues

    def scan_db_custom_portal_rows(self) -> List[IntegrityIssue]:
        """Report custom:% job_id rows: duplicates as warning, singles as advisory info.

        Missing tables are skipped; any error logs and returns [].
        """
        issues: List[IntegrityIssue] = []
        try:
            cursor = self.conn.cursor()
            for table in ("job_assessments", "job_reviews"):
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
                if not cursor.fetchone():
                    continue
                cursor.execute(
                    f"""
                    SELECT job_id, COUNT(*) AS cnt
                    FROM {table}
                    WHERE job_id LIKE 'custom:%'
                    GROUP BY job_id
                    """
                )
                for job_id, count in cursor.fetchall():
                    if count > 1:
                        issues.append(
                            IntegrityIssue(
                                issue_type="duplicate_id_db",
                                severity="warning",
                                table=table,
                                record_id=job_id,
                                details=f"{count} rows share custom job_id '{job_id}' in {table}",
                                suggested_action="Manual review: re-crawl affected URLs, then purge stale rows",
                            )
                        )
                    else:
                        issues.append(
                            IntegrityIssue(
                                issue_type="custom_portal_row",
                                severity="info",
                                table=table,
                                record_id=job_id,
                                details=f"Custom-portal job_id '{job_id}' present in {table}",
                                suggested_action="Advisory only: no action required",
                            )
                        )
            logger.info(f"Found {len(issues)} custom-portal DB issues")
        except Exception as e:
            logger.error(f"Error scanning custom-portal rows: {e}")
            return []

        return issues

    def run_duplicate_inspection(self, json_dir: str = "data/work", pattern: str = "*.json") -> IntegrityReport:
        """Run read-only duplicate inspection (JSON + DB) and return aggregated report."""
        logger.info("Starting duplicate inspection")
        self.issues = []
        self.issues.extend(self.scan_json_duplicate_ids(json_dir=json_dir, pattern=pattern))
        self.issues.extend(self.scan_db_custom_portal_rows())

        summary_by_type: dict[str, int] = {}
        for issue in self.issues:
            summary_by_type[issue.issue_type] = summary_by_type.get(issue.issue_type, 0) + 1

        affected_records = len({issue.record_id for issue in self.issues})

        return IntegrityReport(
            timestamp=datetime.utcnow(),
            total_checks=2,
            issues_found=self.issues,
            summary_by_type=summary_by_type,
            total_records_affected=affected_records,
            purge_recommendations=[],
        )
