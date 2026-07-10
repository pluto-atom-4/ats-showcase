# Copilot Instructions for ATS Playground

> **Comprehensive guide**: Read [CLAUDE.md](../CLAUDE.md) (core rules), [AGENTS.md](../AGENTS.md) (roles), [DESIGN.md](../DESIGN.md) (architecture), and [.claude/rules/](../.claude/rules/) (phase details).

---

## Quick Start

```bash
# Setup (see CLAUDE.md § Setup for details)
uv sync
uv run python -m spacy download en_core_web_md
uv run playwright install
cp .env.example .env  # Add ANTHROPIC_API_KEY

# Run full workflow
uv run python -m src.cli --all --cv data/cv.json --config config/companies.json
```

See [CLAUDE.md § Quick Workflow](../CLAUDE.md#quick-workflow) for complete command reference.

---

## Architecture Overview

6-phase agentic AI pipeline for intelligent job assessment:

```
CONFIG → CRAWL → PREPROCESS → VERIFY → ASSESS → EXPORT
```

**Key Design**: Local preprocessing reduces LLM costs 80–90% ($0.60 → $0.07 per 100 jobs).

**Detailed Architecture**: See [DESIGN.md](../DESIGN.md)

---

## Phase Reference

| Phase | Purpose | Rules File | Command |
|-------|---------|-----------|---------|
| **Crawl** | Browser automation (Playwright) | [.claude/rules/crawl.md](../.claude/rules/crawl.md) | `uv run python -m src.cli crawl --config config/companies.json` |
| **Preprocess** | HTML cleaning, NLP chunking, token counting | [.claude/rules/preprocess.md](../.claude/rules/preprocess.md) | `uv run python -m src.cli preprocess --show-estimates` |
| **Verify** | Interactive user review + cost transparency | [.claude/rules/verify.md](../.claude/rules/verify.md) | `uv run python -m src.cli review --interactive` |
| **Assess** | Claude API scoring by category | [.claude/rules/assess.md](../.claude/rules/assess.md) | `uv run python -m src.cli assess --cv data/cv.json` |
| **Storage** | SQLite persistence, FTS5 search | [.claude/rules/storage.md](../.claude/rules/storage.md) | `uv run python -m src.cli query --keyword "python"` |
| **CLI** | Typer command organization | [.claude/rules/cli.md](../.claude/rules/cli.md) | `uv run python -m src.cli --help` |

---

## Module Reference

| Module | Purpose | Key Classes |
|--------|---------|------------|
| `src/models/` | Pydantic schemas | `JobPosting`, `PreprocessedJob`, `Assessment` |
| `src/browser/` | Playwright automation | `BrowserManager`, `crawl()` |
| `src/parsers/` | HTML cleaning | `parse_html()`, BeautifulSoup fallback |
| `src/tokenization/` | NLP + token counting | `chunk_by_sentences()`, `count_tokens()` |
| `src/verification/` | Interactive CLI review | `JobReviewer`, `review_jobs_interactive()` |
| `src/llm/` | Claude API client | `LLMProvider`, `assess_job()` |
| `src/storage/` | SQLite + FTS5 | `JobStore`, `export_markdown()` |

---

## Key Conventions

1. **Semantic Chunking** – Split at sentence boundaries, not random tokens (preserves meaning)
   → See [.claude/rules/preprocess.md](../.claude/rules/preprocess.md)

2. **Token Transparency** – Always estimate + show cost before LLM calls
   → See [.claude/rules/verify.md](../.claude/rules/verify.md)

3. **HTML Cleaning** – MarkItDown primary, BeautifulSoup fallback
   → See [.claude/rules/preprocess.md](../.claude/rules/preprocess.md)

4. **User Verification** – Confirm/reject/edit before assessment
   → See [.claude/rules/verify.md](../.claude/rules/verify.md)

5. **SQLite + FTS5** – No external DB; fast full-text search (<100ms)
   → See [.claude/rules/storage.md](../.claude/rules/storage.md)

6. **Claude 3.5 Sonnet** – Respects rate limits; exponential backoff retries
   → See [.claude/rules/assess.md](../.claude/rules/assess.md)

7. **Typer CLI** – Async-ready, type hints, sub-command organization
   → See [.claude/rules/cli.md](../.claude/rules/cli.md)

---

## Multi-Agent Governance

Roles: Architect (design), Coder (implement), Reviewer (test).

**See [AGENTS.md](../AGENTS.md)** for:
- Role responsibilities & boundaries
- Handover protocol (tasks.md → code → tests)
- Three-Strike Rule (error escalation)
- Permission matrix

---

## Configuration Files

All instruction files auto-load based on context:

```
CLAUDE.md                          # Core rules (quick reference)
AGENTS.md                          # Agent roles & governance
.claude/settings.json              # Model tier pinning, permissions
.claude/rules/
  ├── crawl.md                     # Playwright patterns
  ├── preprocess.md                # MarkItDown, spaCy, chunking
  ├── verify.md                    # Interactive CLI, cost transparency
  ├── assess.md                    # Claude API, prompts
  ├── storage.md                   # SQLite, FTS5, queries
  ├── cli.md                       # Typer patterns
  ├── multi-agent.md               # Phase-specific coordination
  └── tui.md                       # Text UI patterns (Textual)
.github/instructions/
  ├── cli-usage.instructions.md    # CLI commands, flags, examples
  └── code-patterns.instructions.md # Pydantic, async, type hints
```

See [DESIGN.md](../DESIGN.md) for file organization rationale.

---

## Testing & Verification

```bash
# Run all tests
uv run pytest tests/ -v --cov=src

# Quick checks
uv run black src/ tests/           # Format
uv run ruff check src/ tests/      # Lint
uv run mypy src/                   # Type check

# Watch logs
tail -f logs/app.log
```

See [CLAUDE.md § Verification Commands](../CLAUDE.md#verification-commands) for full list.

---

## Troubleshooting

Common issues and solutions: See [docs/COMPATIBILITY.md](../docs/COMPATIBILITY.md)

---

## Getting Help

- Questions about commands? → [CLAUDE.md § Quick Workflow](../CLAUDE.md#quick-workflow)
- Questions about architecture? → [DESIGN.md](../DESIGN.md)
- Questions about implementation? → Read `.claude/rules/*` for phase-specific guidance
- Questions about roles/governance? → [AGENTS.md](../AGENTS.md)

---

**Last Updated**: 2026-07-10
**Configuration Status**: Progressive Disclosure (minimal bloat, maximum clarity)
