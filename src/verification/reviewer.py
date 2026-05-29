"""Job verification and review module for ATS Playground.

This module provides interactive job review capabilities, allowing users to
confirm, reject, or skip jobs before expensive LLM API calls in Phase 4.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

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
        status TEXT NOT NULL DEFAULT 'pending',
        reason TEXT,
        tokens INTEGER,
        estimated_cost REAL,
        reviewed_at TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs(id)
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
        self.conn.commit()
        logger.info("Initialized review database")

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
    ) -> None:
        """Save review decision to database."""
        if not self.conn:
            return
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT OR REPLACE INTO job_reviews
               (job_id, title, location, status, reason, tokens, estimated_cost, reviewed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job_id,
                title,
                location,
                status,
                reason,
                tokens,
                estimated_cost,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.conn.commit()
        logger.debug(f"Saved review: {job_id} -> {status}")

    def get_confirmed_jobs(self) -> List[Dict[str, Any]]:
        """Get all confirmed jobs from database."""
        if not self.conn:
            return []
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM job_reviews WHERE status = 'confirmed' ORDER BY reviewed_at")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def review_job_interactive(
        self,
        job_idx: int,
        total_jobs: int,
        job: Dict[str, Any],
        preprocessed: Dict[str, Any],
        stats: ReviewStats,
    ) -> None:
        """
        Interactively review a single job posting.

        Args:
            job_idx: Current job index (0-based)
            total_jobs: Total number of jobs
            job: Job posting dict
            preprocessed: Preprocessed job data
            stats: ReviewStats to track decisions
        """
        import typer

        job_id = job.get("id", f"job_{job_idx}")
        title = job.get("title", "Unknown")
        location = job.get("location", "Unknown")
        tokens = preprocessed.get("token_count", 0)
        cost = preprocessed.get("estimated_cost", 0.0)

        # Check if already reviewed
        existing_status = self.get_review_status(job_id)
        if existing_status:
            logger.debug(f"Job {job_id} already reviewed as {existing_status}, skipping")
            stats.add_skipped()
            return

        stats.total += 1

        # Display job
        typer.echo(f"\n🔍 Job {job_idx + 1} of {total_jobs}: {title}")
        typer.echo(f"   Location: {location}")
        typer.echo(f"   Tokens: {tokens} | Cost: ${cost:.6f}")

        while True:
            prompt = "   Action (c=confirm/r=reject/s=skip/q=quit): "
            action = typer.prompt(prompt).strip().lower()

            if action == "c":
                self.save_review(
                    job_id, title, location, status="confirmed", tokens=tokens, estimated_cost=cost
                )
                stats.add_confirmed(tokens, cost)
                typer.echo(f"   ✓ Confirmed ({stats.confirmed}/{stats.total} confirmed)")
                break

            elif action == "r":
                reason_prompt = "   Rejection reason (tech/location/seniority/other): "
                reason = typer.prompt(reason_prompt).strip().lower()
                self.save_review(job_id, title, location, status="rejected", reason=reason)
                stats.add_rejected(reason)
                typer.echo("   ✗ Rejected")
                break

            elif action == "s":
                stats.add_skipped()
                typer.echo("   ⊘ Skipped (will review later)")
                break

            elif action == "q":
                typer.echo("\n⏹️  Review interrupted by user")
                raise typer.Exit(0)

            else:
                typer.echo("   ❌ Invalid action. Use c/r/s/q")

    def review_batch(
        self,
        extracted_file: str,
        preprocessed_file: str,
    ) -> ReviewStats:
        """
        Review multiple jobs interactively.

        Args:
            extracted_file: Path to extracted jobs JSON
            preprocessed_file: Path to preprocessed jobs JSON

        Returns:
            ReviewStats with final counts
        """
        import typer

        # Load jobs
        extracted_path = Path(extracted_file)
        preprocessed_path = Path(preprocessed_file)

        if not extracted_path.exists():
            logger.error(f"Extracted jobs file not found: {extracted_file}")
            typer.echo(f"❌ File not found: {extracted_file}", err=True)
            raise typer.Exit(1)

        if not preprocessed_path.exists():
            logger.error(f"Preprocessed jobs file not found: {preprocessed_file}")
            typer.echo(f"❌ File not found: {preprocessed_file}", err=True)
            raise typer.Exit(1)

        with open(extracted_path) as f:
            extracted_jobs = json.load(f)

        with open(preprocessed_path) as f:
            preprocessed_jobs = json.load(f)

        # Map preprocessed by job_id
        preprocessed_map = {j["job_id"]: j for j in preprocessed_jobs}

        stats = ReviewStats()
        typer.echo(f"\n👀 Starting job review ({len(extracted_jobs)} jobs total)\n")

        for idx, job in enumerate(extracted_jobs):
            job_id = job.get("id", f"job_{idx}")
            preprocessed = preprocessed_map.get(job_id, {})

            try:
                self.review_job_interactive(idx, len(extracted_jobs), job, preprocessed, stats)
            except typer.Exit:
                raise

        # Display summary
        typer.echo(stats.get_summary())

        return stats
