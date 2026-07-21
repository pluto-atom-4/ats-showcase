# CLAUDE.md

ATS Playground: CV-to-jobs assessment system. Crawls career pages, preprocesses HTML, sends to Claude for scoring.

---

## NEVER DO THIS

- **Don't assess unconfirmed jobs**: Use `--confirmed-only` (default) to filter status
- **Don't run multiple assessment processes concurrently**: SQLite single-writer. Use queue/single-process
- **Don't send raw HTML to Claude**: Always preprocess (clean + chunk). Raw HTML ~6,000 tokens per job
- **Don't skip verification**: Always show user cost estimate before API calls
- **Don't force uniform token counts in chunks**: Splits at sentence boundaries (spaCy). Chunks vary 100–600 tokens intentionally
- **Don't re-assess already reviewed jobs**: Use pipeline control flags (--skip-assessed, --skip-rejected) to skip jobs
- **Don't commit directly to main**: All changes must go through feature branches. Pre-commit hook enforces this.

---

## Git Workflow (Enforced)

Feature branches only. Pre-commit hook blocks direct `main` commits.

```bash
git checkout -b feat/issue-XXX-description
git commit -m "message"
git push -u origin feat/issue-XXX-description
```

Setup: `bash .claude/skills/pre-commit-enforce/setup.sh`. See [docs](https://github.com/pluto-atom-4/pre-commit-enforce-skill).

---

## Setup

```bash
uv sync
uv run python -m spacy download en_core_web_md
uv run playwright install chromium
cp .env.example .env  # Set ANTHROPIC_API_KEY
uv run python src/storage/db.py --init
```

---

## Quick Workflow

```bash
# Full pipeline (Sonnet, $3/$15 per 1M)
uv run python -m src.cli all --cv data/cv.json --config config/companies.json

# Cheaper version (Haiku, $0.80/$4 per 1M)
uv run python -m src.cli all --cv data/cv.json --config config/companies.json --model haiku

# Stop before assess (cost verify)
uv run python -m src.cli all --cv data/cv.json --config config/companies.json --up-to review
```

See [CLI reference](.github/instructions/cli-usage.instructions.md) for all commands.

---

## Verification Commands

```bash
uv run pytest tests/ -v                          # All tests
uv run pytest tests/ -v --cov=src               # With coverage
uv run black src/ tests/ && uv run ruff check src/ tests/ --fix  # Format + lint
uv run python -m src.cli query --keyword "python" --min-score 75  # Query DB
uv run python -m src.cli stats --show-token-usage              # Cost breakdown
tail -f logs/app.log                             # Watch logs
```

---

## Phase-Specific Rules

Read phase-specific guidance in `.claude/rules/`:

- **Crawl**: [crawl.md](.claude/rules/crawl.md) – Playwright, CSS selectors, rate limiting
- **Preprocess**: [preprocess.md](.claude/rules/preprocess.md) – MarkItDown, spaCy chunking, token counting
- **Verify**: [verify.md](.claude/rules/verify.md) – Interactive CLI, cost transparency, status flow, re-review
- **Assess**: [assess.md](.claude/rules/assess.md) – Claude API, prompts, rate limiting, error handling
- **Storage**: [storage.md](.claude/rules/storage.md) – SQLite schema, FTS5, markdown export
- **CLI**: [cli.md](.claude/rules/cli.md) – Typer patterns, command organization
- **Multi-Agent**: [multi-agent.md](.claude/rules/multi-agent.md) – Phase coordination across agent roles

---

## Workflows

- **Crawl + Preprocess**: `.claude/skills/crawl-jobs/SKILL.md`
- **Review + Assess**: `.claude/skills/assess-jobs/SKILL.md`

---

## Context File Maintenance

Automated token budget validation in `.github/workflows/context-lint.yml`. See [maintenance guide](docs/dev-note/ai-config-maintenance.md).

## Docs & Help

- **Architecture**: [DESIGN.md](DESIGN.md)
- **Phase rules**: [.claude/rules/](#phase-specific-rules)
- **CLI reference**: [.github/instructions/cli-usage.instructions.md](.github/instructions/cli-usage.instructions.md)

---

**Status**: Progressive Disclosure (minimal bloat, maximum clarity)
**Last Updated**: 2026-07-21 (trimmed for token budget)
