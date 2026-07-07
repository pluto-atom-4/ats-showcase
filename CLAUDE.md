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

## Pipeline Visibility (Issue #102 Phase 1)

Show job counts by status and filter impact before review:

```bash
# Display pipeline stats before review
uv run python -m src.cli review --merge-all --show-stats

# Output example:
# ================================================================================
# 📊 PIPELINE STATUS
# ================================================================================
#
# Total jobs:          127
#   • Pending review:  8      ← Ready for review
#   • Confirmed:       92     ← Ready for assessment
#   • Rejected:        23     ← Will be skipped
#   • Assessed:        4      ← Already processed
#
# Applying filters: --skip-rejected=True --skip-assessed=True
#   → Will process:  8 jobs
#   → Will skip:     119 jobs
#
# Skip breakdown:
#     • Rejected:       23
#     • Already assessed: 4
```

**Implementation:** Issue #102 Phase 1 adds:
- `get_pipeline_stats()` – Returns job counts by status (pending_review, confirmed, rejected, assessed)
- `get_stats_with_filters()` – Shows what would be processed/skipped with active filters
- `display_pipeline_stats()` – Formats stats for CLI display (handles missing tables gracefully)
- `--show-stats` flag – Displays stats before review workflow starts

## Score Threshold Filtering (Issue #102 Phase 2)

Filter jobs during assessment by minimum prior CV match score:

```bash
# Only assess jobs with prior match score ≥ 75%
uv run python -m src.cli assess --cv data/cv.json --score-threshold 75

# Show only high-confidence matches
uv run python -m src.cli query --keyword "python" --score-threshold 80
```

**Implementation:** Issue #102 Phase 2 adds:
- `get_jobs_by_score()` – Filters confirmed jobs by min prior_match_score
- `--score-threshold` flag on assess/query commands (default: 0 = no filtering)
- Job assessment table stores `prior_match_score` for each job
- Performance: Query runs in <100ms even with 10k+ jobs

## Interactive Re-Review Workflow (Issue #102 Phase 3)

Show prior review decisions and allow users to change status:

```bash
# Review with prior decision tracking
uv run python -m src.cli review --interactive --allow-re-review

# Output example:
# Job: Senior Python Developer @ TechCorp
# Location: Remote
# Prior decision: confirmed on 2026-07-01 14:22
# Tokens: 742 (estimated $0.002)
# ─────────────────────────────────────────
# [Confirm] [Reject] [Skip] [Re-review]:
```

**Implementation:** Issue #102 Phase 3 adds:
- `--allow-re-review` flag to review command (default: False)
- `reviewed_at` timestamp in job_reviews table (when status last changed)
- `re_review_audit` table tracks status change history and reasoning
- `get_prior_review()` fetches prior decision + timestamp
- `should_allow_re_review()` checks if job has prior decision
- Interactive prompt shows prior status + date before asking for new decision

## Job Timeline Visibility (Issue #102 Phase 4)

Track and display full job lifecycle from crawl to assessment:

```bash
# Timeline displayed during interactive review
uv run python -m src.cli review --interactive

# Output example:
# Job: Machine Learning Engineer @ TechCorp
# ─────────────────────────────────────────
# 📅 Timeline:
#   Crawled:      2026-07-01 10:00
#   Preprocessed: 2026-07-01 10:05
#   Reviewed:     2026-07-01 14:22
#   Assessed:     not processed
#
# Tokens: 742 (estimated $0.002)
# ─────────────────────────────────────────
# [Confirm] [Reject] [Skip]:
```

**Implementation:** Issue #102 Phase 4 adds:
- `crawled_at` timestamp in job_reviews (auto-set on crawl, fallback to current time)
- `preprocessed_at` timestamp in job_reviews (set when preprocessing completes)
- `reviewed_at` timestamp in job_reviews (set when review status changes)
- `assessed_at` timestamp in job_assessments (set when Claude assessment completes)
- `set_crawled_at()` method to record crawl timestamp
- `set_preprocessed_at()` method to record preprocessing completion
- `get_job_timeline()` fetches all 4 timestamps as dict
- `_format_timestamp()` converts ISO format to human-readable "YYYY-MM-DD HH:MM"
- `_display_job_timeline()` renders timeline in interactive review view
- `preprocess` command auto-updates preprocessed_at for all jobs
- Schema migration: `_run_migrations()` gracefully adds columns to existing databases

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
