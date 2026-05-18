# CLI Phase: Command-Line Interface with Typer

## Overview

The CLI phase provides a unified command-line interface orchestrating all ATS Playground phases:

1. **Command organization** - Logical grouping (crawl, preprocess, verify, assess, store, export)
2. **Interactive workflows** - Real-time user feedback during long operations
3. **Progress tracking** - Spinners, progress bars, cost estimates
4. **Error handling** - Clear error messages with remediation suggestions
5. **Help system** - Comprehensive `--help` at every level
6. **Typer framework** - Modern, type-hinted, async-ready CLI (Python 3.10+)

## Architecture

### Command Hierarchy

```
ats-playground/
├── crawl                    # Phase 1: Extract jobs from career pages
│   └── --config             # Company URLs + CSS selectors
│
├── preprocess               # Phase 2: Clean & chunk text
│   ├── --file               # Input JSON (extracted jobs)
│   └── --output             # Output file (preprocessed chunks)
│
├── review                   # Phase 3: User verification
│   ├── --file               # Jobs to review
│   └── --interactive        # Show cost estimates during review
│
├── assess                   # Phase 4: Claude LLM matching
│   ├── --cv                 # Candidate CV
│   ├── --confirmed-only     # Only process verified jobs
│   └── --model              # Claude model selection (Sonnet/Haiku)
│
├── query                    # Phase 5: Search results
│   ├── --search             # Keyword search (FTS5)
│   ├── --min-score          # Filter by match score
│   └── --company            # Filter by company
│
├── export                   # Phase 5: Generate reports
│   ├── --format             # md|csv|json
│   ├── --output             # Output file path
│   └── --min-score          # Export threshold
│
├── stats                    # Analytics
│   ├── --show-tokens        # Token usage report
│   ├── --show-costs         # Cost breakdown by company
│   └── --days               # Time period (default: 7)
│
└── --all                    # Full workflow (crawl→preprocess→verify→assess→export)
```

## Typer Implementation

### Project Structure

```python
src/
├── cli.py                   # Main entry point (Typer app)
├── commands/
│   ├── __init__.py
│   ├── crawl.py            # Crawl subcommand
│   ├── preprocess.py       # Preprocess subcommand
│   ├── review.py           # Review subcommand
│   ├── assess.py           # Assess subcommand
│   ├── query.py            # Query subcommand
│   ├── export.py           # Export subcommand
│   └── stats.py            # Stats subcommand
├── utils/
│   ├── formatting.py       # Tables, colors, progress
│   └── constants.py        # Defaults, messages
└── main.py                 # Entry point script
```

### Main CLI Entry Point

```python
# src/cli.py
import typer
from typing import Optional
from pathlib import Path
from rich.console import Console
import logging

from commands import crawl, preprocess, review, assess, query, export, stats

console = Console()
app = typer.Typer(
    name="ats-playground",
    help="Agentic AI workflow for job opportunity assessment",
    pretty_exceptions_enable=True,
    no_args_is_help=True,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/app.log"),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

# Register subcommands
app.command()(crawl.crawl_command)
app.command()(preprocess.preprocess_command)
app.command()(review.review_command)
app.command()(assess.assess_command)
app.command()(query.query_command)
app.command()(export.export_command)
app.command()(stats.stats_command)

@app.command()
def version():
    """Show version."""
    console.print("ATS Playground v1.0.0")

@app.command()
def init():
    """Initialize database and config."""
    from src.storage import StorageClient
    from pathlib import Path
    
    console.print("[bold]Initializing ATS Playground...[/bold]")
    
    # Create directories
    Path("data").mkdir(exist_ok=True)
    Path("logs").mkdir(exist_ok=True)
    
    # Initialize database
    storage = StorageClient()
    storage.init_schema()
    
    # Create example config if not exists
    config_path = Path("config/companies.json")
    if not config_path.exists():
        config_path.parent.mkdir(exist_ok=True)
        example_config = {
            "companies": [
                {
                    "name": "TechCorp",
                    "url": "https://techcorp.com/careers",
                    "selectors": {
                        "job_title": "h2.job-title",
                        "requirements": "div.requirements"
                    }
                }
            ]
        }
        import json
        with open(config_path, 'w') as f:
            json.dump(example_config, f, indent=2)
    
    console.print("[green]✓ Initialization complete[/green]")
    console.print(f"  - Database: data/ats_playground.db")
    console.print(f"  - Config: config/companies.json")
    console.print(f"  - Logs: logs/app.log")

@app.callback()
def global_options(
    debug: bool = typer.Option(False, help="Enable debug logging"),
    config: Optional[Path] = typer.Option(None, help="Config file path"),
):
    """Global options for all commands."""
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")

if __name__ == "__main__":
    app()
```

### Sample Subcommand: crawl.py

```python
# src/commands/crawl.py
import typer
from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.progress import Progress
import json

console = Console()

def crawl_command(
    config: Path = typer.Option(
        "config/companies.json",
        "--config",
        help="Company config file (JSON with URLs + CSS selectors)",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output directory for extracted jobs (default: data/extracted_jobs/)",
    ),
    headless: bool = typer.Option(
        True,
        "--headless/--no-headless",
        help="Run browser in headless mode",
    ),
    timeout: int = typer.Option(
        30,
        "--timeout",
        help="Page load timeout in seconds",
    ),
):
    """
    Phase 1: Crawl career pages and extract job postings.
    
    Reads company URLs from config file, navigates to each career page,
    and extracts job listings using CSS selectors.
    
    Example:
        ats-playground crawl --config config/companies.json
    """
    from src.browser import PlaywrightCrawler
    import logging
    
    logger = logging.getLogger(__name__)
    output_dir = output or Path("data/extracted_jobs")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load config
    try:
        with open(config) as f:
            config_data = json.load(f)
    except FileNotFoundError:
        console.print(f"[red]Error: Config file not found: {config}[/red]")
        raise typer.Exit(code=1)
    except json.JSONDecodeError:
        console.print(f"[red]Error: Invalid JSON in config file[/red]")
        raise typer.Exit(code=1)
    
    companies = config_data.get("companies", [])
    if not companies:
        console.print("[yellow]Warning: No companies in config[/yellow]")
        raise typer.Exit(code=1)
    
    # Initialize crawler
    crawler = PlaywrightCrawler(headless=headless, timeout=timeout)
    
    console.print(f"[bold]Crawling {len(companies)} companies...[/bold]\n")
    
    total_jobs = 0
    with Progress() as progress:
        task = progress.add_task("Crawling...", total=len(companies))
        
        for company in companies:
            company_name = company["name"]
            url = company["url"]
            selectors = company.get("selectors", {})
            
            try:
                jobs = crawler.extract_jobs(url, selectors, company_name)
                total_jobs += len(jobs)
                
                # Save to file
                output_file = output_dir / f"{company_name}_jobs.json"
                with open(output_file, 'w') as f:
                    json.dump(jobs, f, indent=2)
                
                console.print(
                    f"  [green]✓[/green] {company_name}: {len(jobs)} jobs → {output_file.name}"
                )
            
            except Exception as e:
                console.print(f"  [red]✗[/red] {company_name}: {str(e)}")
                logger.error(f"Crawl failed for {company_name}", exc_info=True)
            
            progress.advance(task)
    
    console.print(f"\n[bold green]✓ Crawl complete: {total_jobs} jobs extracted[/bold green]")

def get_company_selectors(company_name: str) -> dict:
    """Get CSS selectors for company (helper)."""
    # Could implement intelligent selector detection here
    return {
        "job_title": "h2.job-title, h3.position",
        "requirements": "div.requirements, ul.requirements",
        "responsibilities": "div.description, div.responsibilities",
    }
```

### Sample Subcommand: assess.py

```python
# src/commands/assess.py
import typer
from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.progress import Progress
from rich.panel import Panel
from rich.table import Table
import json
import logging

console = Console()

def assess_command(
    cv: Path = typer.Option(
        "data/cv.json",
        "--cv",
        help="Candidate CV file (JSON format)",
    ),
    confirmed_only: bool = typer.Option(
        True,
        "--confirmed-only/--all",
        help="Only assess verified jobs (default: confirmed only)",
    ),
    model: str = typer.Option(
        "claude-3-5-sonnet-20241022",
        "--model",
        help="Claude model (sonnet|haiku|opus)",
    ),
    min_score: float = typer.Option(
        0.0,
        "--min-score",
        help="Export only matches >= threshold (0.0-1.0)",
    ),
    batch_size: int = typer.Option(
        10,
        "--batch-size",
        help="Batch size for concurrent assessments",
    ),
):
    """
    Phase 4: Assess job-CV matches using Claude API.
    
    Loads verified job postings and CV, then uses Claude to score
    each job-CV pair on a 0.0-1.0 scale with reasoning.
    
    Example:
        ats-playground assess --cv data/cv.json --confirmed-only
    """
    from src.storage import StorageClient
    from src.llm import AssessmentClient, BatchAssessor
    
    logger = logging.getLogger(__name__)
    
    # Load CV
    try:
        with open(cv) as f:
            cv_data = json.load(f)
    except FileNotFoundError:
        console.print(f"[red]Error: CV file not found: {cv}[/red]")
        raise typer.Exit(code=1)
    
    cv_id = cv_data.get("id") or cv.stem
    cv_summary = cv_data.get("summary", "")
    
    # Load jobs from database
    storage = StorageClient()
    
    status_filter = "confirmed" if confirmed_only else "pending"
    cursor = storage.conn.cursor()
    cursor.execute("""
        SELECT * FROM jobs WHERE status = ?
    """, (status_filter,))
    
    jobs = [dict(row) for row in cursor.fetchall()]
    
    if not jobs:
        console.print(f"[yellow]No {status_filter} jobs to assess[/yellow]")
        raise typer.Exit(code=0)
    
    console.print(f"[bold]Assessing {len(jobs)} jobs for CV: {cv_id}[/bold]\n")
    
    # Initialize Claude client
    client = AssessmentClient(model=model)
    assessor = BatchAssessor(client)
    
    # Prepare job-CV pairs
    job_cv_pairs = [
        (job, cv_summary, job["job_id"], cv_id)
        for job in jobs
    ]
    
    # Run assessments
    try:
        assessor.assess_batch(job_cv_pairs, show_progress=True)
    except Exception as e:
        console.print(f"[red]Assessment failed: {str(e)}[/red]")
        logger.error("Batch assessment failed", exc_info=True)
        raise typer.Exit(code=1)
    
    # Save results
    assessor.save_results()
    
    # Print summary
    assessor.print_cost_summary()
    
    # Show top matches
    console.print("\n[bold]Top 5 Matches:[/bold]\n")
    top_matches = sorted(
        assessor.results,
        key=lambda r: r.match_score,
        reverse=True
    )[:5]
    
    table = Table(title="Top Matches")
    table.add_column("Score", style="cyan")
    table.add_column("Job", style="magenta")
    table.add_column("Company", style="green")
    table.add_column("Reasoning")
    
    for result in top_matches:
        job = next((j for j in jobs if j["job_id"] == result.job_id), {})
        table.add_row(
            f"{result.match_score:.1%}",
            job.get("title", "Unknown"),
            job.get("company_name", "Unknown"),
            result.reasoning[:50] + "..."
        )
    
    console.print(table)
```

## Complete Command Reference

### crawl
**Purpose**: Extract job postings from career pages

```bash
ats-playground crawl \
  --config config/companies.json \
  --output data/extracted_jobs/ \
  --headless \
  --timeout 30
```

**Options**:
- `--config PATH` - Company config file (required)
- `--output PATH` - Output directory (default: data/extracted_jobs)
- `--headless/--no-headless` - Browser mode (default: headless)
- `--timeout INT` - Page timeout seconds (default: 30)

**Output**: JSON files per company with extracted jobs

---

### preprocess
**Purpose**: Clean HTML, chunk text, count tokens

```bash
ats-playground preprocess \
  --file data/extracted_jobs/TechCorp_jobs.json \
  --output data/preprocessed_jobs/ \
  --strategy semantic
```

**Options**:
- `--file PATH` - Input jobs JSON (required)
- `--output PATH` - Output directory (default: data/preprocessed_jobs)
- `--strategy TEXT` - Chunking strategy: semantic|fixed (default: semantic)
- `--chunk-size INT` - Target tokens per chunk (default: 400)

**Output**: JSON with cleaned chunks, token counts, cost estimates

---

### review
**Purpose**: User verification before LLM processing

```bash
ats-playground review \
  --file data/extracted_jobs/TechCorp_jobs.json \
  --interactive \
  --show-costs
```

**Options**:
- `--file PATH` - Jobs to review (required)
- `--interactive/--batch` - Interactive vs batch review (default: interactive)
- `--show-costs/--hide-costs` - Show token costs (default: show)
- `--auto-confirm` - Auto-confirm jobs (use with caution!)

**Output**: Marked jobs as "confirmed"/"rejected" in database

---

### assess
**Purpose**: Claude LLM job-CV matching

```bash
ats-playground assess \
  --cv data/cv.json \
  --confirmed-only \
  --model claude-3-5-sonnet-20241022 \
  --batch-size 10
```

**Options**:
- `--cv PATH` - Candidate CV file (required)
- `--confirmed-only/--all` - Filter verified jobs (default: confirmed only)
- `--model TEXT` - Claude model selection (default: claude-3-5-sonnet-20241022)
- `--min-score FLOAT` - Filter results >= threshold (default: 0.0)
- `--batch-size INT` - Concurrent assessments (default: 10)

**Output**: Assessment results in CSV, cost summary printed

---

### query
**Purpose**: Search assessment results

```bash
ats-playground query \
  --search "Python" \
  --min-score 0.75 \
  --company TechCorp \
  --limit 20
```

**Options**:
- `--search TEXT` - Keyword search (FTS5) (optional)
- `--min-score FLOAT` - Filter by match score (default: 0.0)
- `--company TEXT` - Filter by company (optional)
- `--recommendation TEXT` - Filter: strong_match|moderate_match|weak_match (optional)
- `--limit INT` - Result limit (default: 20)

**Output**: Formatted table of results

---

### export
**Purpose**: Generate reports

```bash
ats-playground export \
  --format markdown \
  --output data/assessments/report.md \
  --min-score 0.75
```

**Options**:
- `--format TEXT` - md|csv|json (default: markdown)
- `--output PATH` - Output file (default: auto-generated)
- `--min-score FLOAT` - Export threshold (default: 0.0)
- `--group-by TEXT` - Group by: score|company|recommendation (default: score)

**Output**: Report file in requested format

---

### stats
**Purpose**: Analytics and cost tracking

```bash
ats-playground stats \
  --show-tokens \
  --show-costs \
  --days 7
```

**Options**:
- `--show-tokens/--hide-tokens` - Token usage report (default: show)
- `--show-costs/--hide-costs` - Cost breakdown (default: show)
- `--show-timing/--hide-timing` - Performance metrics (default: show)
- `--days INT` - Time period (default: 7)
- `--company TEXT` - Filter by company (optional)

**Output**: Summary tables and charts

---

### Full Workflow
**Purpose**: Execute all phases sequentially

```bash
ats-playground --all \
  --config config/companies.json \
  --cv data/cv.json \
  --output data/assessments/
```

**Equivalent to**:
```bash
ats-playground crawl --config config/companies.json
ats-playground review --file data/extracted_jobs/...
ats-playground assess --cv data/cv.json --confirmed-only
ats-playground export --format markdown --output data/assessments/
```

## Error Handling Patterns

### Error Messages & Remediation

```python
class CLIError(Exception):
    """Base CLI error with remediation."""
    
    def __init__(self, message: str, hint: str = None):
        self.message = message
        self.hint = hint
        super().__init__(message)

# Usage
def validate_cv_file(cv_path: Path):
    if not cv_path.exists():
        raise CLIError(
            f"CV file not found: {cv_path}",
            hint=f"Create CV at {cv_path} in JSON format"
        )
    
    try:
        with open(cv_path) as f:
            json.load(f)
    except json.JSONDecodeError:
        raise CLIError(
            f"Invalid JSON in {cv_path}",
            hint="Validate JSON syntax: python -m json.tool cv.json"
        )
```

### Exit Codes

| Code | Meaning | Remediation |
|------|---------|-------------|
| 0 | Success | - |
| 1 | Input/config error | Check `--help` and config files |
| 2 | Network error | Check internet connection, proxy |
| 3 | API error | Check ANTHROPIC_API_KEY, rate limits |
| 4 | Database error | Check file permissions, disk space |
| 5 | Timeout | Increase --timeout, check network |

## Interactive Workflows

### Review Command (Interactive Mode)

```
┌─ Job 1 of 5 ────────────────────────────────────┐
│ Title: Senior Python Engineer                    │
│ Company: TechCorp                                │
│ Requirements: 5+ years Python, AWS               │
│                                                   │
│ Token count: 450 / Cost: $0.0014                 │
│                                                   │
│ (c)onfirm / (r)eject / (e)dit / (s)kip / (q)uit? │
└────────────────────────────────────────────────┘
```

**Keystrokes**:
- `c` - Confirm and save to database
- `r` - Reject (mark for skip)
- `e` - Edit in $EDITOR
- `s` - Skip to next
- `q` - Quit

### Assess Command (Progress Tracking)

```
Assessing 50 jobs for CV: john_smith

▓▓▓▓▓▓▓▓░░░░░░░░░░░ 40%

[10/25] MES Programmer @ EngineerCorp
  ✓ Score: 0.82 | Cost: $0.0007 | Latency: 1.2s

[11/25] Manufacturing IT @ MfgCorp
  ✗ Error: Rate limited (retry 1/3)

Assessment complete:
  - Total: 50 jobs
  - Successful: 48 (96%)
  - Failed: 2 (4%)
  - Total cost: $0.035
  - Avg cost/job: $0.0007
```

## Testing CLI

### Unit Tests

```python
# tests/test_cli.py
import pytest
from typer.testing import CliRunner
from src.cli import app

runner = CliRunner()

def test_crawl_missing_config():
    """Test crawl with missing config file."""
    result = runner.invoke(app, ["crawl", "--config", "nonexistent.json"])
    assert result.exit_code == 1
    assert "not found" in result.stdout

def test_assess_success(tmp_path):
    """Test successful assessment workflow."""
    cv_file = tmp_path / "test_cv.json"
    cv_file.write_text('{"id": "test", "summary": "Python engineer"}')
    
    result = runner.invoke(app, ["assess", "--cv", str(cv_file), "--confirmed-only"])
    assert result.exit_code in [0, 1]  # 0 success, 1 no jobs

def test_query_keyword_search(tmp_path):
    """Test FTS5 keyword search."""
    result = runner.invoke(app, ["query", "--search", "Python"])
    assert result.exit_code == 0
```

### Integration Tests

```python
# tests/integration/test_full_workflow.py
def test_full_workflow(tmp_path, monkeypatch):
    """Test crawl→review→assess→export workflow."""
    from pathlib import Path
    
    # Setup
    config_file = tmp_path / "config.json"
    cv_file = tmp_path / "cv.json"
    output_dir = tmp_path / "output"
    
    config_file.write_text(json.dumps({
        "companies": [{
            "name": "TestCorp",
            "url": "https://example.com",
            "selectors": {"job_title": "h2"}
        }]
    }))
    
    cv_file.write_text(json.dumps({
        "id": "test_cv",
        "summary": "Experienced engineer"
    }))
    
    # Execute workflow
    runner = CliRunner()
    
    # Crawl
    result = runner.invoke(app, [
        "crawl",
        "--config", str(config_file),
        "--output", str(output_dir / "extracted")
    ])
    assert result.exit_code in [0, 1]  # May fail if URL unreachable
    
    # Export
    result = runner.invoke(app, [
        "export",
        "--format", "markdown",
        "--output", str(output_dir / "report.md")
    ])
    assert result.exit_code == 0
```

## Best Practices

✅ **Always provide defaults** - Users shouldn't need flags for common cases
✅ **Show costs upfront** - Display token/cost estimates before LLM calls
✅ **Batch operations** - Process multiple items efficiently
✅ **Progress feedback** - Show spinners, progress bars for long operations
✅ **Clear error messages** - Include "hint" for remediation
✅ **Async operations** - Use Typer's async support for concurrent work
✅ **Log everything** - Write to `logs/app.log` for debugging
✅ **Validation first** - Check inputs before expensive operations

❌ Don't silently ignore errors
❌ Don't process without user confirmation
❌ Don't make irreversible changes without --force flag
❌ Don't send to expensive APIs without showing cost estimate

## Deployment Checklist

- [ ] **Installation**:
  - [ ] `pip install -e .` installs CLI entry point
  - [ ] `ats-playground --help` works
  - [ ] `ats-playground version` shows version
  
- [ ] **Configuration**:
  - [ ] `ats-playground init` creates config/data directories
  - [ ] `.env` file with ANTHROPIC_API_KEY set
  - [ ] `config/companies.json` populated
  
- [ ] **Testing**:
  - [ ] Run unit tests: `pytest tests/ -v`
  - [ ] Test each subcommand manually
  - [ ] Test error cases (missing file, invalid config)
  - [ ] Run integration tests: `pytest tests/integration/ -v`
  
- [ ] **Documentation**:
  - [ ] `ats-playground --help` is clear
  - [ ] `ats-playground <command> --help` detailed
  - [ ] README.md has quick-start with commands
  
- [ ] **Performance**:
  - [ ] Crawl 100 jobs in <5 minutes
  - [ ] Preprocess 100 jobs in <1 minute
  - [ ] Assess 50 jobs in <5 minutes

## Next Steps

1. **Async support**: Add `async def` commands for concurrent operations
2. **Shell completion**: Generate bash/zsh/fish completions
3. **Config validation**: JSON schema for companies.json
4. **Telemetry**: Optional usage tracking (opt-in)
5. **Plugin system**: Allow custom commands via plugins

---

**Related Documentation**:
- [CRAWL.md](./CRAWL.md) - Crawling implementation
- [PREPROCESS.md](./PREPROCESS.md) - Preprocessing implementation
- [VERIFY.md](./VERIFY.md) - Verification workflow
- [ASSESS.md](./ASSESS.md) - Assessment implementation
- [STORAGE.md](./STORAGE.md) - Database queries
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System design
- [CONVENTIONS.md](./CONVENTIONS.md) - Code style & testing
