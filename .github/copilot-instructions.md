# Copilot Instructions for ATS Playground

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
uv run python main.py --all --cv data/cv.json --config config/companies.json
```

## Project Overview

Agentic AI workflow for job opportunity assessment:
1. **Crawl** career pages (Playwright) → extract jobs → validate (Pydantic)
2. **Preprocess** text (MarkItDown/BeautifulSoup) → HTML cleaning → semantic chunks → token count & cost estimate (spaCy, tiktoken)
3. **User verify** extracted data before LLM processing
4. **Assess** with Claude → match score by category
5. **Store** in SQLite (searchable) → export markdown

**Key**: Extract & chunk locally (80-90% token savings vs raw HTML)

## Tech Stack

- Python 3.11+ (3.13 recommended)
- **CLI**: Typer (modern, async-ready, well-documented)
- **Browser**: Playwright (multi-site support, maintainable)
- **HTML cleaning**: MarkItDown (primary, Microsoft) or BeautifulSoup4 + lxml (fallback)
- **NLP**: spaCy (v3.8+), tiktoken
- **Data**: Pydantic v2, SQLite
- **LLM**: Claude 3.5 Sonnet ($3.00/1M input, $15.00/1M output) ✅ recommended

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

| Task | Command |
|------|---------|
| Crawl & extract | `uv run python main.py crawl --config config/companies.json` |
| Preprocess | `uv run python main.py preprocess --file data/extracted_jobs/Company_jobs.json` |
| Review & confirm | `uv run python main.py review --file data/extracted_jobs/Company_jobs.json` |
| Assess with LLM | `uv run python main.py assess --cv data/cv.json --confirmed-only` |
| Export markdown | `uv run python main.py export --output data/assessments/report.md` |
| Full workflow | `uv run python main.py --all --cv data/cv.json --config config/companies.json` |
| Search results | `uv run python main.py query --search "MES" --min-score 75` |
| Token stats | `uv run python main.py stats --show-token-usage` |
| Run tests | `uv run pytest tests/ -v` |

## Key Conventions

### HTML Cleaning
- MarkItDown primary (preserves structure, token-efficient)
- BeautifulSoup + lxml fallback if MarkItDown unavailable
- Store clean text for preprocessing

### NLP Preprocessing (spaCy)
- Sentence segmentation (preserves meaning)
- Entity extraction (skills, technologies)
- Boilerplate removal (legal, EOE statements)

### Semantic Chunking
- Split at sentence boundaries, not random token breaks
- Target ~400 tokens/chunk (within LLM context)
- Example: "Requires 5+ years MES. Must know Wonderware." stays together

### Token Counting (tiktoken)
- Always count tokens **before** sending to LLM
- Display cost estimate to user (transparency)
- Track actual vs estimated tokens

### Data Validation (Pydantic v2)
- Define models in `src/models/`
- Validate before SQLite storage
- Catch errors early

### User Verification
- Show extracted job + token cost estimate
- User confirms/rejects/edits before LLM
- Prevents garbage data to expensive API calls

### SQLite Storage
- Jobs table with FTS5 index for keyword search
- Track token count & cost per job
- Status: pending_review, confirmed, rejected

### Error Handling
- Extraction fails → log, mark low confidence, mark for review
- Preprocessing fails → use fallback (simple sentence split)
- LLM fails → retry with exponential backoff (max 3 attempts)

## Environment Variables

Create `.env` from `.env.example`:

```
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...
SPACY_MODEL=en_core_web_md
DATABASE_PATH=data/ats_playground.db
LOG_LEVEL=INFO
PLAYWRIGHT_HEADLESS=true
```

## Dependency Versions

See `docs/COMPATIBILITY.md` for detailed version matrix and known issues.

```toml
dependencies = [
    "playwright>=1.48.0,<2.0",
    "markitdown>=0.1.5,<1.0",           # Primary HTML cleaner
    "beautifulsoup4>=4.12.0,<5.0",      # Fallback
    "lxml>=4.9.0,<5.0",
    "spacy>=3.8.0,<4.0",
    "tiktoken>=0.8.0,<1.0",
    "pydantic>=2.5.0,<3.0",
    "anthropic>=0.25.0,<1.0",
]
```

## Common Issues

**spaCy model not loading?**
```bash
uv run python -m spacy download en_core_web_sm
```

**MarkItDown installation issues?**
```bash
pip install "markitdown[all]"
# Falls back to BeautifulSoup if unavailable
```

**Playwright browsers missing?**
```bash
uv run playwright install
```

**SQLite locked?**
- Check if another process has DB open
- Retry with backoff

See `docs/COMPATIBILITY.md` for detailed troubleshooting.

## Documentation

**Phase-specific (in `docs/`):**
- **`CRAWL.md`** (19 KB, ✅ Done) - Playwright, CSS selectors, multi-site architecture
- **`PREPROCESS.md`** (21 KB, ✅ Done) - MarkItDown, BeautifulSoup, semantic chunking, token counting
- **`VERIFY.md`** (25 KB, ✅ Done) - Interactive CLI, user verification, cost transparency
- **`ASSESS.md`** (25 KB, ✅ Done) - Claude integration, prompts, cost optimization, error handling
- **`STORAGE.md`** (28.5 KB, ✅ Done) - SQLite schema, queries, export
- **`CLI.md`** (23.5 KB, ✅ Done) - Command reference, Typer patterns, full workflow orchestration

**Cross-cutting (in `docs/`):**
- **`ARCHITECTURE.md`** (13.8 KB, ✅ Done) - System architecture, data flow, phase integration, scaling
- **`CONVENTIONS.md`** (19 KB, ✅ Done) - Code style, testing strategy, deployment, troubleshooting

**Utilities:**
- **`README.md`** - Documentation navigation hub
- **`COMPATIBILITY.md`** - Known issues, version compatibility, detailed troubleshooting

## Performance

- Crawling: 100+ jobs/min
- Preprocessing: 200+ jobs/min
- Token counting: 1000+ jobs/sec
- LLM assessment: 2-5 jobs/min
- Token savings: 80-90% vs raw HTML

## Best Practices

✅ Extract locally (no LLM cost) | ✅ Preprocess before LLM | ✅ Semantic chunks | ✅ Count tokens before sending | ✅ User confirms | ✅ Track token usage | ✅ Cache preprocessed results

❌ Don't send raw HTML to LLM | ❌ Don't auto-confirm all jobs

## Getting Help

1. Check `COMPATIBILITY.md` for known issues
2. Check `ARCHITECTURE.md` for design details
3. Run: `uv run pytest tests/ -v` to verify setup
4. Check logs: `tail -f logs/app.log`
