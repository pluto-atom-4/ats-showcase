# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Commands

### Setup & Validation
```bash
uv sync                                          # Install dependencies
uv run python -m spacy download en_core_web_md  # Download NLP model
uv run playwright install                        # Download Chromium
cp .env.example .env                             # Create env file (add ANTHROPIC_API_KEY)
uv run python src/storage/db.py --init          # Initialize SQLite
```

### Development Commands
```bash
# Run full workflow
uv run python -m src.cli --all --cv data/cv.json --config config/companies.json

# Run individual phases
uv run python -m src.cli crawl --config config/companies.json
uv run python -m src.cli preprocess --show-estimates
uv run python -m src.cli review --interactive
uv run python -m src.cli assess --cv data/cv.json
uv run python -m src.cli export --output data/assessments/report.md

# Testing
uv run pytest tests/ -v                          # All tests
uv run pytest tests/test_llm.py -v              # Specific test file
uv run pytest tests/ -k "test_chunk" -v         # Tests matching pattern
uv run pytest tests/ -v --cov=src               # With coverage

# Linting & Formatting
uv run black src/ tests/                        # Format code
uv run ruff check src/ tests/ --fix             # Lint & fix

# Utilities
uv run python -m src.cli query --keyword "python" --min-score 75
uv run python -m src.cli stats --show-token-usage
tail -f logs/app.log                             # Watch logs
```

## GitHub Copilot CLI Plugin Model

Unlike Claude Code (which uses `.claude/settings.json`), GitHub Copilot CLI requires skills to be installed as **plugins** via the CLI plugin system.

### Two-System Architecture

1. **Claude Code Skills** (claude.ai/code)
   - Defined in: `.claude/settings.json`
   - Registration: `skillOverrides` array
   - Installation: Automatic (file-based)
   - When available: During Code sessions

2. **GitHub Copilot CLI Skills** (gh copilot)
   - Delivered via: GitHub plugin repositories
   - Installation: Manual (`gh copilot -- plugin install`)
   - Prerequisites: GitHub Copilot CLI installed + authenticated
   - When available: During CLI sessions

### Installing ATS Playground Plugin

To enable ATS Playground skills in GitHub Copilot CLI sessions:

```bash
# Install the plugin
gh copilot -- plugin install pluto-atom-4/copilot-plugin-ats-playground

# Verify installation
gh copilot -- plugin list

# Start a session
gh copilot

# In the session, use skills:
> /ats-preprocessing --help
> /ats-assessment --cv data/cv.json
> /ats-nlp-setup --model en_core_web_md
```

### Plugin Repository

The `copilot-plugin-ats-playground` repository contains:
- Plugin manifest (`plugin.json`)
- Skill definitions for:
  - `ats-nlp-setup`: Configure NLP models
  - `ats-preprocessing`: Preprocess job postings
  - `ats-assessment`: Assess job matches
- Usage examples and troubleshooting
- Full documentation

See: https://github.com/pluto-atom-4/copilot-plugin-ats-playground

### Important Note

This is separate from Claude Code configuration. Both systems can work together:
- **Claude Code**: Use skills defined in `.claude/settings.json`
- **GitHub Copilot CLI**: Use skills installed as plugins

## Architecture Overview

### Core Design: Local Preprocessing for Token Savings

The system reduces LLM costs **80–90%** by preprocessing jobs locally before sending to Claude. Raw HTML (~6,000 tokens per job) is cleaned and chunked to ~700 tokens locally, cutting costs from $0.60 to $0.07 per 100 jobs.

### Workflow Pipeline

```
CONFIG (companies.json, CSS selectors)
    ↓
CRAWL (src/browser/)
    • Playwright renders JavaScript
    • Extracts via CSS selectors
    • Rate limits & retries
    ↓ Raw HTML
PREPROCESS (src/parsers/ + src/tokenization/)
    • MarkItDown cleans HTML → clean text
    • spaCy segments by sentences (semantic, not token-based)
    • tiktoken counts tokens before LLM
    ↓ Clean chunks + token estimates
VERIFY (src/verification/)
    • Interactive CLI shows extracted jobs
    • User confirms/rejects before expensive API calls
    • Cost transparency (token count + USD estimate)
    ↓ Confirmed jobs
ASSESS (src/llm/)
    • Claude 3.5 Sonnet evaluates CV fit
    • Scores by category (tech skills, seniority, etc.)
    • Rate limiting & retry logic
    • Tracks actual vs estimated tokens
    ↓ Assessment + metadata
STORAGE (src/storage/)
    • SQLite with FTS5 full-text search index
    • Stores jobs, assessments, token counts, costs
    ↓ Queryable database
EXPORT (src/storage/)
    • Generate Markdown reports
    • Search by keyword/score
    • Analytics (token usage, cost breakdown)
```

### Module Structure

| Module | Purpose | Key Exports |
|--------|---------|-------------|
| **src/models/** | Pydantic schemas for data validation | Job, Assessment, CostMetrics |
| **src/browser/** | Playwright automation | BrowserManager (async) |
| **src/parsers/** | HTML cleaning (MarkItDown → BeautifulSoup fallback) | parse_html(), clean_text() |
| **src/tokenization/** | NLP chunking (spaCy) + token counting (tiktoken) | chunk_by_sentences(), count_tokens() |
| **src/verification/** | Interactive CLI review before LLM | review_jobs_interactive() |
| **src/llm/** | Claude API client (provider-agnostic pattern) | LLMProvider, assess_job() |
| **src/storage/** | SQLite persistence + queries + markdown export | JobStore, export_markdown() |
| **src/cli.py** | Typer CLI orchestration | app (Typer instance) |

### Key Architectural Decisions

**1. Semantic Chunking (Sentences, Not Tokens)**
- Split at sentence boundaries using spaCy NLP, not random token breaks
- Preserves meaning: "Requires 5+ years MES. Must know Wonderware." stays together
- Target ~400 tokens per chunk (safe for LLM context)
- See `src/tokenization/chunking.py`

**2. Token Counting Before LLM**
- Always use tiktoken to estimate tokens **before** sending to LLM
- Show user cost estimate: `tokens × $0.003 input per 1M tokens`
- Track actual tokens returned from Claude and compare
- Enables transparency + cost accountability

**3. HTML Cleaning Precedence**
- Primary: MarkItDown (preserves structure, Microsoft-maintained)
- Fallback: BeautifulSoup + lxml (if MarkItDown unavailable or too slow)
- Store clean text output, not raw HTML, to save space

**4. User Verification Before Assessment**
- Show extracted job + estimated cost before LLM call
- User confirms/edits/rejects → status saved in DB
- Prevents sending low-confidence extractions to expensive API
- Assessment only runs on "confirmed" jobs by default

**5. SQLite + FTS5 for Search**
- Jobs indexed by full-text search (FTS5 extension)
- Queries complete in <100ms even with 1000+ jobs
- Schema: `jobs` (main), `assessments` (related), `cost_tracking` (analytics)
- No external database needed; all data in `data/ats_playground.db`

**6. Claude 3.5 Sonnet (Not Batch API)**
- Chosen for balance: fast enough for interactive workflows, cost-effective
- Batch API not used because output is needed immediately for verification
- Rate limits: ~10 RPM, ~50k TPM (respects this in `src/llm/`)
- Retries with exponential backoff (max 3 attempts) on transient errors

**7. Typer for CLI (Not Click Directly)**
- Async-ready: allows concurrent crawling/assessment
- Built-in help + type hints
- Sub-apps for phase organization (`crawl`, `preprocess`, `assess`, etc.)
- See `src/cli.py` for command registration pattern

### Data Flow & State

```
Extracted Job (from crawl):
  status: pending_review → confirmed/rejected
  raw_html: <raw HTML from career page>
  ↓ After preprocess:
  clean_text: <MarkItDown output>
  chunks: [chunk1, chunk2, ...]
  estimated_tokens: 650
  estimated_cost: $0.002
  ↓ After verify (user confirms):
  status: confirmed
  ↓ After assess:
  assessment: {match_score: 78, categories: {...}, reasoning: "..."}
  actual_tokens: 673
  actual_cost: $0.002
  ↓ In storage (queryable):
  job_id, company, title, clean_text, chunks, assessment, tokens, cost
  (indexed by FTS5 for search)
```

### Environment Variables

Required in `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...           # Claude API key
SPACY_MODEL=en_core_web_md             # NLP model name
DATABASE_PATH=data/ats_playground.db   # SQLite file
LOG_LEVEL=INFO                         # Logging level
PLAYWRIGHT_HEADLESS=true               # Browser headless mode
```

### Common Patterns

**Add a new CLI command:**
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

**Access database from a module:**
```python
from src.storage.db import JobStore
store = JobStore("data/ats_playground.db")
results = store.query_by_keyword("python", min_score=75)
```

**Count tokens for a string:**
```python
from src.tokenization.counter import count_tokens
tokens = count_tokens(text)
cost_usd = tokens * 0.000003  # Claude 3.5 input rate
```

**Parse HTML to clean text:**
```python
from src.parsers.html import parse_html
clean_text = parse_html(raw_html)
```

### Important Non-Obvious Behavior

- **Chunks are sentences, not fixed-size windows**: Splitting at sentence boundaries (spaCy) means chunk sizes vary (100–600 tokens). This is intentional—preserves meaning better than token-based splits.
- **Confirmed status required for assessment**: By default, `assess` only processes jobs where `status == "confirmed"`. Use `--confirmed-only` flag to enforce; omit it to also assess "pending_review" jobs (for testing).
- **Cost estimates are pre-API**: Token counts in the UI are estimates from tiktoken. Actual tokens from Claude may differ slightly due to special tokens, prompt overhead, etc. Differences tracked in cost_tracking table.
- **SQLite is single-writer**: Don't run multiple assessment processes concurrently on the same DB (they will lock). Use a queue or single-process pattern.

## Testing Strategy

Tests are organized by module in `tests/`:
- **test_browser.py** – Playwright crawling (mocked browser)
- **test_parsers.py** – HTML cleaning (BeautifulSoup, MarkItDown fallback)
- **test_tokenization.py** – Chunking, token counting
- **test_llm.py** – Claude API client, error handling, retries
- **test_storage.py** – SQLite queries, FTS5 search, exports
- **test_cli.py** – CLI commands, argument parsing
- **test_verification.py** – Interactive verification CLI

Run by module or pattern (see Quick Commands above). Coverage target: 80%+.

## Known Issues & Troubleshooting

**MarkItDown installation fails:**
- Fallback to BeautifulSoup works, but slower
- If needed, install with: `pip install "markitdown[all]"`

**spaCy model not found:**
- Run: `uv run python -m spacy download en_core_web_md`

**Playwright browser crashes:**
- Ensure Chromium installed: `uv run playwright install chromium`
- Check logs: `tail -f logs/app.log`

**SQLite locked error:**
- Only one process can write at a time
- Wait for other assessments to finish
- If stuck, check: `lsof | grep ats_playground.db`

See `docs/COMPATIBILITY.md` for detailed troubleshooting and version matrix.

## Documentation Map

- **README.md** – Project overview, quick start, benchmarks
- **docs/ARCHITECTURE.md** – System design, data flow, scaling strategies
- **docs/CONVENTIONS.md** – Code style, testing, deployment checklist
- **docs/CRAWL.md** – Playwright patterns, CSS selectors, multi-site setup
- **docs/PREPROCESS.md** – MarkItDown, spaCy, semantic chunking, token math
- **docs/VERIFY.md** – Interactive CLI, user verification, cost transparency
- **docs/ASSESS.md** – Claude API integration, prompts, error handling, cost tracking
- **docs/STORAGE.md** – SQLite schema, FTS5 queries, markdown export
- **docs/CLI.md** – Command reference, Typer patterns, workflow orchestration
- **.github/copilot-instructions.md** – Concise overview for GitHub Copilot
- **CLAUDE.md** – This file

## Hooks & Settings

No special hooks or settings.json configuration required. Standard Python project.
