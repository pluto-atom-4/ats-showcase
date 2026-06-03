"""Typer CLI for ATS Playground workflow orchestration."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

import typer

from browser.crawler import Crawler
from storage.assessment_store import AssessmentStore
from storage.export import ExportConfig, MarkdownExporter

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="ats-cli",
    help="ATS Playground: Intelligent job assessment with AI",
    invoke_without_command=False,
)

# Create sub-applications for each phase
crawl_app = typer.Typer(help="Crawl company career pages")
preprocess_app = typer.Typer(help="Preprocess job postings")
review_app = typer.Typer(help="User verification & review")
assess_app = typer.Typer(help="AI assessment with Claude")
export_app = typer.Typer(help="Export results")

# Register sub-commands
app.add_typer(crawl_app, name="crawl")
app.add_typer(preprocess_app, name="preprocess")
app.add_typer(review_app, name="review")
app.add_typer(assess_app, name="assess")
app.add_typer(export_app, name="export")


# ============================================================================
# MAIN COMMANDS
# ============================================================================


@app.command()
def all(
    cv: str = typer.Option(..., help="Path to CV file (JSON)"),
    config: str = typer.Option(..., help="Path to companies config (JSON)"),
    headless: bool = typer.Option(True, help="Run browser in headless mode"),
    confirmed_only: bool = typer.Option(False, help="Skip unconfirmed jobs"),
) -> None:
    """
    Run full workflow: crawl → preprocess → review → assess → export.

    Example:
        python -m src.cli all --cv data/cv.json --config config/companies.json
    """
    import time

    logger.info("Running full workflow")
    typer.echo("✨ Full workflow started...\n")

    start_time = time.time()

    try:
        # ====================================================================
        # PHASE 1: CRAWL
        # ====================================================================
        typer.echo("=" * 80)
        typer.echo("PHASE 1: CRAWL - Extract job postings from career pages")
        typer.echo("=" * 80)

        phase_start = time.time()

        config_path = Path(config)
        if not config_path.exists():
            typer.echo(f"❌ Config file not found: {config}", err=True)
            raise typer.Exit(1)

        try:
            with open(config_path) as f:
                config_data = json.load(f)
        except json.JSONDecodeError as e:
            typer.echo(f"❌ Invalid JSON in config: {e}", err=True)
            raise typer.Exit(1) from None

        companies = config_data.get("companies", {})
        if not companies:
            typer.echo("❌ No companies found in config", err=True)
            raise typer.Exit(1)

        typer.echo(f"📋 Found {len(companies)} companies to crawl\n")

        crawler = Crawler(headless=headless, timeout_ms=30000)

        async def run_crawl():
            try:
                results = await crawler.crawl_multiple(companies)

                total_jobs = sum(len(jobs) for jobs in results.values())
                typer.echo(f"\n✅ Crawl complete! Extracted {total_jobs} total jobs\n")

                for company_name, jobs in results.items():
                    typer.echo(f"   • {company_name}: {len(jobs)} jobs")

                    if jobs:
                        output_file = (
                            Path("data/extracted_jobs") / f"{company_name.lower()}_jobs.json"
                        )
                        output_file.parent.mkdir(parents=True, exist_ok=True)

                        jobs_data = [job.model_dump(mode="json") for job in jobs]
                        with open(output_file, "w") as f:
                            json.dump(jobs_data, f, indent=2, default=str)
                        typer.echo(f"      Saved to: {output_file}")

                return results

            except Exception as e:
                logger.error(f"Crawl failed: {e}", exc_info=True)
                typer.echo(f"\n❌ Crawl failed: {e}", err=True)
                raise typer.Exit(1) from None
            finally:
                await crawler.close()

        crawl_results = asyncio.run(run_crawl())
        phase_time = time.time() - phase_start
        typer.echo(f"⏱️  Phase 1 took {phase_time:.2f}s\n")

        # ====================================================================
        # PHASE 2: PREPROCESS
        # ====================================================================
        typer.echo("=" * 80)
        typer.echo("PHASE 2: PREPROCESS - Clean HTML, chunk, count tokens")
        typer.echo("=" * 80)

        phase_start = time.time()

        from src.tokenization.chunker import SemanticChunker
        from src.tokenization.counter import TokenCounter

        extracted_dir = Path("data/extracted_jobs")
        if not extracted_dir.exists():
            typer.echo(f"❌ Directory not found: {extracted_dir}", err=True)
            raise typer.Exit(1)

        job_files = list(extracted_dir.glob("*_jobs.json"))
        if not job_files:
            typer.echo("❌ No extracted jobs found", err=True)
            raise typer.Exit(1)

        typer.echo(f"📂 Processing {len(job_files)} job files...\n")

        all_preprocessed = []
        failed_count = 0
        total_tokens = 0
        total_cost = 0.0

        chunker = SemanticChunker()
        counter = TokenCounter()

        for job_file in job_files:
            if "preprocessed" in job_file.name:
                continue

            with open(job_file) as f:
                jobs = json.load(f)

            typer.echo(f"📂 Processing {job_file.name}...")
            preprocessed_jobs = []

            for i, job in enumerate(jobs):
                try:
                    # Build clean text from available fields
                    clean_text = job.get("title", "")
                    if job.get("location"):
                        clean_text = f"{clean_text}\n{job.get('location', '')}"
                    if job.get("description"):
                        clean_text = f"{clean_text}\n{job.get('description', '')}"

                    chunks = chunker.chunk(clean_text)
                    token_count = sum(counter.count_tokens(c) for c in chunks)
                    estimated_cost = counter.estimate_cost(token_count)

                    preprocessed_job = {
                        "job_id": job.get("id"),
                        "title": job.get("title"),
                        "company": job.get("company"),
                        "location": job.get("location"),
                        "url": job.get("url"),
                        "clean_text": clean_text,
                        "chunks": chunks,
                        "token_count": token_count,
                        "estimated_cost": estimated_cost,
                        "status": "pending_review",
                    }

                    preprocessed_jobs.append(preprocessed_job)
                    total_tokens += token_count
                    total_cost += estimated_cost

                    if i % 5 == 0:
                        typer.echo(f"   Job {i}: {job.get('title', 'N/A')[:40]}...")
                        typer.echo(f"      Tokens: {token_count} | Cost: ${estimated_cost:.4f}")

                except Exception as e:
                    logger.error(f"Failed to preprocess job {i}: {e}", exc_info=True)
                    failed_count += 1

            all_preprocessed.extend(preprocessed_jobs)

        typer.echo("\n✅ Preprocessing complete!\n")
        typer.echo("📊 Summary:")
        typer.echo(f"   Total jobs: {len(all_preprocessed) + failed_count}")
        typer.echo(f"   Processed: {len(all_preprocessed)}")
        typer.echo(f"   Failed: {failed_count}")
        typer.echo(f"   Total tokens: {total_tokens}")
        typer.echo(f"   Total cost: ${total_cost:.4f}")

        if len(all_preprocessed) > 0:
            avg_tokens = total_tokens // len(all_preprocessed)
            typer.echo(f"   Avg tokens/job: {avg_tokens}")

        output_file = extracted_dir / "preprocessed_jobs.json"
        with open(output_file, "w") as f:
            json.dump(all_preprocessed, f, indent=2)
        typer.echo(f"   ✓ Saved to: {output_file}")

        phase_time = time.time() - phase_start
        typer.echo(f"⏱️  Phase 2 took {phase_time:.2f}s\n")

        # ====================================================================
        # PHASE 3: REVIEW
        # ====================================================================
        typer.echo("=" * 80)
        typer.echo("PHASE 3: REVIEW - Auto-confirm jobs (non-interactive mode)")
        typer.echo("=" * 80)

        phase_start = time.time()

        # For the `all` command, auto-confirm all jobs without interactive review
        typer.echo("⏭️  Skipping interactive review - auto-confirming all preprocessed jobs\n")

        # Load and auto-confirm preprocessed jobs
        preprocessed_path = Path("data/extracted_jobs/preprocessed_jobs.json")
        if preprocessed_path.exists():
            with open(preprocessed_path) as f:
                preprocessed_jobs = json.load(f)

            # Mark all as confirmed
            for job in preprocessed_jobs:
                job["status"] = "confirmed"

            # Save back
            with open(preprocessed_path, "w") as f:
                json.dump(preprocessed_jobs, f, indent=2)

            confirmed_count = len(preprocessed_jobs)
            typer.echo(f"✅ Auto-confirmed: {confirmed_count} jobs\n")
        else:
            confirmed_count = 0
            typer.echo("⚠️  No preprocessed jobs found\n")

        phase_time = time.time() - phase_start
        typer.echo(f"⏱️  Phase 3 took {phase_time:.2f}s\n")

        # ====================================================================
        # PHASE 4: ASSESS
        # ====================================================================
        typer.echo("=" * 80)
        typer.echo("PHASE 4: ASSESS - AI assessment with Claude")
        typer.echo("=" * 80)

        phase_start = time.time()

        from src.llm.provider import LLMProvider

        # Load CV
        cv_path = Path(cv)
        if not cv_path.exists():
            typer.echo(f"❌ CV file not found: {cv}", err=True)
            raise typer.Exit(1)

        with open(cv_path) as f:
            if cv_path.suffix == ".json":
                cv_data = json.load(f)
                cv_text = cv_data.get("text") or cv_data.get("content") or json.dumps(cv_data)
            else:
                cv_text = f.read()

        typer.echo(f"📄 Loaded CV from: {cv}\n")

        # Initialize LLM provider
        try:
            llm_provider = LLMProvider()
        except ValueError as e:
            typer.echo(f"❌ LLM setup failed: {e}", err=True)
            typer.echo("   Set ANTHROPIC_API_KEY environment variable", err=True)
            raise typer.Exit(1) from e

        # Load confirmed jobs from preprocessed file
        preprocessed_path = Path("data/extracted_jobs/preprocessed_jobs.json")
        confirmed_jobs = []
        if preprocessed_path.exists():
            with open(preprocessed_path) as f:
                jobs_data = json.load(f)
                confirmed_jobs = [j for j in jobs_data if j.get("status") == "confirmed"]

        if not confirmed_jobs:
            typer.echo("❌ No confirmed jobs found.", err=True)
            raise typer.Exit(1)

        typer.echo(f"🤖 Starting CV assessment for {len(confirmed_jobs)} confirmed jobs\n")

        # Initialize assessment store
        assessment_store = AssessmentStore()

        # Build map of preprocessed jobs for context
        preprocessed_map = {j["job_id"]: j for j in jobs_data} if "jobs_data" in locals() else {}

        # Assess each confirmed job
        successful = 0
        failed = 0
        assessment_list = []
        total_tokens = 0
        total_cost = 0.0

        for idx, job in enumerate(confirmed_jobs, 1):
            try:
                title = job.get("title", "Unknown")
                typer.echo(f"[{idx}/{len(confirmed_jobs)}] Assessing: {title[:50]}...", nl=False)

                # Get preprocessed job for context
                preprocessed = preprocessed_map.get(job["job_id"], {})
                clean_text = preprocessed.get("clean_text", job.get("description", ""))
                job_chunks = preprocessed.get("chunks", [clean_text])

                # Perform assessment
                assessment = llm_provider.assess_job(
                    job_id=job["job_id"],
                    job_chunks=job_chunks,
                    cv_text=cv_text,
                )

                # Store assessment
                assessment_store.save_assessment(
                    job_id=job["job_id"],
                    title=job.get("title", "Unknown"),
                    company=job.get("company", "Unknown"),
                    location=job.get("location", ""),
                    overall_score=assessment.overall_score,
                    tech_score=assessment.tech_score,
                    seniority_score=assessment.seniority_score,
                    location_score=assessment.location_score,
                    recommendations=assessment.recommendations,
                    summary=assessment.summary,
                    tokens_used=assessment.tokens_used,
                    actual_cost=assessment.actual_cost,
                )
                assessment_list.append(assessment)
                successful += 1
                total_tokens += assessment.tokens_used
                total_cost += assessment.actual_cost

                overall_score = assessment.overall_score
                typer.echo(f" ✅ Score: {overall_score:.0f}/100")

            except Exception as e:
                logger.error(f"Assessment failed for job {idx}: {e}", exc_info=True)
                failed += 1
                title = job.get("title", "Unknown")
                typer.echo(f"❌ Job {idx}/{len(confirmed_jobs)}: {title}\n" f"   Error: {e}\n")

        typer.echo("\n" + "=" * 80)
        typer.echo("📊 Assessment Summary:")
        typer.echo(f"   Total assessed: {successful}/{len(confirmed_jobs)}")
        if failed > 0:
            typer.echo(f"   Failed: {failed}")
        avg_score = sum(a.overall_score for a in assessment_list) / max(successful, 1)
        typer.echo(f"   Avg overall score: {avg_score:.1f}/100")
        typer.echo(f"   Total cost: ${total_cost:.6f}")
        typer.echo(f"   Total tokens: {total_tokens}")

        if successful > 0:
            top_matches = sorted(assessment_list, key=lambda a: a.overall_score, reverse=True)[:5]

            if top_matches:
                typer.echo("\n🏆 Top Matches:")
                # Get job titles from confirmed_jobs list
                job_titles = {j.get("job_id"): j.get("title", "N/A") for j in confirmed_jobs}
                for i, match in enumerate(top_matches, 1):
                    title = job_titles.get(match.job_id, "N/A")
                    typer.echo(f"   {i}. {title} - Overall: {match.overall_score:.0f}/100")

        typer.echo("\n✅ Assessment complete!\n")

        phase_time = time.time() - phase_start
        typer.echo(f"⏱️  Phase 4 took {phase_time:.2f}s\n")

        # ====================================================================
        # PHASE 5: EXPORT
        # ====================================================================
        typer.echo("=" * 80)
        typer.echo("PHASE 5: EXPORT - Generate markdown report")
        typer.echo("=" * 80)

        phase_start = time.time()

        try:
            # Validate inputs
            min_score = 0
            max_score = 100
            sort_by = "score"
            template = "detailed"
            include_recommendations = True
            include_stats = True
            output = "data/assessments/report.md"

            # Load assessment store
            db_path = "data/ats_playground.db"
            store = AssessmentStore(db_path)
            total = store.count_assessments()

            if total == 0:
                typer.echo(
                    "⚠️  No assessments found. Run assess-jobs first.",
                    err=True,
                )
                raise typer.Exit(1)

            # Create export config
            config = ExportConfig(
                min_score=min_score,
                max_score=max_score,
                sort_by=sort_by,
                template_style=template,
                include_recommendations=include_recommendations,
                include_stats=include_stats,
            )

            # Generate report
            exporter = MarkdownExporter(store, config)
            report_content = exporter.generate_report()
            
            # Write report to file
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report_content)
            report_path = output_path

            typer.echo(f"✅ Report exported to: {report_path}\n")

        except Exception as e:
            logger.error(f"Export failed: {e}", exc_info=True)
            typer.echo(f"❌ Export failed: {e}", err=True)
            raise typer.Exit(1) from None

        phase_time = time.time() - phase_start
        typer.echo(f"⏱️  Phase 5 took {phase_time:.2f}s\n")

        # ====================================================================
        # SUMMARY
        # ====================================================================
        total_time = time.time() - start_time
        typer.echo("=" * 80)
        typer.echo("🎉 FULL WORKFLOW COMPLETED SUCCESSFULLY!")
        typer.echo("=" * 80)
        typer.echo(f"⏱️  Total time: {total_time:.2f}s")
        typer.echo("📊 Generated files:")
        typer.echo("   - Data: data/extracted_jobs/")
        typer.echo("   - Database: data/ats_playground.db")
        typer.echo("   - Report: data/assessments/report.md")
        typer.echo("")

    except Exception as e:
        logger.error(f"Workflow failed: {e}", exc_info=True)
        typer.echo(f"\n❌ Workflow failed: {e}", err=True)
        raise typer.Exit(1) from None


# ============================================================================
# CRAWL COMMANDS
# ============================================================================


@crawl_app.command()
def crawl_companies(
    config: str = typer.Option("config/companies.json", help="Companies config file"),
    headless: bool = typer.Option(True, help="Headless browser mode"),
    timeout: int = typer.Option(30000, help="Browser timeout (ms)"),
    mock: bool = typer.Option(False, help="Mock crawling without browser"),
) -> None:
    """Crawl job postings from company career pages."""
    logger.info(f"Crawling companies from {config}")
    typer.echo("🌐 Crawling in progress...\n")

    config_path = Path(config)
    if not config_path.exists():
        typer.echo(f"❌ Config file not found: {config}", err=True)
        raise typer.Exit(1)

    try:
        with open(config_path) as f:
            config_data = json.load(f)
    except json.JSONDecodeError as e:
        typer.echo(f"❌ Invalid JSON in config: {e}", err=True)
        raise typer.Exit(1) from None

    companies = config_data.get("companies", {})
    if not companies:
        typer.echo("❌ No companies found in config", err=True)
        raise typer.Exit(1)

    typer.echo(f"📋 Found {len(companies)} companies to crawl\n")

    crawler = Crawler(headless=headless, timeout_ms=timeout)

    async def run_crawl():
        try:
            results = await crawler.crawl_multiple(companies)

            total_jobs = sum(len(jobs) for jobs in results.values())
            typer.echo(f"\n✅ Crawl complete! Extracted {total_jobs} total jobs\n")

            for company_name, jobs in results.items():
                typer.echo(f"   • {company_name}: {len(jobs)} jobs")

                if jobs:
                    output_file = Path("data/extracted_jobs") / f"{company_name.lower()}_jobs.json"
                    output_file.parent.mkdir(parents=True, exist_ok=True)

                    jobs_data = [job.model_dump(mode="json") for job in jobs]
                    with open(output_file, "w") as f:
                        json.dump(jobs_data, f, indent=2, default=str)
                    typer.echo(f"      Saved to: {output_file}")

        except Exception as e:
            logger.error(f"Crawl failed: {e}", exc_info=True)
            typer.echo(f"\n❌ Crawl failed: {e}", err=True)
            raise typer.Exit(1) from None
        finally:
            await crawler.close()

    asyncio.run(run_crawl())


# ============================================================================
# PREPROCESS COMMANDS
# ============================================================================


@preprocess_app.command()
def preprocess_jobs(
    batch_size: int = typer.Option(10, help="Jobs per batch"),
    show_estimates: bool = typer.Option(False, help="Show token/cost estimates"),
) -> None:
    """Preprocess job postings (clean HTML, chunk, count tokens)."""
    import json
    from pathlib import Path

    from src.models.job import JobPosting, PreprocessedJob
    from src.tokenization.chunker import SemanticChunker
    from src.tokenization.counter import TokenCounter

    logger.info("Starting preprocessing")
    typer.echo("🔄 Preprocessing jobs...\n")

    extracted_dir = Path("data/extracted_jobs")
    if not extracted_dir.exists():
        typer.echo(f"❌ Directory not found: {extracted_dir}", err=True)
        raise typer.Exit(1) from None

    job_files = [f for f in extracted_dir.glob("*_jobs.json") if "preprocessed" not in f.name]
    if not job_files:
        typer.echo("❌ No extracted jobs found", err=True)
        raise typer.Exit(1) from None

    chunker = SemanticChunker(target_chunk_size=400)
    counter = TokenCounter()

    all_preprocessed = []
    total_tokens = 0
    total_cost = 0.0
    failed_count = 0

    for job_file in job_files:
        typer.echo(f"📂 Processing {job_file.name}...")

        try:
            with open(job_file) as f:
                jobs_data = json.load(f)

            for i, job_dict in enumerate(jobs_data, 1):
                try:
                    job = JobPosting(**job_dict)

                    clean_text = job.title
                    if job.location:
                        clean_text = f"{job.title}\n{job.location}"

                    chunks = chunker.chunk(clean_text)
                    token_count = sum(counter.count_tokens(c) for c in chunks)
                    estimated_cost = counter.estimate_cost(token_count)

                    preprocessed = PreprocessedJob(
                        job_id=f"{job_file.stem}_{i}",
                        clean_text=clean_text,
                        sentences=clean_text.split("\n"),
                        chunks=chunks,
                        token_count=token_count,
                        estimated_cost=estimated_cost,
                    )

                    all_preprocessed.append(preprocessed)
                    total_tokens += token_count
                    total_cost += estimated_cost

                    if show_estimates and i <= 3:
                        typer.echo(f"   Job {i}: {job.title[:40]}...")
                        typer.echo(f"      Tokens: {token_count} | Cost: ${estimated_cost:.4f}")

                except Exception as e:
                    logger.warning(f"Failed to preprocess job {i}: {e}")
                    failed_count += 1

        except Exception as e:
            logger.error(f"Failed to process {job_file}: {e}")

    typer.echo("\n✅ Preprocessing complete!\n")
    typer.echo("📊 Summary:")
    typer.echo(f"   Total jobs: {len(all_preprocessed) + failed_count}")
    typer.echo(f"   Processed: {len(all_preprocessed)}")
    typer.echo(f"   Failed: {failed_count}")
    typer.echo(f"   Total tokens: {total_tokens}")
    typer.echo(f"   Total cost: ${total_cost:.4f}")

    if all_preprocessed:
        avg_tokens = total_tokens // len(all_preprocessed)
        typer.echo(f"   Avg tokens/job: {avg_tokens}")
        typer.echo("\n💾 Saving preprocessed jobs...")

        output_file = Path("data/extracted_jobs/preprocessed_jobs.json")
        jobs_output = [j.model_dump(mode="json") for j in all_preprocessed]

        with open(output_file, "w") as f:
            json.dump(jobs_output, f, indent=2, default=str)

        typer.echo(f"   ✓ Saved to: {output_file}")


# ============================================================================
# REVIEW COMMANDS
# ============================================================================


@review_app.command()
def review_jobs(
    extracted: str = typer.Option(
        "data/extracted_jobs/carbonrobotics_jobs.json", help="Path to extracted jobs JSON"
    ),
    preprocessed: str = typer.Option(
        "data/extracted_jobs/preprocessed_jobs.json", help="Path to preprocessed jobs JSON"
    ),
) -> None:
    """Interactively review extracted jobs before LLM assessment."""
    from src.verification import JobReviewer

    logger.info("Starting job review")

    try:
        reviewer = JobReviewer()
        stats = reviewer.review_batch(extracted, preprocessed)
        logger.info(f"Review complete: {stats.confirmed} confirmed, {stats.rejected} rejected")

    except Exception as e:
        logger.error(f"Review failed: {e}", exc_info=True)
        typer.echo(f"\n❌ Review failed: {e}", err=True)
        raise typer.Exit(1) from None


# ============================================================================
# ASSESS COMMANDS
# ============================================================================


@assess_app.command()
def assess_jobs(
    cv: str = typer.Option(..., help="CV file path (json or txt)"),
    confirmed_only: bool = typer.Option(True, help="Only assess confirmed jobs"),
) -> None:
    """Assess CV fit for confirmed jobs using Claude 3.5 Sonnet."""
    import json
    from pathlib import Path

    from src.llm.provider import LLMProvider
    from src.storage.assessment_store import AssessmentStore
    from src.verification import JobReviewer

    logger.info(f"Starting job assessment with CV: {cv}")

    try:
        # Load CV
        cv_path = Path(cv)
        if not cv_path.exists():
            typer.echo(f"❌ CV file not found: {cv}", err=True)
            raise typer.Exit(1)

        with open(cv_path) as f:
            if cv_path.suffix == ".json":
                cv_data = json.load(f)
                cv_text = cv_data.get("text") or cv_data.get("content") or json.dumps(cv_data)
            else:
                cv_text = f.read()

        typer.echo(f"📄 Loaded CV from: {cv}\n")

        # Initialize LLM provider
        try:
            llm_provider = LLMProvider()
        except ValueError as e:
            typer.echo(f"❌ LLM setup failed: {e}", err=True)
            typer.echo("   Set ANTHROPIC_API_KEY environment variable", err=True)
            raise typer.Exit(1) from e

        # Get confirmed jobs from database
        reviewer = JobReviewer()
        confirmed_jobs = reviewer.get_confirmed_jobs()

        if not confirmed_jobs:
            typer.echo("❌ No confirmed jobs found. Run 'review-jobs' first.", err=True)
            raise typer.Exit(1)

        typer.echo(f"🤖 Starting CV assessment for {len(confirmed_jobs)} confirmed jobs\n")

        # Initialize assessment store
        assessment_store = AssessmentStore()

        # Load preprocessed jobs for context
        preprocessed_path = Path("data/extracted_jobs/preprocessed_jobs.json")
        preprocessed_map = {}

        if preprocessed_path.exists():
            with open(preprocessed_path) as f:
                preprocessed_jobs = json.load(f)
                preprocessed_map = {j["job_id"]: j for j in preprocessed_jobs}

        # Assess each job
        successful = 0
        failed = 0
        total_cost = 0.0
        total_tokens = 0

        for idx, confirmed_job in enumerate(confirmed_jobs, 1):
            job_id = confirmed_job["job_id"]
            title = confirmed_job["title"]
            location = confirmed_job.get("location", "Unknown")

            try:
                # Get preprocessed chunks
                preprocessed = preprocessed_map.get(job_id, {})
                job_chunks = preprocessed.get("chunks", [title, location])

                # Assess job
                assessment = llm_provider.assess_job(job_id, job_chunks, cv_text)

                # Save assessment
                assessment_store.save_assessment(
                    job_id=job_id,
                    title=title,
                    company=confirmed_job.get("company", "Unknown"),
                    location=location,
                    overall_score=assessment.overall_score,
                    tech_score=assessment.tech_score,
                    seniority_score=assessment.seniority_score,
                    location_score=assessment.location_score,
                    recommendations=assessment.recommendations,
                    summary=assessment.summary,
                    tokens_used=assessment.tokens_used,
                    actual_cost=assessment.actual_cost,
                )

                # Display progress
                typer.echo(
                    f"✅ Job {idx}/{len(confirmed_jobs)}: {title}\n"
                    f"   Tech: {assessment.tech_score:.0f}/100 | "
                    f"Seniority: {assessment.seniority_score:.0f}/100 | "
                    f"Location: {assessment.location_score:.0f}/100 | "
                    f"Overall: {assessment.overall_score:.0f}/100\n"
                    f"   Cost: ${assessment.actual_cost:.6f} | "
                    f"Tokens: {assessment.tokens_used}\n"
                )

                successful += 1
                total_cost += assessment.actual_cost
                total_tokens += assessment.tokens_used

            except Exception as e:
                typer.echo(f"❌ Job {idx}/{len(confirmed_jobs)}: {title}\n" f"   Error: {e}\n")
                failed += 1
                logger.error(f"Assessment failed for job {job_id}: {e}", exc_info=True)

        # Display summary
        stats = assessment_store.get_stats()
        typer.echo("\n" + "=" * 80)
        typer.echo("📊 Assessment Summary:")
        typer.echo(f"   Total assessed: {successful}/{len(confirmed_jobs)}")
        if failed > 0:
            typer.echo(f"   Failed: {failed}")

        typer.echo(f"   Avg overall score: {stats.get('avg_score', 0):.1f}/100")
        typer.echo(f"   Total cost: ${total_cost:.6f}")
        typer.echo(f"   Total tokens: {total_tokens}")

        # Show top matches
        top_matches = assessment_store.get_top_matches(limit=3)
        if top_matches:
            typer.echo("\n🏆 Top Matches:")
            for i, match in enumerate(top_matches, 1):
                typer.echo(f"   {i}. {match['title']} - Overall: {match['overall_score']:.0f}/100")

        typer.echo("\n✅ Assessment complete!\n")

        logger.info(
            f"Assessment complete: {successful} successful, "
            f"{failed} failed, ${total_cost:.6f} total cost"
        )

    except Exception as e:
        logger.error(f"Assessment failed: {e}", exc_info=True)
        typer.echo(f"\n❌ Assessment failed: {e}", err=True)
        raise typer.Exit(1) from None


# ============================================================================
# EXPORT COMMANDS
# ============================================================================


@export_app.command()
def export_results(
    output: str = typer.Option("data/assessments/report.md", help="Output file path"),
    min_score: int = typer.Option(0, help="Minimum score to include (0-100)"),
    max_score: int = typer.Option(100, help="Maximum score to include (0-100)"),
    sort_by: str = typer.Option("score", help="Sort by: score, company, or location"),
    template: str = typer.Option("detailed", help="Template: detailed or summary"),
    include_recommendations: bool = typer.Option(True, help="Include LLM recommendations"),
    include_stats: bool = typer.Option(True, help="Include analytics section"),
) -> None:
    """Export assessment results to Markdown report."""
    try:
        # Validate inputs
        if not 0 <= min_score <= 100:
            typer.echo("❌ min_score must be 0-100", err=True)
            raise typer.Exit(1)
        if not 0 <= max_score <= 100:
            typer.echo("❌ max_score must be 0-100", err=True)
            raise typer.Exit(1)
        if min_score > max_score:
            typer.echo("❌ min_score must be <= max_score", err=True)
            raise typer.Exit(1)

        # Load assessment store
        db_path = "data/ats_playground.db"
        store = AssessmentStore(db_path)
        total = store.count_assessments()

        if total == 0:
            typer.echo(
                "⚠️  No assessments found. Run assess-jobs first.",
                err=True,
            )
            raise typer.Exit(1)

        # Create export config
        config = ExportConfig(
            min_score=min_score,
            max_score=max_score,
            sort_by=sort_by,
            template_style=template,
            include_recommendations=include_recommendations,
            include_stats=include_stats,
        )

        # Generate report
        typer.echo(f"📊 Generating report (score {min_score}-{max_score})...")
        exporter = MarkdownExporter(store, config)
        report = (
            exporter.generate_summary() if template == "summary" else exporter.generate_report()
        )

        # Write to file
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")

        # Display summary
        filtered_in_range = len(store.get_assessments_by_score(min_score, max_score))
        file_size_kb = output_path.stat().st_size / 1024

        typer.echo(f"✅ Exported {filtered_in_range}/{total} jobs to {output}")
        typer.echo(f"   File size: {file_size_kb:.1f} KB")
        typer.echo(f"   Template: {template}")

        logger.info(f"Export complete: {filtered_in_range} jobs, {file_size_kb:.1f} KB")

    except ValueError as e:
        typer.echo(f"❌ Invalid option: {e}", err=True)
        raise typer.Exit(1) from None
    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        typer.echo(f"❌ Export failed: {e}", err=True)
        raise typer.Exit(1) from None


# ============================================================================
# UTILITY COMMANDS
# ============================================================================


@app.command()
def query(
    keyword: str = typer.Option(..., help="Search keyword"),
    min_score: Optional[int] = typer.Option(None, help="Minimum score filter"),
    max_score: Optional[int] = typer.Option(None, help="Maximum score filter"),
    limit: int = typer.Option(10, help="Maximum results"),
    json_output: bool = typer.Option(False, help="Output as JSON"),
) -> None:
    """Search stored assessments by keyword and score."""
    try:
        # Load assessment store
        db_path = "data/ats_playground.db"
        store = AssessmentStore(db_path)

        # Set defaults
        min_s = min_score if min_score is not None else 0
        max_s = max_score if max_score is not None else 100

        # Search
        typer.echo(f"🔍 Searching for '{keyword}' (score {min_s}-{max_s}, limit {limit})...\n")
        results = store.search_by_keyword(keyword, min_score=min_s, max_score=max_s, limit=limit)

        if not results:
            typer.echo(f"⚠️  No results found for '{keyword}' in score range {min_s}-{max_s}")
            raise typer.Exit(0)

        if json_output:
            # JSON output
            output = json.dumps(results, indent=2, default=str)
            typer.echo(output)
        else:
            # Table output
            typer.echo(f"Found {len(results)} results:\n")
            typer.echo("Rank │ Company          │ Title                    │ Score │ Tech │ Senior")
            typer.echo("─────┼──────────────────┼──────────────────────────┼───────┼──────┼───────")

            for idx, job in enumerate(results, 1):
                company = str(job.get("company", "N/A"))[:15].ljust(15)
                title = str(job.get("job_title", "N/A"))[:24].ljust(24)
                overall = int(job.get("overall_score", 0))
                tech = int(job.get("tech_score", 0))
                seniority = int(job.get("seniority_score", 0))

                typer.echo(
                    f" {idx:2d}  │ {company} │ {title} │ {overall:3d}   │ {tech:3d}  │ {seniority:3d}"
                )

            # Stats
            typer.echo("")
            avg_score = sum(r.get("overall_score", 0) for r in results) / len(results)
            typer.echo(f"📊 Average score: {avg_score:.1f}")
            typer.echo(f"💡 Tip: Use 'export-results --min-score {min_s}' to get a full report")

        logger.info(f"Search complete: found {len(results)} results for '{keyword}'")

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        typer.echo(f"❌ Search failed: {e}", err=True)
        raise typer.Exit(1) from None


@app.command()
def stats(
    show_token_usage: bool = typer.Option(False, help="Show token statistics"),
) -> None:
    """Display database and cost statistics."""
    # TODO: Implement stats logic
    logger.info("Displaying statistics")
    typer.echo("📈 Statistics:")


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
