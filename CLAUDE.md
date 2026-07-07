# CLAUDE.md

ATS Playground: CV-to-jobs assessment system. Crawls career pages, preprocesses HTML, sends to Claude for scoring.

## NEVER DO THIS

- **Don't assess unconfirmed jobs**: Use `--confirmed-only` (default) to filter status
- **Don't run multiple assessment processes concurrently**: SQLite single-writer. Use queue/single-process
- **Don't send raw HTML to Claude**: Always preprocess (clean + chunk). Raw HTML ~6,000 tokens per job
- **Don't skip verification**: Always show user cost estimate before API calls
- **Don't force uniform token counts in chunks**: Splits at sentence boundaries (spaCy). Chunks vary 100–600 tokens intentionally
- **Don't re-assess already reviewed jobs**: Use pipeline control flags (--skip-assessed, --skip-rejected) to skip jobs

## Setup

```bash
uv sync
uv run python -m spacy download en_core_web_md
uv run playwright install chromium
cp .env.example .env  # Set ANTHROPIC_API_KEY
uv run python src/storage/db.py --init
```

## Quick Workflow

```bash
# Full pipeline (single config)
uv run python -m src.cli --all --cv data/cv.json --config config/companies.json

# Or step-by-step
uv run python -m src.cli crawl --config config/companies.json
uv run python -m src.cli preprocess --show-estimates
uv run python -m src.cli review --interactive
uv run python -m src.cli assess --cv data/cv.json
uv run python -m src.cli export --output data/assessments/report.md

# Review with pipeline control (skip already-assessed/rejected jobs)
uv run python -m src.cli review --merge-all --skip-assessed --skip-rejected
# Skip jobs crawled before a date (selective re-assessment)
uv run python -m src.cli review --merge-all --skip-before-date 2026-07-01
```

## Verification Commands

```bash
uv run pytest tests/ -v                          # All tests
uv run pytest tests/ -v --cov=src               # With coverage
uv run black src/ tests/ && uv run ruff check src/ tests/ --fix  # Format + lint
uv run python -m src.cli query --keyword "python" --min-score 75  # Query DB
uv run python -m src.cli stats --show-token-usage              # Cost breakdown
tail -f logs/app.log                             # Watch logs
```

## Phase-Specific Rules

- **Crawl**: `.claude/rules/crawl.md` – Playwright, CSS selectors, rate limiting
- **Preprocess**: `.claude/rules/preprocess.md` – MarkItDown, spaCy chunking, token counting
- **Verify**: `.claude/rules/verify.md` – Interactive CLI, cost transparency, status flow
- **Assess**: `.claude/rules/assess.md` – Claude API, prompts, rate limiting, error handling
- **Storage**: `.claude/rules/storage.md` – SQLite schema, FTS5, markdown export
- **CLI**: `.claude/rules/cli.md` – Typer patterns, command organization

## Workflows

- **Crawl + Preprocess**: `.claude/skills/crawl-jobs/SKILL.md`
- **Review + Assess**: `.claude/skills/assess-jobs/SKILL.md`

## Pipeline Control (Issue #100)

Skip re-assessing jobs using filtering options on the `review` command:

```bash
# Skip previously rejected jobs (default: True)
uv run python -m src.cli review --merge-all --skip-rejected

# Skip already assessed jobs (default: True)
uv run python -m src.cli review --merge-all --skip-assessed

# Skip jobs crawled before a date (selective re-assessment)
uv run python -m src.cli review --merge-all --skip-before-date 2026-07-01

# Combine filters
uv run python -m src.cli review --merge-all --skip-before-date 2026-07-01 --skip-rejected --skip-assessed
```

**Database Schema for Filtering:**
- `jobs.crawled_at` (TEXT, ISO format) – Timestamp when job was extracted
- `job_reviews.status` (TEXT) – pending, confirmed, rejected
- `job_assessments` (table) – Tracks jobs already assessed by Claude

**Implementation:** Phase 2-3 (issue #100) adds:
- `get_jobs_needing_assessment()` – Returns confirmed jobs without assessments
- `get_jobs_since()` – Date-based filtering for selective re-crawl
- `should_skip_job()` – Combines review status, assessment, and date checks

## Tech Stack

- **Browser**: Playwright (async, JS rendering)
- **HTML cleaning**: MarkItDown (primary), BeautifulSoup (fallback)
- **NLP**: spaCy (sentence segmentation)
- **Tokens**: tiktoken (estimates), Claude API (actual)
- **DB**: SQLite with FTS5 full-text search
- **LLM**: Claude 3.5 Sonnet ($0.003 per 1M input tokens)
- **CLI**: Typer (async-ready)

## Docs

- **DESIGN.md** – Architecture, module structure, decisions
- **PLUGIN.md** – GitHub Copilot CLI plugin
- **README.md** – Overview, quick start, benchmarks
- **docs/COMPATIBILITY.md** – Troubleshooting, version matrix
