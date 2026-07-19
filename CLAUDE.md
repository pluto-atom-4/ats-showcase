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

**Feature Branch Workflow**: All commits must go through feature branches. Direct commits to `main` are blocked by a pre-commit hook.

**Proper workflow:**
```bash
# 1. Create feature branch
git checkout -b feat/issue-XXX-description

# 2. Commit changes
git commit -m "message"

# 3. Push branch
git push -u origin feat/issue-XXX-description

# 4. Create PR on GitHub
# 5. Merge via PR (never direct push to main)
```

**Why**: Enforces code review, CI checks, and team visibility before merging.

**If you see "Direct commits to main are not allowed"**: Create a feature branch and cherry-pick your commit:
```bash
git branch feat/recover-commit
git checkout feat/recover-commit
git reset HEAD~1  # Undo commit on main
git checkout main
git reset --hard origin/main  # Restore main to remote
```

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
# Full pipeline (default: Sonnet model, $3/$15 per 1M tokens)
uv run python -m src.cli all --cv data/cv.json --config config/companies.json

# Full pipeline with Haiku (95% cheaper, $0.80/$4 per 1M)
uv run python -m src.cli all --cv data/cv.json --config config/companies.json --model haiku

# Full pipeline with Opus (most capable, $15/$75 per 1M)
uv run python -m src.cli all --cv data/cv.json --config config/companies.json --model opus

# Step-by-step
uv run python -m src.cli crawl --config config/companies.json
uv run python -m src.cli preprocess --show-estimates
uv run python -m src.cli review --interactive                           # Basic review
uv run python -m src.cli review --interactive --model haiku             # Show Haiku costs
uv run python -m src.cli review --interactive --cost-limit 0.05         # Warn if > $0.05
uv run python -m src.cli assess --cv data/cv.json --model sonnet
uv run python -m src.cli export --output data/assessments/report.md
```

**Model options** (aliases or full IDs):
- `haiku` or `claude-haiku-4-5-20251001` – Fast, cheap ($0.80/$4 per 1M)
- `sonnet` or `claude-sonnet-5` – Balanced ($3/$15 per 1M, default)
- `opus` or `claude-opus-4-8` – Most capable ($15/$75 per 1M)

**Command reference**: See [.github/instructions/cli-usage.instructions.md](.github/instructions/cli-usage.instructions.md)

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

## Tech Stack

- **Browser**: Playwright (async, JS rendering)
- **HTML cleaning**: MarkItDown (primary), BeautifulSoup (fallback)
- **NLP**: spaCy (sentence segmentation)
- **Tokens**: tiktoken (estimates), Claude API (actual)
- **DB**: SQLite with FTS5 full-text search
- **LLM**: Claude (configurable via --model flag):
  - Haiku (default for cost): $0.80/$4.0 per 1M (95% savings)
  - Sonnet (default): $3.0/$15.0 per 1M (80% savings)
  - Opus: $15.0/$75.0 per 1M (best accuracy)
- **CLI**: Typer (async-ready)

---

## Docs Map

- **Architecture**: [DESIGN.md](DESIGN.md)
- **Agent Roles**: [AGENTS.md](AGENTS.md)
- **Code Patterns**: [.github/instructions/code-patterns.instructions.md](.github/instructions/code-patterns.instructions.md)
- **Copilot**: [.github/copilot-instructions.md](.github/copilot-instructions.md)
- **Config Audit**: [docs/dev-note/chore-124-config-audit.md](docs/dev-note/chore-124-config-audit.md)

---

## Getting Help

- **Command syntax?** → [.github/instructions/cli-usage.instructions.md](.github/instructions/cli-usage.instructions.md)
- **Code patterns?** → [.github/instructions/code-patterns.instructions.md](.github/instructions/code-patterns.instructions.md)
- **Agent roles?** → [AGENTS.md](AGENTS.md)
- **Phase details?** → [.claude/rules/](#phase-specific-rules) (links above)
- **Troubleshooting?** → [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md)

---

**Status**: Progressive Disclosure (minimal bloat, maximum clarity)
**Last Updated**: 2026-07-18 (model selection feature added)
