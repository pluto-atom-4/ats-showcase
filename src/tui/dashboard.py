"""Main TUI Dashboard for ATS Showcase workflow orchestration."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static

from src.browser.crawler import Crawler
from src.tui.models.state import PhaseStatus, StateManager
from src.tui.panels.assess_panel import AssessPanel
from src.tui.panels.crawl_panel import CrawlPanel
from src.tui.panels.export_panel import ExportPanel
from src.tui.panels.preprocess_panel import PreprocessPanel
from src.tui.widgets.phase_indicator import PhaseIndicator

logger = logging.getLogger(__name__)


class HeaderPanel(Static):
    """Header showing overall workflow status and cost."""

    def __init__(self, state: StateManager, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = state

    def render(self) -> str:
        """Render header with workflow status and total cost."""
        from src.tui.utils.formatters import format_cost, format_tokens

        title = "🎯 ATS Showcase - Workflow Dashboard"
        tokens = format_tokens(self.state.total_tokens_used)
        cost = format_cost(self.state.total_cost_usd)

        return f"{title}\nTokens: {tokens} | Total Cost: {cost}"


class ATPDashboard(Screen):
    """
    Main TUI Dashboard for ATS Showcase workflow.

    Layout:
    ┌─────────────────────────────────────┐
    │  Header: Workflow Status, Total Cost │
    ├─────────────────────────────────────┤
    │  Phase Indicator (✓ ⏳ ⚪ ⚪)        │
    ├─────────────────────────────────────┤
    │                                       │
    │  Active Panel (Crawl/Prep/Assess/Exp)│
    │                                       │
    ├─────────────────────────────────────┤
    │ [p]ause [r]esume [q]uit               │
    └─────────────────────────────────────┘
    """

    CSS = """
    Screen {
        layout: vertical;
    }

    #header {
        height: 3;
        border: solid $primary;
    }

    #phase-indicator {
        height: 1;
        background: $boost;
    }

    #content {
        height: 1fr;
        border: solid $primary;
    }

    #footer {
        height: 1;
        background: $boost;
    }
    """

    BINDINGS = [
        ("p", "pause_resume", "Pause/Resume"),
        ("r", "resume_workflow", "Resume"),
        ("q", "quit_app", "Quit"),
    ]

    def __init__(
        self,
        state: StateManager,
        companies: Optional[Dict[str, Any]] = None,
        cv_file: Optional[str] = None,
        headless: bool = True,
    ):
        super().__init__()
        self.state = state
        self.title = "ATS Showcase - TUI Dashboard"
        self.current_phase = "crawl"
        self.companies = companies or {}
        self.cv_file = cv_file
        self.cv_text = ""
        self.headless = headless

        # Load CV if provided
        if cv_file:
            self._load_cv(cv_file)

    def compose(self) -> ComposeResult:
        """Render dashboard layout."""
        yield HeaderPanel(self.state, id="header")
        yield PhaseIndicator(self.state, id="phase-indicator")

        with Vertical(id="content"):
            yield CrawlPanel(self.state, id="crawl-panel")
            preprocess_panel = PreprocessPanel(self.state, id="preprocess-panel")
            preprocess_panel.styles.display = "none"
            yield preprocess_panel

            assess_panel = AssessPanel(self.state, id="assess-panel")
            assess_panel.styles.display = "none"
            yield assess_panel

            export_panel = ExportPanel(self.state, id="export-panel")
            export_panel.styles.display = "none"
            yield export_panel

        yield Static("[p]ause [r]esume [q]uit", id="footer")

    def _show_panel(self, panel_id: str) -> None:
        """Show one panel, hide others."""
        for panel_name in [
            "crawl-panel",
            "preprocess-panel",
            "assess-panel",
            "export-panel",
        ]:
            panel = self.query_one(f"#{panel_name}")
            panel.styles.display = "block" if panel_name == panel_id else "none"

    def action_pause_resume(self) -> None:
        """Toggle pause on workflow."""
        self.state.paused = not self.state.paused
        verb = "Paused" if self.state.paused else "Resumed"
        self.notify(f"{verb} workflow")

    def action_resume_workflow(self) -> None:
        """Resume from pause."""
        if self.state.paused:
            self.state.paused = False
            self.notify("Resumed workflow")

    def action_quit_app(self) -> None:
        """Exit dashboard."""
        if any(
            s == PhaseStatus.RUNNING for s in self.state.phase_status.values()
        ):
            self.notify("Workflow still running. Press [p] to pause first.")
        else:
            self.app.exit()

    def _load_cv(self, cv_file: str) -> None:
        """Load CV text from file."""
        try:
            from pathlib import Path

            cv_path = Path(cv_file)
            if cv_path.exists():
                self.cv_text = cv_path.read_text(encoding="utf-8")
                logger.info(f"Loaded CV from {cv_file}")
            else:
                logger.warning(f"CV file not found: {cv_file}")
        except Exception as e:
            logger.error(f"Failed to load CV: {e}")

    def on_mount(self) -> None:
        """Start workflow when dashboard mounts."""
        self.run_workflow()

    def run_workflow(self) -> None:
        """Start async workflow orchestration."""
        asyncio.create_task(self._run_workflow_async())

    async def _run_workflow_async(self) -> None:
        """Run complete workflow asynchronously."""
        try:
            await self._phase_crawl()
            await self._phase_preprocess()
            await self._phase_assess()
            await self._phase_export()
            self.notify("Workflow complete!")
        except Exception as e:
            logger.exception(f"Workflow failed: {e}")
            self.notify(f"Error: {e}", severity="error")

    async def _phase_crawl(self) -> None:
        """Execute crawl phase."""
        self._show_panel("crawl-panel")
        self.state.start_phase("crawl", total_items=len(self.companies))

        if not self.companies:
            self.notify("No companies to crawl")
            self.state.complete_phase("crawl")
            return

        try:
            crawler = Crawler(headless=self.headless)
            results = await crawler.crawl_multiple(self.companies)
            await crawler.close()

            total_jobs = sum(len(jobs) for jobs in results.values())

            for _, jobs in results.items():
                for job in jobs:
                    self.state.add_job(
                        job_id=job.job_id,
                        title=job.title,
                        company=job.company,
                        location=job.location or "Unknown",
                        url=job.apply_url or "",
                    )
                self.state.increment_phase_progress("crawl")

            logger.info(f"Crawled {total_jobs} jobs from {len(results)} companies")
            self.state.complete_phase("crawl")
        except Exception as e:
            logger.exception(f"Crawl phase error: {e}")
            self.state.error_phase("crawl", str(e))
            self.notify(f"Crawl failed: {e}", severity="error")
            raise

    async def _phase_preprocess(self) -> None:
        """Execute preprocess phase."""
        from src.parsers.html_cleaner import HTMLCleaner
        from src.tokenization.chunker import SemanticChunker
        from src.tokenization.counter import TokenCounter

        self._show_panel("preprocess-panel")
        self.state.start_phase("preprocess", total_items=len(self.state.jobs))

        if not self.state.jobs:
            self.state.complete_phase("preprocess")
            return

        try:
            cleaner = HTMLCleaner()
            chunker = SemanticChunker(target_chunk_size=400)
            counter = TokenCounter()

            for job_id, job_data in self.state.jobs.items():
                try:
                    # Extract description to clean
                    description = job_data.get("description", "")
                    if not description:
                        self.state.increment_phase_progress("preprocess", tokens=0)
                        continue

                    # Clean HTML to text
                    clean_text = cleaner.clean(description)
                    if not clean_text:
                        self.state.increment_phase_progress("preprocess", tokens=0)
                        continue

                    # Chunk semantically by sentences
                    chunks = chunker.chunk(clean_text)

                    # Count tokens in all chunks
                    total_tokens = sum(counter.count_tokens(chunk) for chunk in chunks)

                    # Calculate estimated cost
                    estimated_cost = counter.estimate_cost(total_tokens)

                    # Update job with preprocessing results
                    self.state.update_job(
                        job_id,
                        clean_text=clean_text,
                        chunks=chunks,
                        total_tokens=total_tokens,
                        estimated_cost=estimated_cost,
                    )

                    self.state.increment_phase_progress("preprocess", tokens=total_tokens)
                    await asyncio.sleep(0.01)
                except Exception as e:
                    logger.warning(f"Failed to preprocess job {job_id}: {e}")
                    self.state.increment_phase_progress(
                        "preprocess", error=f"Preprocess failed: {e}"
                    )

            self.state.complete_phase("preprocess")
        except Exception as e:
            logger.exception(f"Preprocess phase error: {e}")
            self.state.error_phase("preprocess", str(e))
            raise

    async def _phase_assess(self) -> None:
        """Execute assess phase with LLM assessment."""
        from src.llm.provider import LLMProvider

        self._show_panel("assess-panel")
        self.state.start_phase("assess", total_items=len(self.state.jobs))

        if not self.state.jobs or not self.cv_text:
            logger.warning("No jobs or CV to assess")
            self.state.complete_phase("assess")
            return

        try:
            provider = LLMProvider()

            for job_id, job_data in self.state.jobs.items():
                try:
                    # Get preprocessed chunks
                    chunks = job_data.get("chunks", [])
                    if not chunks:
                        logger.debug(f"No chunks for job {job_id}, skipping")
                        self.state.increment_phase_progress("assess", tokens=0)
                        continue

                    # Assess with LLM
                    result = provider.assess_job(
                        job_id=job_id,
                        job_chunks=chunks,
                        cv_text=self.cv_text,
                    )

                    # Update job with assessment results
                    self.state.update_job(
                        job_id,
                        overall_score=result.overall_score,
                        tech_score=result.tech_score,
                        seniority_score=result.seniority_score,
                        location_score=result.location_score,
                        assessment_summary=result.summary,
                        recommendations=result.recommendations,
                    )

                    # Update progress with actual tokens and cost
                    self.state.increment_phase_progress(
                        "assess", tokens=result.tokens_used, cost=result.actual_cost
                    )

                    # Update top matches after each assessment
                    matches = [
                        {
                            "id": jid,
                            "title": self.state.jobs[jid].get("title", ""),
                            "company": self.state.jobs[jid].get("company", ""),
                            "overall_score": self.state.jobs[jid].get("overall_score", 0),
                        }
                        for jid in self.state.jobs.keys()
                        if self.state.jobs[jid].get("overall_score")
                    ]
                    self.state.update_top_matches(matches)

                    await asyncio.sleep(0.01)
                except Exception as e:
                    logger.warning(f"Failed to assess job {job_id}: {e}")
                    self.state.increment_phase_progress(
                        "assess", tokens=0, error=f"Assessment failed: {e}"
                    )

            self.state.complete_phase("assess")
        except Exception as e:
            logger.exception(f"Assess phase error: {e}")
            self.state.error_phase("assess", str(e))
            raise

    async def _phase_export(self) -> None:
        """Execute export phase with markdown report generation."""
        from pathlib import Path

        self._show_panel("export-panel")
        self.state.start_phase("export", total_items=1)

        try:
            # Generate markdown report
            report_dir = Path("data/assessments")
            report_dir.mkdir(parents=True, exist_ok=True)
            report_file = report_dir / "assessment_report.md"

            # Build markdown content
            lines = [
                "# ATS Showcase Assessment Report",
                f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "\n## Summary",
                f"- Total jobs assessed: {len(self.state.jobs)}",
                f"- Total tokens used: {self.state.total_tokens_used:,}",
                f"- Total cost: ${self.state.total_cost_usd:.6f}",
            ]

            # Add top matches section
            if self.state.top_matches:
                lines.append("\n## Top Matches")
                for i, match in enumerate(self.state.top_matches, 1):
                    lines.append(
                        f"\n### {i}. {match.get('title', 'N/A')} @ "
                        f"{match.get('company', 'N/A')}"
                    )
                    lines.append(f"**Overall Score:** {match.get('overall_score', 0):.0f}/100")

                    job_id = match.get("id")
                    if job_id and job_id in self.state.jobs:
                        job = self.state.jobs[job_id]
                        if "assessment_summary" in job:
                            lines.append(f"\n{job['assessment_summary']}")
                        if "recommendations" in job and job["recommendations"]:
                            lines.append("\n**Recommendations:**")
                            for rec in job["recommendations"]:
                                lines.append(f"- {rec}")

            # Add all jobs section (sorted by score)
            lines.append("\n## All Assessed Jobs")
            jobs_sorted = sorted(
                [
                    (jid, jdata)
                    for jid, jdata in self.state.jobs.items()
                    if jdata.get("overall_score")
                ],
                key=lambda x: x[1].get("overall_score", 0),
                reverse=True,
            )

            for _, job in jobs_sorted:
                lines.append(
                    f"\n### {job.get('title', 'N/A')} @ {job.get('company', 'N/A')}"
                )
                lines.append(f"**Score:** {job.get('overall_score', 0):.0f}/100")
                if "location" in job:
                    lines.append(f"**Location:** {job['location']}")

            # Write report
            report_content = "\n".join(lines)
            report_file.write_text(report_content, encoding="utf-8")
            logger.info(f"Report written to {report_file}")

            self.state.increment_phase_progress("export")
            self.state.complete_phase("export")
        except Exception as e:
            logger.exception(f"Export phase error: {e}")
            self.state.error_phase("export", str(e))
            raise


class ATPDashboardApp(App):
    """Textual App wrapper for ATPDashboard screen."""

    CSS = """
    Screen {
        layout: vertical;
    }
    """

    def __init__(
        self,
        state: StateManager,
        companies: Optional[Dict[str, Any]] = None,
        cv_file: Optional[str] = None,
        headless: bool = True,
    ):
        super().__init__()
        self.state = state
        self.companies = companies or {}
        self.cv_file = cv_file
        self.headless = headless

    def on_mount(self) -> None:
        """Mount dashboard screen when app starts."""
        dashboard = ATPDashboard(
            self.state,
            companies=self.companies,
            cv_file=self.cv_file,
            headless=self.headless,
        )
        self.push_screen(dashboard)
