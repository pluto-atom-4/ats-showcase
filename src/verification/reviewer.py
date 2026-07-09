"""Job verification and review module for ATS Showcase.

This module provides interactive job review capabilities, allowing users to
confirm, reject, or skip jobs before expensive LLM API calls in Phase 4.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import typer

logger = logging.getLogger(__name__)


class ReviewStats:
    """Track review statistics."""

    def __init__(self):
        """Initialize stats."""
        self.total = 0
        self.confirmed = 0
        self.rejected = 0
        self.skipped = 0
        self.rejection_reasons: Dict[str, int] = {}
        self.total_tokens = 0
        self.total_cost = 0.0

    def add_confirmed(self, tokens: int, cost: float) -> None:
        """Record confirmed job."""
        self.confirmed += 1
        self.total_tokens += tokens
        self.total_cost += cost

    def add_rejected(self, reason: str) -> None:
        """Record rejected job."""
        self.rejected += 1
        self.rejection_reasons[reason] = self.rejection_reasons.get(reason, 0) + 1

    def add_skipped(self) -> None:
        """Record skipped job."""
        self.skipped += 1

    def get_summary(self) -> str:
        """Get formatted summary."""
        return f"""
📊 Review Summary:
   Total reviewed:  {self.total}
   Confirmed:       {self.confirmed} ({100*self.confirmed//max(1,self.total)}%)
   Rejected:        {self.rejected} ({100*self.rejected//max(1,self.total)}%)
   Skipped:         {self.skipped}

   Ready for Phase 4 Assessment:
     • Jobs: {self.confirmed}
     • Est. LLM cost: ${self.total_cost:.6f}
     • Avg tokens/job: {self.total_tokens//max(1,self.confirmed)}
"""


class JobReviewer:
    """Interactive CLI for reviewing and confirming extracted jobs before LLM assessment."""

    REVIEW_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS job_reviews (
        job_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        location TEXT,
        company TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        reason TEXT,
        tokens INTEGER,
        estimated_cost REAL,
        crawled_at TIMESTAMP,
        preprocessed_at TIMESTAMP,
        reviewed_at TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs(id)
    )
    """

    REVIEW_AUDIT_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS review_audit (
        audit_id TEXT PRIMARY KEY,
        job_id TEXT NOT NULL,
        prior_status TEXT,
        new_status TEXT NOT NULL,
        prior_reviewed_at TIMESTAMP,
        reviewed_at TIMESTAMP,
        re_review_reason TEXT,
        FOREIGN KEY (job_id) REFERENCES job_reviews(job_id)
    )
    """

    def __init__(self, db_path: str = "data/ats_playground.db"):
        """Initialize job reviewer with database."""
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._initialize_db()

    def _initialize_db(self) -> None:
        """Initialize database and schema."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        cursor = self.conn.cursor()
        cursor.execute(self.REVIEW_TABLE_SQL)
        cursor.execute(self.REVIEW_AUDIT_TABLE_SQL)
        self.conn.commit()
        logger.info("Initialized review database")
        self._run_migrations()

    def _run_migrations(self) -> None:
        """Run schema migrations to add missing columns."""
        if not self.conn:
            return
        cursor = self.conn.cursor()

        # Add crawled_at column if missing
        try:
            cursor.execute("ALTER TABLE job_reviews ADD COLUMN crawled_at TIMESTAMP")
            self.conn.commit()
            logger.info("Added crawled_at column to job_reviews")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Add preprocessed_at column if missing
        try:
            cursor.execute("ALTER TABLE job_reviews ADD COLUMN preprocessed_at TIMESTAMP")
            self.conn.commit()
            logger.info("Added preprocessed_at column to job_reviews")
        except sqlite3.OperationalError:
            pass  # Column already exists

    def _close_db(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def get_review_status(self, job_id: str) -> Optional[str]:
        """Get existing review status for a job."""
        if not self.conn:
            return None
        cursor = self.conn.cursor()
        cursor.execute("SELECT status FROM job_reviews WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        return row["status"] if row else None

    def save_review(
        self,
        job_id: str,
        title: str,
        location: Optional[str],
        status: str,
        reason: Optional[str] = None,
        tokens: int = 0,
        estimated_cost: float = 0.0,
        company: Optional[str] = None,
    ) -> None:
        """Save review decision to database."""
        if not self.conn:
            return
        cursor = self.conn.cursor()

        # Get existing row to preserve timeline fields
        cursor.execute(
            "SELECT crawled_at, preprocessed_at FROM job_reviews WHERE job_id = ?",
            (job_id,),
        )
        existing = cursor.fetchone()
        crawled_at = existing["crawled_at"] if existing else None
        preprocessed_at = existing["preprocessed_at"] if existing else None

        cursor.execute(
            """INSERT OR REPLACE INTO job_reviews
               (job_id, title, location, company, status, reason, tokens,
                estimated_cost, crawled_at, preprocessed_at, reviewed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job_id,
                title,
                location,
                company,
                status,
                reason,
                tokens,
                estimated_cost,
                crawled_at,
                preprocessed_at,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.conn.commit()
        logger.debug(f"Saved review: {job_id} -> {status}")

    def get_prior_review(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get prior review decision and timestamp."""
        if not self.conn:
            return None
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT status, reviewed_at FROM job_reviews WHERE job_id = ?", (job_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def save_re_review_audit(
        self,
        job_id: str,
        prior_status: str,
        new_status: str,
        prior_reviewed_at: str,
        re_review_reason: Optional[str] = None,
    ) -> None:
        """Track re-review decision in audit table."""
        if not self.conn:
            return
        cursor = self.conn.cursor()
        import uuid

        audit_id = str(uuid.uuid4())
        cursor.execute(
            """INSERT INTO review_audit
               (audit_id, job_id, prior_status, new_status, prior_reviewed_at, reviewed_at, re_review_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                audit_id,
                job_id,
                prior_status,
                new_status,
                prior_reviewed_at,
                datetime.now(timezone.utc).isoformat(),
                re_review_reason,
            ),
        )
        self.conn.commit()
        logger.debug(f"Saved re-review audit: {job_id} {prior_status} -> {new_status}")

    def set_preprocessed_at(self, job_id: str) -> None:
        """Record preprocessing timestamp for a job."""
        if not self.conn:
            return
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "UPDATE job_reviews SET preprocessed_at = ? WHERE job_id = ?",
                (datetime.now(timezone.utc).isoformat(), job_id),
            )
            self.conn.commit()
        except sqlite3.OperationalError:
            logger.warning(f"preprocessed_at column not found for job {job_id}")

    def set_crawled_at(self, job_id: str, crawled_at: Optional[str] = None) -> None:
        """Record or update crawled timestamp for a job."""
        if not self.conn:
            return
        cursor = self.conn.cursor()
        timestamp = crawled_at or datetime.now(timezone.utc).isoformat()
        try:
            cursor.execute(
                "UPDATE job_reviews SET crawled_at = ? WHERE job_id = ?",
                (timestamp, job_id),
            )
            self.conn.commit()
        except sqlite3.OperationalError:
            logger.warning(f"crawled_at column not found for job {job_id}")

    def get_job_timeline(self, job_id: str) -> Dict[str, Optional[str]]:
        """Get full job lifecycle timeline (crawled → preprocessed → reviewed → assessed)."""
        if not self.conn:
            return {
                "crawled_at": None,
                "preprocessed_at": None,
                "reviewed_at": None,
                "assessed_at": None,
            }
        cursor = self.conn.cursor()

        timeline: Dict[str, Optional[str]] = {
            "crawled_at": None,
            "preprocessed_at": None,
            "reviewed_at": None,
            "assessed_at": None,
        }

        # Get crawled_at and review timeline
        try:
            cursor.execute(
                "SELECT crawled_at, preprocessed_at, reviewed_at, status FROM job_reviews WHERE job_id = ?",
                (job_id,),
            )
            row = cursor.fetchone()
            if row:
                timeline["crawled_at"] = row["crawled_at"]
                timeline["preprocessed_at"] = row["preprocessed_at"]
                timeline["reviewed_at"] = row["reviewed_at"]
        except (sqlite3.OperationalError, KeyError):
            pass

        # Get assessed_at from assessments
        try:
            cursor.execute(
                "SELECT assessed_date FROM job_assessments WHERE job_id = ?",
                (job_id,),
            )
            row = cursor.fetchone()
            if row and row["assessed_date"]:
                timeline["assessed_at"] = row["assessed_date"]
        except sqlite3.OperationalError:
            pass

        return timeline

    def get_confirmed_jobs(self) -> List[Dict[str, Any]]:
        """Get all confirmed jobs from database."""
        if not self.conn:
            return []
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM job_reviews WHERE status = 'confirmed' ORDER BY reviewed_at")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def _check_review_status(
        self, job_id: str, skip_rejected: bool
    ) -> tuple[bool, Optional[str]]:
        """Check if job should be skipped based on review status."""
        cursor = self.conn.cursor()  # type: ignore
        cursor.execute("SELECT status FROM job_reviews WHERE job_id = ?", (job_id,))
        review_row = cursor.fetchone()
        if review_row:
            status = review_row["status"]
            if skip_rejected and status == "rejected":
                return True, "previously_rejected"
            if status == "confirmed":
                return True, "already_confirmed"
        return False, None

    def _check_assessment_status(self, job_id: str) -> tuple[bool, Optional[str]]:
        """Check if job should be skipped based on assessment status."""
        try:
            cursor = self.conn.cursor()  # type: ignore
            cursor.execute("SELECT COUNT(*) as count FROM job_assessments WHERE job_id = ?", (job_id,))
            if cursor.fetchone()["count"] > 0:
                return True, "already_assessed"
        except sqlite3.OperationalError:
            pass
        return False, None

    def _check_crawled_date(self, job_id: str, skip_before_date: str) -> tuple[bool, Optional[str]]:
        """Check if job should be skipped based on crawled_at date."""
        try:
            cursor = self.conn.cursor()  # type: ignore
            cursor.execute("SELECT crawled_at FROM jobs WHERE id = ?", (job_id,))
            job_row = cursor.fetchone()
            if job_row and job_row["crawled_at"]:
                crawled_at = str(job_row["crawled_at"])
                if crawled_at < skip_before_date:
                    return True, f"crawled_before_{skip_before_date}"
        except sqlite3.OperationalError:
            pass
        return False, None

    def should_skip_job(
        self,
        job_id: str,
        skip_before_date: Optional[str] = None,
        skip_rejected: bool = True,
        skip_assessed: bool = True,
    ) -> tuple[bool, Optional[str]]:
        """
        Determine if job should be skipped during review based on filtering rules.

        Args:
            job_id: Job to check
            skip_before_date: Skip jobs crawled before this date (ISO format)
            skip_rejected: Skip jobs with 'rejected' status
            skip_assessed: Skip jobs that have been assessed

        Returns:
            Tuple of (should_skip: bool, reason: Optional[str])
        """
        if not self.conn:
            return False, None

        # Check review status
        skip, reason = self._check_review_status(job_id, skip_rejected)
        if skip:
            return skip, reason

        # Check if assessed
        if skip_assessed:
            skip, reason = self._check_assessment_status(job_id)
            if skip:
                return skip, reason

        # Check crawled_at date
        if skip_before_date:
            skip, reason = self._check_crawled_date(job_id, skip_before_date)
            if skip:
                return skip, reason

        return False, None

    def review_job_interactive(
        self,
        job_idx: int,
        total_jobs: int,
        job: Dict[str, Any],
        preprocessed: Dict[str, Any],
        stats: ReviewStats,
        allow_re_review: bool = False,
    ) -> None:
        """
        Interactively review a single job posting.

        Args:
            job_idx: Current job index (0-based)
            total_jobs: Total number of jobs
            job: Job posting dict
            preprocessed: Preprocessed job data
            stats: ReviewStats to track decisions
            allow_re_review: Show prior decisions and allow re-review option
        """
        import typer

        job_id = job.get("id", f"job_{job_idx}")
        title = job.get("title", "Unknown")
        location = job.get("location", "Unknown")
        company = preprocessed.get("company")
        tokens = preprocessed.get("token_count", 0)
        cost = preprocessed.get("estimated_cost", 0.0)

        # Check if already reviewed
        existing_status = self.get_review_status(job_id)
        prior_review = None
        if existing_status and not allow_re_review:
            logger.debug(f"Job {job_id} already reviewed as {existing_status}, skipping")
            stats.add_skipped()
            return

        # If re-review allowed, check for prior decision
        if allow_re_review and existing_status:
            prior_review = self.get_prior_review(job_id)

        if not allow_re_review:
            stats.total += 1
        else:
            stats.total += 1

        self._display_job_details(
            job_idx, total_jobs, title, company, location, tokens, cost, preprocessed, prior_review
        )

        self._display_job_timeline(job_id)

        while True:
            prompt_text = "   Action (c=confirm/r=reject/s=skip/q=quit"
            if prior_review:
                prompt_text += "/e=re-review"
            prompt_text += "): "
            action = typer.prompt(prompt_text).strip().lower()

            if self._process_user_action(
                action, job_id, title, location, tokens, cost, company, prior_review, stats
            ):
                break

    def _save_re_review_if_changed(
        self,
        job_id: str,
        prior_review: Optional[Dict[str, Any]],
        new_status: str,
        re_review_reason: str,
    ) -> None:
        """Save re-review audit if status changed."""
        if prior_review:
            prior_status = prior_review.get("prior_status")
            prior_reviewed_at = prior_review.get("reviewed_at")
            if prior_status and prior_status != new_status:
                self.save_re_review_audit(
                    job_id,
                    prior_status=prior_status,
                    new_status=new_status,
                    prior_reviewed_at=prior_reviewed_at or "",
                    re_review_reason=re_review_reason,
                )

    def _handle_confirm_action(
        self,
        job_id: str,
        title: str,
        location: str,
        tokens: int,
        cost: float,
        company: Optional[str],
        prior_review: Optional[Dict[str, Any]],
        stats: "ReviewStats",
    ) -> None:
        """Handle confirm action."""
        self.save_review(
            job_id, title, location, status="confirmed", tokens=tokens, estimated_cost=cost, company=company
        )
        self._save_re_review_if_changed(
            job_id, prior_review, "confirmed", "User re-reviewed and changed decision"
        )
        stats.add_confirmed(tokens, cost)

    def _handle_reject_action(
        self,
        job_id: str,
        title: str,
        location: str,
        company: Optional[str],
        prior_review: Optional[Dict[str, Any]],
        stats: "ReviewStats",
    ) -> str:
        """Handle reject action and return reason."""
        reason_prompt = "   Rejection reason (tech/location/seniority/other): "
        reason: str = typer.prompt(reason_prompt).strip().lower()
        self.save_review(job_id, title, location, status="rejected", reason=reason, company=company)
        self._save_re_review_if_changed(
            job_id, prior_review, "rejected", f"User re-reviewed and rejected ({reason})"
        )
        stats.add_rejected(reason)
        return reason

    def _display_job_details(
        self,
        job_idx: int,
        total_jobs: int,
        title: str,
        company: Optional[str],
        location: str,
        tokens: int,
        cost: float,
        preprocessed: Dict[str, Any],
        prior_review: Optional[Dict[str, Any]],
    ) -> None:
        """Display job details for review."""
        typer.echo(f"\n🔍 Job {job_idx + 1} of {total_jobs}: {title}")
        if company:
            typer.echo(f"   Company: {company}")
        typer.echo(f"   Location: {location}")
        typer.echo(f"   Tokens: {tokens} | Cost: ${cost:.6f}")

        if prior_review:
            prior_status = prior_review.get("prior_status", "unknown")
            reviewed_at = prior_review.get("reviewed_at", "unknown")
            typer.echo(f"   [Prior: {prior_status} on {reviewed_at}]")

        content = preprocessed.get("clean_text", "")
        if content:
            preview = content.split("\n")[2:5]
            if preview:
                preview_text = " ".join(preview)[:80]
                typer.echo(f"   Content: {preview_text}...")

    def _format_timestamp(self, timestamp: Optional[str]) -> str:
        """Format timestamp for display, showing only date and time."""
        if not timestamp:
            return "not processed"
        try:
            # Handle ISO format timestamps (with or without timezone)
            if "T" in timestamp:
                dt_part = timestamp.split("T")[0]  # Get YYYY-MM-DD
                time_part = timestamp.split("T")[1].split("+")[0].split("Z")[0][:5]  # Get HH:MM
                return f"{dt_part} {time_part}"
            return timestamp[:16]  # Fallback: first 16 chars
        except Exception:
            return "invalid timestamp"

    def _display_job_timeline(self, job_id: str) -> None:
        """Display job lifecycle timeline before review."""
        timeline = self.get_job_timeline(job_id)
        if all(v is None for v in timeline.values()):
            return  # No timeline data to display

        typer.echo("\n   📅 Timeline:")
        crawled = self._format_timestamp(timeline.get("crawled_at"))
        preprocessed = self._format_timestamp(timeline.get("preprocessed_at"))
        reviewed = self._format_timestamp(timeline.get("reviewed_at"))
        assessed = self._format_timestamp(timeline.get("assessed_at"))

        typer.echo(f"      Crawled: {crawled}")
        typer.echo(f"      Preprocessed: {preprocessed}")
        typer.echo(f"      Reviewed: {reviewed}")
        typer.echo(f"      Assessed: {assessed}")

    def _process_user_action(
        self,
        action: str,
        job_id: str,
        title: str,
        location: str,
        tokens: int,
        cost: float,
        company: Optional[str],
        prior_review: Optional[Dict[str, Any]],
        stats: "ReviewStats",
    ) -> bool:
        """Process user action. Return True if action breaks loop, False to continue."""
        if action == "c":
            self._handle_confirm_action(
                job_id, title, location, tokens, cost, company, prior_review, stats
            )
            typer.echo(f"   ✓ Confirmed ({stats.confirmed}/{stats.total} confirmed)")
            return True
        elif action == "r":
            self._handle_reject_action(
                job_id, title, location, company, prior_review, stats
            )
            typer.echo("   ✗ Rejected")
            return True
        elif action == "s":
            stats.add_skipped()
            typer.echo("   ⊘ Skipped (will review later)")
            return True
        elif action == "q":
            typer.echo("\n⏹️  Review interrupted by user")
            raise typer.Exit(0)
        elif action == "e" and prior_review:
            typer.echo("   📝 Re-reviewing job...")
            return False
        else:
            msg = "   ❌ Invalid action. Use c/r/s/e/q" if prior_review else "   ❌ Invalid action. Use c/r/s/q"
            typer.echo(msg)
            return False

    def review_batch(
        self,
        extracted_files: Union[List[Path], str, Path],
        preprocessed_file: str,
        skip_before_date: Optional[str] = None,
        skip_rejected: bool = True,
        skip_assessed: bool = True,
        allow_re_review: bool = False,
    ) -> ReviewStats:
        """
        Review multiple jobs interactively with optional filtering.

        Args:
            extracted_files: Path(s) to extracted jobs JSON. Can be:
                - List of Path objects (multi-company)
                - Single Path or str (backward compat)
            preprocessed_file: Path to preprocessed jobs JSON
            skip_before_date: Skip jobs crawled before this date (ISO format, e.g. "2026-07-01")
            skip_rejected: Skip jobs with 'rejected' status (default True)
            skip_assessed: Skip jobs that have been assessed (default True)
            allow_re_review: Show prior decisions and allow re-review choice (default False)

        Returns:
            ReviewStats with final counts
        """
        import typer

        # Handle backward compat: convert single path to list
        if isinstance(extracted_files, (str, Path)):
            extracted_files = [Path(extracted_files)]
        else:
            extracted_files = [Path(f) if isinstance(f, str) else f for f in extracted_files]

        # Validate preprocessed file exists
        preprocessed_path = Path(preprocessed_file)
        if not preprocessed_path.exists():
            logger.error(f"Preprocessed jobs file not found: {preprocessed_file}")
            typer.echo(f"❌ File not found: {preprocessed_file}", err=True)
            raise typer.Exit(1)

        # Load preprocessed jobs
        with open(preprocessed_path) as f:
            preprocessed_jobs = json.load(f)

        # Map preprocessed by job_id
        preprocessed_map = {j["job_id"]: j for j in preprocessed_jobs}

        stats = ReviewStats()

        # Load and review all extracted files
        all_extracted_jobs = []
        for extracted_path in extracted_files:
            if not extracted_path.exists():
                logger.error(f"Extracted jobs file not found: {extracted_path}")
                typer.echo(f"❌ File not found: {extracted_path}", err=True)
                raise typer.Exit(1)

            with open(extracted_path) as f:
                extracted_jobs = json.load(f)
            all_extracted_jobs.append((extracted_path, extracted_jobs))

        total_jobs = sum(len(jobs) for _, jobs in all_extracted_jobs)
        typer.echo(f"\n👀 Starting job review ({total_jobs} jobs total)\n")

        job_counter = 0
        for extracted_path, extracted_jobs in all_extracted_jobs:
            source_name = extracted_path.stem  # e.g., "carbonrobotics_jobs"
            for idx, job in enumerate(extracted_jobs):
                # Use actual job ID from extracted job for lookup in preprocessed_map
                job_id = job.get("id", f"{source_name}_{idx + 1}")
                preprocessed = preprocessed_map.get(job_id, {})

                # Phase 3: Check if job should be skipped based on filters
                should_skip, skip_reason = self.should_skip_job(
                    job_id,
                    skip_before_date=skip_before_date,
                    skip_rejected=skip_rejected,
                    skip_assessed=skip_assessed,
                )
                if should_skip:
                    stats.add_skipped()
                    logger.debug(f"Skipped job {job_id}: {skip_reason}")
                    continue

                try:
                    self.review_job_interactive(
                        job_counter, total_jobs, job, preprocessed, stats,
                        allow_re_review=allow_re_review
                    )
                except typer.Exit:
                    raise

                job_counter += 1

        # Display summary
        typer.echo(stats.get_summary())

        return stats

    def display_pipeline_stats(
        self,
        skip_before_date: Optional[str] = None,
        skip_rejected: bool = True,
        skip_assessed: bool = True,
    ) -> None:
        """Display pipeline statistics showing job counts by status and filter effects."""
        from src.storage.assessment_store import AssessmentStore

        store = AssessmentStore(self.db_path)

        # Get base pipeline stats
        stats = store.get_pipeline_stats()
        if not stats:
            typer.echo("⚠️  No pipeline statistics available (database tables not initialized)")
            return

        # Get filter impact stats
        filter_stats = store.get_stats_with_filters(
            skip_rejected=skip_rejected,
            skip_assessed=skip_assessed,
            skip_before_date=skip_before_date,
        )

        typer.echo("\n" + "=" * 80)
        typer.echo("📊 PIPELINE STATUS")
        typer.echo("=" * 80)

        total_jobs = (
            stats.get("pending_review", 0)
            + stats.get("confirmed", 0)
            + stats.get("rejected", 0)
        )
        typer.echo(f"\nTotal jobs:          {total_jobs}")
        typer.echo(f"  • Pending review:  {stats.get('pending_review', 0):<6} ← Ready for review")
        typer.echo(f"  • Confirmed:       {stats.get('confirmed', 0):<6} ← Ready for assessment")
        typer.echo(f"  • Rejected:        {stats.get('rejected', 0):<6} ← Will be skipped")
        typer.echo(f"  • Assessed:        {stats.get('assessed', 0):<6} ← Already processed")

        if filter_stats and filter_stats.get("total", 0) > 0:
            filters_msg = f"--skip-rejected={skip_rejected} --skip-assessed={skip_assessed}"
            if skip_before_date:
                filters_msg += f" --skip-before-date {skip_before_date}"
            typer.echo(f"\nApplying filters: {filters_msg}")

            typer.echo(f"  → Will process:  {filter_stats.get('would_process', 0)} jobs")
            typer.echo(f"  → Will skip:     {filter_stats.get('would_skip', 0)} jobs")

            reasons = filter_stats.get("reasons", {})
            if reasons and filter_stats.get("would_skip", 0) > 0:
                typer.echo("\nSkip breakdown:")
                if reasons.get("rejected", 0) > 0:
                    typer.echo(f"    • Rejected:       {reasons.get('rejected', 0)}")
                if reasons.get("already_assessed", 0) > 0:
                    typer.echo(f"    • Already assessed: {reasons.get('already_assessed', 0)}")
                if reasons.get("crawled_before_date", 0) > 0:
                    typer.echo(f"    • Crawled before date: {reasons.get('crawled_before_date', 0)}")

        typer.echo("=" * 80 + "\n")
