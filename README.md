# ATS Playground

An agentic AI workflow for job assessment. Extract job postings from company websites, preprocess with NLP, verify with users, assess CV fit using Claude, and store results in a queryable database.

**Cost optimized**: 80–90% token reduction through preprocessing. ~$0.0006–0.0008 per assessment.

## Quick Start

```bash
# 1. Clone & setup
git clone https://github.com/yourusername/ats-playground.git
cd ats-playground
uv sync
python -m spacy download en_core_web_md

# 2. Set API key
export CLAUDE_API_KEY="sk-..."

# 3. Run workflow
python -m src.cli crawl --company acme
python -m src.cli preprocess
python -m src.cli review
python -m src.cli assess --all
python -m src.cli export --output results.md
```

## Documentation

**Start here**: [.github/copilot-instructions.md](./.github/copilot-instructions.md) (5 min quick-start)

**Full index**: [docs/README.md](./docs/README.md)

**Phase-specific guides**:
- [CRAWL.md](./docs/CRAWL.md) – Playwright multi-site crawling
- [PREPROCESS.md](./docs/PREPROCESS.md) – NLP preprocessing & chunking
- [VERIFY.md](./docs/VERIFY.md) – Interactive user verification
- [ASSESS.md](./docs/ASSESS.md) – Claude API integration & cost optimization
- [STORAGE.md](./docs/STORAGE.md) – SQLite persistence & querying
- [CLI.md](./docs/CLI.md) – Command reference

**System design**:
- [ARCHITECTURE.md](./docs/ARCHITECTURE.md) – Data flow, modules, scaling
- [CONVENTIONS.md](./docs/CONVENTIONS.md) – Code style, testing, deployment

**Troubleshooting**: [COMPATIBILITY.md](./docs/COMPATIBILITY.md)

## Features

- 🌐 **Multi-site crawling** – Playwright with JavaScript support, CSS selector pooling
- 🔄 **Smart preprocessing** – MarkItDown + BeautifulSoup, semantic chunking, token counting
- 👀 **User verification** – Interactive CLI review before expensive LLM calls
- 🤖 **LLM assessment** – Claude 3.5 Sonnet with rate limiting, batch processing, cost tracking
- 💾 **Data persistence** – SQLite with FTS5 full-text search, Markdown export
- 📊 **Cost analytics** – Real-time cost tracking, token accounting, per-job breakdowns

## Tech Stack

| Phase | Technology |
|-------|-----------|
| **Crawl** | Playwright (browser), async/await |
| **Preprocess** | MarkItDown, BeautifulSoup, spaCy, tiktoken |
| **Verify** | Typer (CLI), interactive prompts |
| **Assess** | Claude API, Anthropic SDK |
| **Store** | SQLite, FTS5 (full-text search) |
| **CLI** | Typer framework, async support |

## Requirements

- Python 3.11+
- `uv` (package manager)
- Chromium or Chrome (for Playwright)
- Claude API key

## Installation

See [.github/copilot-instructions.md](./.github/copilot-instructions.md#installation) for detailed setup.

```bash
# Using uv (recommended)
uv sync
python -m spacy download en_core_web_md
```

## Usage

```bash
# Full workflow
python -m src.cli --all --company acme

# Individual commands
python -m src.cli crawl --company acme --headless
python -m src.cli preprocess --batch 50
python -m src.cli review --interactive
python -m src.cli assess --mock  # test without API calls
python -m src.cli query --keyword "python" --min-score 75
python -m src.cli export --format md --output assessments.md
python -m src.cli stats

# Help
python -m src.cli --help
python -m src.cli assess --help
```

## Cost Example

Assessing 100 jobs:
- **Raw HTML**: ~6,000 tokens/job × 100 = 600,000 tokens
- **Preprocessed**: ~700 tokens/job × 100 = 70,000 tokens
- **Savings**: 530,000 tokens (88%)
- **LLM cost**: ~$0.07 (vs $0.60 unoptimized)

See [docs/PREPROCESS.md](./docs/PREPROCESS.md#token-cost-savings) for detailed breakdown.

## Testing

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=term-missing

# Specific test
pytest tests/test_llm.py::test_batch_processing -v
```

## Contributing

1. Read [CONVENTIONS.md](./docs/CONVENTIONS.md) for code style
2. Create feature branch: `git checkout -b feature/my-feature`
3. Make changes & test: `pytest tests/ -v`
4. Lint: `black src/` and `ruff check src/`
5. Commit: `git commit -m "feat(cli): add new command"`
6. Push & create PR

## Debugging

**Issue**: Playwright crashes  
**Solution**: `python -m playwright install chromium` and see [COMPATIBILITY.md](./docs/COMPATIBILITY.md#playwright--browser-installation)

**Issue**: spaCy model not found  
**Solution**: `python -m spacy download en_core_web_md` and see [COMPATIBILITY.md](./docs/COMPATIBILITY.md#spacy-model-issues)

**Issue**: Claude API errors  
**Solution**: Check `logs/app.log` and see [ASSESS.md](./docs/ASSESS.md#error-handling)

More troubleshooting: [COMPATIBILITY.md](./docs/COMPATIBILITY.md)

## Performance

| Metric | Value |
|--------|-------|
| Crawl speed | 100–200 jobs/min |
| Preprocess speed | 50–100 jobs/min |
| Assess speed | 2–5 jobs/min (Claude rate limit) |
| Query latency | <100ms (FTS5 indexed) |
| Database size | ~5 MB per 500 assessments |
| LLM cost | $0.0006–0.0008 per job |

## Architecture

```
CRAWL (Playwright)
  ↓
PREPROCESS (MarkItDown, spaCy)
  ↓
VERIFY (Interactive CLI)
  ↓
ASSESS (Claude API)
  ↓
STORE (SQLite)
  ↓
QUERY/EXPORT
```

See [ARCHITECTURE.md](./docs/ARCHITECTURE.md) for system design & data flow.

## License

MIT (or your chosen license)

## Questions?

- **How do I...?** → Check [docs/README.md](./docs/README.md)
- **Why does...?** → Check [ARCHITECTURE.md](./docs/ARCHITECTURE.md)
- **Getting error...?** → Check [COMPATIBILITY.md](./docs/COMPATIBILITY.md)
- **Best practice for...?** → Check [CONVENTIONS.md](./docs/CONVENTIONS.md)

---

**Last updated**: 2026-05-18  
**Status**: Active & Maintained  
**Documentation**: [8 comprehensive guides](./docs/README.md) — 165 KB total
