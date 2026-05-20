# Copilot Instructions for ATS Playground

> **For comprehensive architecture, design decisions, and detailed workflows, see [CLAUDE.md](../CLAUDE.md)**

## Claude Code Settings

This repository uses `.claude/settings.json` with:
- **Model**: Claude Sonnet (fast, cost-effective)
- **Extended Thinking**: Enabled for complex analysis
- **Permissions**: Pre-configured for safe `git`, `uv`, `pytest`, `black`, `ruff`, `python` commands
- **Post-tool Hooks**: Auto-formatting Python files and running relevant tests
- **LSP Support**: Pyright for Python type checking and intelligent code completion

**Key Denied Operations**: `rm -rf`, `git push --force`, hard resets, direct `.env` reads/writes.

## Quick Start

```bash
# Setup
uv sync
uv run python -m spacy download en_core_web_md
uv run playwright install
cp .env.example .env && # Add ANTHROPIC_API_KEY

# Initialize DB
uv run python src/storage/db.py --init

# Run full workflow
uv run python -m src.cli --all --cv data/cv.json --config config/companies.json
```

## Project Overview

**Agentic AI workflow for intelligent job opportunity assessment** with local preprocessing to save 80–90% on LLM costs.

### 6-Phase Pipeline

```
CONFIG (companies.json, CSS selectors)
    ↓
CRAWL (src/browser/) - Playwright automation, JavaScript rendering
    ↓ Raw HTML
PREPROCESS (src/parsers/ + src/tokenization/) - MarkItDown, spaCy, tiktoken
    ↓ Clean chunks + token estimates (~700 tokens vs 6,000 raw)
VERIFY (src/verification/) - Interactive CLI, user confirmation, cost transparency
    ↓ Confirmed jobs
ASSESS (src/llm/) - Claude 3.5 Sonnet scoring by category
    ↓ Assessment + metadata
STORAGE (src/storage/) - SQLite with FTS5 full-text search
    ↓ Queryable database
EXPORT (src/storage/) - Markdown reports, keyword search, analytics
```

### Key Design: Local Preprocessing

Raw HTML (~6,000 tokens per job) is cleaned and chunked locally to ~700 tokens, **cutting costs from $0.60 to $0.07 per 100 jobs**. This is the core value proposition—always preprocess before LLM calls.

## Module Reference

| Module | Purpose | Key Functions |
|--------|---------|---------------|
| `src/models/` | Pydantic v2 schemas for validation | `JobPosting`, `PreprocessedJob`, `Assessment` |
| `src/browser/` | Playwright automation | `BrowserManager` (async), `crawl()` |
| `src/parsers/` | HTML cleaning | `parse_html()`, fallback to BeautifulSoup |
| `src/tokenization/` | NLP chunking (spaCy) + token counting (tiktoken) | `chunk_by_sentences()`, `count_tokens()` |
| `src/verification/` | Interactive CLI review before LLM | `review_jobs_interactive()` |
| `src/llm/` | Claude API client | `LLMProvider`, `assess_job()` with retries |
| `src/storage/` | SQLite persistence + FTS5 search | `JobStore`, `export_markdown()` |
| `src/cli.py` | Typer CLI orchestration | 8 commands across 6 phases |

**Data Models** (in `src/models/job.py`):
- `JobPosting` - Raw scraped job data with extraction status
- `PreprocessedJob` - Cleaned text, semantic chunks, token count, cost estimate
- `Assessment` - CV match scores by category (overall, tech, seniority, location, recommendations)

## Directory Structure

```
src/
  browser/           # Playwright automation
  parsers/           # HTML parsing (BeautifulSoup)
  tokenization/      # NLP preprocessing (spaCy), chunking, token counting (tiktoken)
  models/            # Pydantic schemas
  verification/      # User review CLI
  llm/               # LLM client (provider abstraction)
  storage/           # SQLite persistence, queries, markdown export

config/companies.json          # Company URLs + CSS selectors
data/
  cv.json                      # User CV input
  extracted_jobs/              # Pending review
  ats_playground.db            # SQLite (auto-created)
  assessments/                 # Final markdown exports
```

## Commands

See `CLAUDE.md` for comprehensive command reference. Quick reference:

| Phase | Command |
|-------|---------|
| **Crawl** | `uv run python -m src.cli crawl --config config/companies.json` |
| **Preprocess** | `uv run python -m src.cli preprocess --show-estimates` |
| **Review** | `uv run python -m src.cli review --interactive` |
| **Assess** | `uv run python -m src.cli assess --cv data/cv.json` |
| **Export** | `uv run python -m src.cli export --output data/assessments/report.md` |
| **Full Workflow** | `uv run python -m src.cli --all --cv data/cv.json --config config/companies.json` |
| **Search** | `uv run python -m src.cli query --keyword "python" --min-score 75` |
| **Statistics** | `uv run python -m src.cli stats --show-token-usage` |
| **Tests** | `uv run pytest tests/ -v --cov=src` |
| **Format** | `uv run black src/ tests/` |
| **Lint** | `uv run ruff check src/ tests/ --fix` |
| **Type Check** | `mypy src/` |
| **Watch Logs** | `tail -f logs/app.log` |

## Key Conventions

### Architectural Decisions (See CLAUDE.md for Details)

1. **Semantic Chunking** - Split at sentence boundaries (spaCy), not random token breaks
   - Preserves meaning: "Requires 5+ years MES. Must know Wonderware." stays together
   - Target ~400 tokens/chunk for LLM safety

2. **Token Counting Before LLM** - Always estimate cost before API calls
   - Use tiktoken to count tokens upfront
   - Show user transparency: `tokens × $0.003/1M input`
   - Track actual vs estimated tokens for accuracy

3. **HTML Cleaning Precedence**
   - Primary: MarkItDown (Microsoft-maintained, preserves structure)
   - Fallback: BeautifulSoup + lxml (if MarkItDown unavailable)
   - Store clean text, not raw HTML (space savings)

4. **User Verification Before Assessment**
   - Show extracted job + estimated cost before LLM call
   - User confirms/edits/rejects → status saved to DB
   - Prevents sending low-confidence extractions to expensive API

5. **SQLite + FTS5 for Search**
   - Full-text search indexes: `jobs`, `assessments`, `cost_tracking`
   - <100ms query time even with 1000+ jobs
   - No external database; all data in `data/ats_playground.db`

6. **Claude 3.5 Sonnet** (Not Batch API)
   - Balance: fast enough for interactive workflows, cost-effective
   - Respects rate limits: ~10 RPM, ~50k TPM
   - Exponential backoff retries (max 3 attempts)

7. **Typer for CLI** (async-ready, type hints, sub-command organization)
   - See `src/cli.py` for command registration pattern

### Typical State Transitions

```
Extracted Job:
  status: pending_review → confirmed/rejected
  raw_html: <raw HTML>
  ↓ After preprocess:
  clean_text, chunks, estimated_tokens, estimated_cost
  ↓ After user verify (confirms):
  status: confirmed
  ↓ After LLM assess:
  assessment: {match_score, categories, reasoning}
  actual_tokens (tracked in cost_tracking table)
```

### Common Implementation Patterns

**Add a new CLI command** (Typer pattern):
```python
# In src/cli.py
@app.command()
def new_command(
    param: str = typer.Option(..., help="Description"),
) -> None:
    """Help text visible in --help."""
    logger.info(f"Starting new_command with {param}")
    typer.echo("Output to user")
```

**Access database**:
```python
from src.storage.db import JobStore
store = JobStore("data/ats_playground.db")
results = store.query_by_keyword("python", min_score=75)
```

**Count tokens**:
```python
from src.tokenization.counter import count_tokens
tokens = count_tokens(text)
cost_usd = tokens * 0.000003  # Claude 3.5 input rate
```

**Parse HTML**:
```python
from src.parsers.html import parse_html
clean_text = parse_html(raw_html)
```

### Non-Obvious Behaviors

- **Chunks are sentences, not fixed-size windows**: spaCy splits at sentence boundaries (intentional—preserves meaning better than token-based splits)
- **Confirmed status required for assessment**: By default, assess only processes jobs where `status == "confirmed"`. Use `--confirmed-only` flag to enforce
- **Cost estimates are pre-API**: tiktoken estimates; actual tokens from Claude may differ slightly (differences tracked in cost_tracking)
- **SQLite is single-writer**: Don't run multiple assessment processes concurrently on same DB (will lock). Use single-process pattern or queue

## Environment Variables

Required in `.env` (never commit `.env`, only `.env.example`):

```bash
ANTHROPIC_API_KEY=sk-ant-...           # Claude API key (REQUIRED)
SPACY_MODEL=en_core_web_md             # NLP model (default: en_core_web_md)
DATABASE_PATH=data/ats_playground.db   # SQLite location
LOG_LEVEL=INFO                         # Logging level
PLAYWRIGHT_HEADLESS=true               # Browser headless mode
```

See `.env.example` for full list. **Never commit real API keys** — GitHub secret scanning will alert if they're committed.

## Dependency Versions

**Locked versions** (see `pyproject.toml` for ranges):

```toml
playwright>=1.48.0         # Browser automation
markitdown>=0.1.5          # Primary HTML cleaner (fallback: BeautifulSoup)
beautifulsoup4>=4.12.0     # HTML parsing (fallback if MarkItDown unavailable)
spacy>=3.8.0               # NLP preprocessing
tiktoken>=0.8.0            # Token counting for cost estimation
pydantic>=2.5.0            # Data validation (v2 required)
anthropic>=0.25.0          # Claude API client
typer>=0.9.0               # CLI framework
```

**Check for vulnerabilities**:
```bash
uv pip audit          # Check all dependencies
pip-audit src/        # Check source code for known issues
```

See `docs/COMPATIBILITY.md` for version matrix and known issues.

## Common Issues & Troubleshooting

Detailed troubleshooting in `docs/COMPATIBILITY.md`. Quick fixes:

| Issue | Solution |
|-------|----------|
| **spaCy model not found** | `uv run python -m spacy download en_core_web_md` |
| **MarkItDown fails to install** | `pip install "markitdown[all]"` or use BeautifulSoup fallback |
| **Playwright browser crashes** | `uv run playwright install chromium` and check `logs/app.log` |
| **SQLite locked error** | Only one process can write at a time; wait for other assessments to finish |
| **Token count mismatch** | Expected—tiktoken estimates vs actual Claude tokens differ slightly (tracked in cost_tracking) |
| **Assessment skips jobs** | Ensure `status == "confirmed"` in DB; use `--confirmed-only` flag if needed |

**View logs**: `tail -f logs/app.log`  
**Full matrix**: See `docs/COMPATIBILITY.md`

## Documentation Map

**Detailed reference** (See CLAUDE.md for comprehensive architecture):
- **CLAUDE.md** - This is the canonical guide for Claude Code users (commands, architecture, patterns, troubleshooting)
- **README.md** - Project overview, quick start, benchmarks
- **docs/ARCHITECTURE.md** - System design, data flow, scaling strategies
- **docs/CONVENTIONS.md** - Code style, testing strategy, deployment checklist
- **docs/CRAWL.md** - Playwright patterns, CSS selectors, multi-site setup
- **docs/PREPROCESS.md** - MarkItDown, spaCy, semantic chunking, token math
- **docs/VERIFY.md** - Interactive CLI, user verification, cost transparency
- **docs/ASSESS.md** - Claude API integration, prompts, error handling, cost tracking
- **docs/STORAGE.md** - SQLite schema, FTS5 queries, markdown export
- **docs/CLI.md** - Command reference, Typer patterns, workflow orchestration
- **docs/COMPATIBILITY.md** - Known issues, version compatibility, troubleshooting matrix
- **SECURITY.md** - Vulnerability reporting, best practices, security review checklist
- **CONTRIBUTING.md** - Development workflow, code quality standards, PR process

**For Copilot users**: Start with CLAUDE.md, then reference phase-specific guides as needed.

## Performance Benchmarks

From real-world testing:

- **Crawling**: 100+ jobs/minute
- **Preprocessing**: 200+ jobs/minute
- **Token counting**: 1000+ jobs/second
- **LLM assessment**: 2–5 jobs/minute (rate-limited)
- **Database queries**: <100ms for FTS5 search (1000+ jobs)
- **Token savings**: 80–90% vs sending raw HTML to LLM

**Cost comparison** (100 jobs):
- Raw HTML to Claude: ~$0.60 (6,000 tokens × 2 API calls)
- Preprocessed chunks: ~$0.07 (700 tokens × 2 API calls)
- **Savings: 88%** 🎯

## Best Practices

✅ **DO**:
- Preprocess locally **before** sending to LLM
- Use semantic (sentence-based) chunks, not token-based
- Count tokens **before** API calls for cost estimation
- Show users cost estimates + actual usage
- Cache preprocessed results (avoid re-chunking)
- Run tests with `uv run pytest tests/ -v --cov=src`

❌ **DON'T**:
- Send raw HTML to Claude (expensive + inefficient)
- Auto-confirm all extracted jobs without user review
- Ignore SQLite locking errors (they indicate concurrent writes)
- Commit `.env` files or API keys
- Hardcode configuration (use config files + environment variables)

## Getting Help

1. **Quick Reference**: Check CLAUDE.md section headers (top of this doc links to it)
2. **Architecture Questions**: See `docs/ARCHITECTURE.md` for system design
3. **Phase-specific Issues**: Check relevant doc (CRAWL.md, PREPROCESS.md, etc.)
4. **Known Issues**: See `docs/COMPATIBILITY.md` for version matrix and workarounds
5. **Setup Verification**: `uv run pytest tests/ -v` to validate environment
6. **Debugging**: Check `tail -f logs/app.log` for detailed error context
7. **Security**: Review SECURITY.md for vulnerability reporting and best practices
8. **Contributing**: See CONTRIBUTING.md for code standards and PR process

## Claude Code Settings Reference

This repository is configured in `.claude/settings.json` with:
- **Extended Thinking**: Enabled for complex problem-solving
- **Pyright LSP**: Type checking and intelligent completions
- **Safe Command Permissions**: Pre-approved `git`, `uv`, `pytest`, `black`, `ruff` commands
- **Protected Operations**: `rm -rf`, `git push --force`, hard resets are blocked
- **Auto-formatting**: Python files auto-formatted on write
- **Auto-testing**: Relevant tests run after file modifications

**Network Access**: API calls allowed only to Anthropic, PyPI, and GitHub (sandboxed for security).
