"""Typer CLI for ATS Playground workflow orchestration."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

import typer

from src.browser.crawler import Crawler

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
        python -m src.cli --all --cv data/cv.json --config config/companies.json
    """
    # TODO: Implement full workflow orchestration
    logger.info("Running full workflow")
    typer.echo("✨ Full workflow started...")


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
    # TODO: Implement preprocessing logic
    logger.info("Preprocessing jobs")
    typer.echo("🔄 Preprocessing in progress...")


# ============================================================================
# REVIEW COMMANDS
# ============================================================================


@review_app.command()
def review_jobs(
    interactive: bool = typer.Option(True, help="Interactive review mode"),
    auto_approve: bool = typer.Option(False, help="Auto-approve all (dangerous!)"),
) -> None:
    """Interactively review extracted jobs before LLM assessment."""
    # TODO: Implement review logic
    logger.info("Starting job review")
    typer.echo("👀 Review mode started...")


# ============================================================================
# ASSESS COMMANDS
# ============================================================================


@assess_app.command()
def assess_jobs(
    cv: str = typer.Option(..., help="CV file path"),
    confirmed_only: bool = typer.Option(False, help="Only assess confirmed jobs"),
    mock: bool = typer.Option(False, help="Mock assessment without API calls"),
    batch: int = typer.Option(5, help="Batch size for rate limiting"),
) -> None:
    """Assess CV fit using Claude API."""
    # TODO: Implement assessment logic
    logger.info(f"Assessing jobs with CV: {cv}")
    typer.echo("🤖 Assessment in progress...")


# ============================================================================
# EXPORT COMMANDS
# ============================================================================


@export_app.command()
def export_results(
    output: str = typer.Option("data/assessments/report.md", help="Output file"),
    format: str = typer.Option("md", help="Format: md or json"),
    min_score: float = typer.Option(0, help="Minimum score to include"),
) -> None:
    """Export assessment results to Markdown or JSON."""
    # TODO: Implement export logic
    logger.info(f"Exporting to {output}")
    typer.echo(f"📊 Exporting to {output}...")


# ============================================================================
# UTILITY COMMANDS
# ============================================================================


@app.command()
def query(
    keyword: str = typer.Option(..., help="Search keyword"),
    min_score: Optional[float] = typer.Option(None, help="Minimum score"),
    limit: int = typer.Option(10, help="Result limit"),
) -> None:
    """Search stored assessments by keyword and score."""
    # TODO: Implement search logic
    logger.info(f"Searching for: {keyword}")
    typer.echo("🔍 Searching...")


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
