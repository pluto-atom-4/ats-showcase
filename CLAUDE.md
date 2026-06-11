# CLAUDE.md

Quick reference for Claude Code when working with ATS Playground.

For architecture, design decisions, and implementation patterns → see **DESIGN.md**
For GitHub Copilot CLI plugin setup → see **PLUGIN.md**

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
# Run full workflow (single config file)
uv run python -m src.cli --all --cv data/cv.json --config config/companies.json

# Run full workflow (directory of configs)
uv run python -m src.cli --all --cv data/cv.json --config-dir ./config

# Run individual phases
uv run python -m src.cli crawl --config config/companies.json
uv run python -m src.cli crawl --config-dir ./config
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

## Key Non-Obvious Behavior

- **Chunks are sentences, not tokens**: Splitting at sentence boundaries (spaCy) preserves meaning better than random token breaks. Chunk sizes vary 100–600 tokens.
- **Confirmed status required for assessment**: By default, `assess` only processes jobs where `status == "confirmed"`. Omit `--confirmed-only` flag to also assess "pending_review" jobs (for testing).
- **Cost estimates are pre-API**: Token counts shown are tiktoken estimates. Actual tokens from Claude may differ slightly (special tokens, prompt overhead). Differences tracked in cost_tracking table.
- **SQLite is single-writer**: Don't run multiple assessment processes concurrently on the same DB. Use a queue or single-process pattern.

## Testing & Troubleshooting

Tests organized by module in `tests/`. Coverage target: 80%+.

**Common issues:**
- **spaCy model not found**: Run `uv run python -m spacy download en_core_web_md`
- **Playwright browser crashes**: Ensure Chromium installed: `uv run playwright install chromium`. Check logs: `tail -f logs/app.log`
- **SQLite locked error**: Only one process can write at a time. Wait for other assessments to finish.

See `docs/COMPATIBILITY.md` for detailed troubleshooting and version matrix.

## Documentation

- **DESIGN.md** – Architecture, module structure, design decisions, common patterns
- **PLUGIN.md** – GitHub Copilot CLI plugin installation
- **README.md** – Project overview, quick start, benchmarks
- **docs/ARCHITECTURE.md** – System design, data flow, scaling strategies
- **docs/CRAWL.md** – Playwright patterns, CSS selectors, multi-site setup
- **docs/PREPROCESS.md** – MarkItDown, spaCy, semantic chunking, token math
- **docs/ASSESS.md** – Claude API integration, prompts, error handling
- **docs/STORAGE.md** – SQLite schema, FTS5 queries, markdown export
- **docs/CLI.md** – Command reference, Typer patterns, workflow orchestration
