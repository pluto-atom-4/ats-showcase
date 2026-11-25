# CONVENTIONS.md – Code Style, Testing & Deployment

**Table of Contents**
- [Code Style Guide](#code-style-guide)
- [Testing Strategy](#testing-strategy)
- [Git & Commit Workflow](#git--commit-workflow)
- [Documentation Standards](#documentation-standards)
- [Troubleshooting & Common Errors](#troubleshooting--common-errors)

---

## Code Style Guide

### Python Version & Tools

**Target**: Python 3.12+
**Package manager**: `uv` (faster than pip)
**Type checking**: `mypy` (non-strict by default; `run-local-ci.sh --strict` available)
**Linting**: `ruff` (Rust-based, faster than flake8)
**Formatting**: `black` (opinionated, uncompromising)
**Testing**: `pytest` with `pytest-cov` + `pytest-asyncio`

### Project Structure

```
src/
├── __init__.py        (empty or version string)
├── cli.py             (main entry point)
├── assessment/
├── browser/
├── config/
├── formatters/
├── id_generation/
├── integrity/
├── llm/
├── models/
├── nlp/
├── parsers/
├── poc/
├── preprocessing/
├── setup/
├── storage/
├── tokenization/
├── tui/
└── verification/

tests/
├── __init__.py
├── conftest.py        # Shared fixtures
├── test_*.py          # Top-level tests
├── assessment/        # assessment/ module tests
├── browser/           # browser/ module tests
├── cli/               # CLI tests
├── llm/               # llm/ module tests
├── parsers/           # parsers/ module tests
├── poc/               # poc/ module tests
├── preprocessing/     # preprocessing/ module tests
├── scripts/           # tooling script tests
├── storage/           # storage/ module tests
├── tokenization/      # tokenization/ module tests
└── tui/               # tui/ module tests

.github/
├── workflows/
│   ├── config-validation.yml
│   ├── context-lint.yml
│   ├── dependency-review.yml
│   └── quality-checks.yml
├── instructions/
├── ISSUE_TEMPLATE/
├── copilot-instructions.md  (quick-start)
└── dependabot.yml
```

### Naming Conventions

Names in this section are illustrative, not the real API.

**Modules**: `snake_case` (crawler.py, llm_client.py)
**Classes**: `PascalCase` (Crawler, LLMProvider, JobStore)
**Functions**: `snake_case` (clean_html, count_tokens)
**Constants**: `UPPER_SNAKE_CASE` (MAX_RETRIES, DEFAULT_TIMEOUT)
**Private**: `_leading_underscore` (_internal_helper, _parse_html)
**Models**: `PascalCase` pydantic classes in `src/models/` (JobPosting, PreprocessedJob, Assessment)
**Type hints**: Always required (mypy; strict via `run-local-ci.sh --strict`)

```python
# GOOD
class Crawler:
    MAX_RETRIES = 5
    DEFAULT_TIMEOUT = 30

    async def crawl_company(self, url: str) -> list[JobPosting]:
        pass

# BAD
class crawler:  # lowercase class
    def crawlCompany(self, url):  # camelCase method
        MAX_TIMEOUT = 30  # constant in method
        pass
```

### Type Hints & Dataclasses

Use pydantic models for `src/models/` (`JobPosting`, `PreprocessedJob`, `Assessment`); validation runs on construction. Use `dataclasses` for internal types in preprocessing, storage, and TUI code:

```python
from src.models.job import JobPosting

# Invalid url or missing title raises pydantic.ValidationError
job = JobPosting(
    title="Senior Python Engineer",
    company="Acme",
    url="https://acme.com/jobs/123",
    description="Build and maintain crawlers.",
)
```

### Error Handling

Names in this section are illustrative, not the real API.

**Prefer specific exceptions**:

```python
# GOOD
class JobCrawlerError(Exception):
    """Base class for crawler errors."""
    pass

class SelectorNotFoundError(JobCrawlerError):
    """CSS selector did not match any elements."""
    pass

class BrowserTimeoutError(JobCrawlerError):
    """Browser operation exceeded timeout."""
    pass

# Usage
try:
    job = await crawler.extract_job(url)
except SelectorNotFoundError as e:
    logger.warning(f"Selector failed for {url}: {e}")
    # fallback or retry
except BrowserTimeoutError as e:
    logger.error(f"Browser timeout for {url}: {e}")
    # increase timeout or skip
except JobCrawlerError as e:
    logger.error(f"Unexpected crawler error: {e}", exc_info=True)
    raise

# BAD
except Exception:  # too broad
    pass
```

### Logging

Use `structlog` or standard `logging` module:

```python
import logging

logger = logging.getLogger(__name__)

# Info: normal flow
logger.info("Starting crawl for company", extra={"company": "acme"})

# Warning: recoverable issue
logger.warning("Selector mismatch, retrying", extra={"attempt": 2})

# Error: failure, but process continues
logger.error("Claude API error", extra={"status": 429, "retry_after": 60})

# Critical: process cannot continue
logger.critical("Database corrupted, cannot continue", exc_info=True)
```

### Async/Await Patterns

Use `asyncio` for I/O-bound operations (crawl, API calls). Names in this section are illustrative, not the real API.

```python
import asyncio
from typing import Coroutine

from src.models.job import JobPosting

# Good: concurrent requests
async def crawl_companies(companies: list[str]) -> list[JobPosting]:
    tasks = [crawl_company(company) for company in companies]
    return await asyncio.gather(*tasks, return_exceptions=True)

# Good: resource pooling
async with BrowserPool(max_size=5) as pool:
    tasks = [pool.get().extract_job(url) for url in urls]
    results = await asyncio.gather(*tasks)

# Good: timeout protection
try:
    result = await asyncio.wait_for(api_call(), timeout=30)
except asyncio.TimeoutError:
    logger.error("API call exceeded 30s timeout")
    raise
```

---

## Testing Strategy

### Test Structure

Tests live under `tests/`, grouped by area in subdirectories (for example `tests/browser/` and `tests/storage/`), with some top-level `tests/test_*.py` files and shared fixtures in `tests/conftest.py`. See [Project Structure](#project-structure) for the layout.

### Unit Testing

**Principle**: Test business logic, mock I/O

```python
import pytest
from unittest.mock import patch, MagicMock
from src.tokenization.counter import TokenCounter

class TestTokenCounter:
    def test_count_tokens_basic(self):
        counter = TokenCounter()
        text = "Hello world"
        count = counter.count_tokens(text)
        assert count > 0
        assert isinstance(count, int)

    def test_count_tokens_empty(self):
        counter = TokenCounter()
        count = counter.count_tokens("")
        assert count == 0

    @patch("tiktoken.get_encoding")
    def test_loads_cl100k_base_encoding(self, mock_get_encoding):
        TokenCounter()
        mock_get_encoding.assert_called_with("cl100k_base")
```

### Integration Testing

**Principle**: Test phase boundaries with real data

```python
import pytest
from src.browser.crawler import Crawler
from src.parsers.html_to_markdown import clean_html

SELECTORS = {
    "job_container": ".job-posting",
    "title": ".job-title",
    "location": ".job-location",
    "link": "a.job-link",
}

@pytest.mark.asyncio
async def test_crawl_and_clean():
    """Test crawl output feeds into the preprocess cleaning step."""
    crawler = Crawler(headless=True)
    try:
        jobs = await crawler.crawl_company(
            "Acme",
            "https://acme.com/jobs",
            SELECTORS,
            crawler_config={"fetch_detail": True},
        )
    finally:
        await crawler.close()

    assert jobs
    cleaned = clean_html(jobs[0].description)
    assert isinstance(cleaned, str)
    assert len(cleaned) > 0
    assert "<script>" not in cleaned  # tags removed
```

### E2E Testing

**Principle**: Test full workflow with real services (staging)

```python
import json
from pathlib import Path

from typer.testing import CliRunner

from src.cli import app

def test_crawl_and_preprocess_e2e(tmp_path: Path) -> None:
    """Test crawl → preprocess via the CLI; stops before any paid API call."""
    # Hazard: runs a live crawl and writes data/ats_playground.db relative to the CWD; use a scratch CWD
    config_path = tmp_path / "companies.json"
    config_path.write_text(json.dumps({
        "companies": {
            "Acme": {
                "enabled": True,
                "name": "Acme",
                "url": "https://acme.com/jobs",
                "selectors": {
                    "job_container": ".job-posting",
                    "title": ".job-title",
                    "location": ".job-location",
                    "link": "a.job-link",
                },
                "crawler": {"fetch_detail": False},
            }
        }
    }))
    cv_path = tmp_path / "cv.json"
    cv_path.write_text("{}")

    runner = CliRunner()
    result = runner.invoke(app, [
        "all", "--cv", str(cv_path), "--config", str(config_path),
        "--no-tui", "--up-to", "preprocess",
    ])
    assert result.exit_code == 0
```

### Mocking & Fixtures

Use `conftest.py` for shared fixtures:

```python
# tests/conftest.py
import json

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.models.job import JobPosting

@pytest.fixture
def mock_browser():
    """Mock Playwright browser."""
    browser = AsyncMock()
    context = AsyncMock()
    page = AsyncMock()

    browser.new_context.return_value = context
    context.new_page.return_value = page
    page.goto.return_value = None
    page.query_selector.return_value = MagicMock(inner_html="<div>Job Title</div>")

    return browser

@pytest.fixture
def mock_claude_response():
    """Mock Claude API response."""
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps({
                    "match_score": 85,
                    "strengths": ["Python", "SQL"],
                    "gaps": ["Kubernetes"],
                    "recommendation": "STRONG_MATCH"
                })
            }
        ],
        "usage": {
            "input_tokens": 1400,
            "output_tokens": 350
        }
    }

@pytest.fixture
def job_posting_sample():
    """Sample job posting from crawl phase."""
    return JobPosting(
        title="Senior Python Engineer",
        company="Acme",
        url="https://acme.com/jobs/123",
        description="<p>Build and maintain crawlers.</p>",
    )
```

### Coverage Requirements

**Target**: 80%+ line coverage, 70%+ branch coverage

```bash
# Run tests with coverage
pytest tests/ --cov=src --cov-report=term-missing

# Generate HTML report
pytest tests/ --cov=src --cov-report=html
# Open htmlcov/index.html
```

---

## Git & Commit Workflow

### Branch Naming

```
feature/add-slack-integration    # New feature
bugfix/fix-rate-limit-crash      # Bug fix
docs/update-architecture         # Documentation
refactor/simplify-tokenizer      # Code improvement
chore/upgrade-dependencies       # Dependency updates
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
**Scope**: Module name (optional but recommended)
**Subject**: Imperative, 50 chars max, lowercase
**Body**: Why, not what (optional, 72 chars wrap)
**Footer**: References (e.g., Fixes #123)

```bash
# Good commits
git commit -m "feat(cli): add --mock flag to crawl command"
git commit -m "fix(llm): handle 429 rate limit with exponential backoff

The assess command would crash on rate limit errors.
Now queues jobs and retries with jitter."
git commit -m "docs(architecture): update scaling considerations

Fixes #45"

# Bad commits
git commit -m "updated stuff"
git commit -m "WIP"
git commit -m "asdasdasd"
```

### Pull Request Process

1. **Create branch**: `git checkout -b feature/my-feature`
2. **Make changes** & test locally:
   ```bash
   uv sync
   pytest tests/ -v
   black src/ tests/
   ruff check src/ tests/
   mypy src/ tests/
   ```
3. **Push & create PR**:
   ```bash
   git push origin feature/my-feature
   # Open PR on GitHub with template
   ```
4. **Automated checks** (CI/CD):
   - Tests pass ✅
   - Linting passes ✅
   - Coverage maintained ✅
   - No secrets detected ✅
5. **Code review** (require 1+ approval)
6. **Squash & merge** to main

### PR Template

```markdown
## Description
Brief explanation of changes.

## Related Issue
Fixes #123

## Type of Change
- [ ] Feature
- [ ] Bug fix
- [ ] Documentation

## Testing
How did you test? Provide commands or screenshots.

## Checklist
- [ ] Lint passes: `ruff check src/`
- [ ] Type check: `mypy src/ tests/`
- [ ] Tests pass: `pytest tests/ -v`
- [ ] Coverage maintained: `--cov-report=term`
- [ ] Docs updated (if applicable)
```

---

## Documentation Standards

### Doc Format

All docs in `docs/` use **GitHub-flavored Markdown**:

```markdown
# Heading 1 (title only, once per file)

## Heading 2 (major sections)

### Heading 3 (subsections)

**Bold** for emphasis
`code` for inline code
```code block``` for multi-line

- Bullet lists
  - Nested bullets

1. Numbered lists
2. For procedures
```

### Code Examples

Always include:
- Function signature (with type hints)
- Brief explanation
- Expected output or side effects

```python
# Example: Extracting jobs from one company career page
from src.browser.crawler import Crawler

selectors = {
    "job_container": ".job-posting",
    "title": ".job-title",
    "location": ".job-location",
    "link": "a.job-link",
}
crawler = Crawler(headless=True)
try:
    jobs = await crawler.crawl_company("Acme", "https://acme.com/jobs", selectors)
finally:
    await crawler.close()
# Output: list[JobPosting]
```

### Table Format

Use pipe-delimited tables with alignment:

```markdown
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Left     | Center   | Right    |
| aligned  | aligned  | aligned  |
```

### Cross-References

Link to other docs:

```markdown
See [CRAWL.md](./CRAWL.md#adding-new-companies) for CSS selector help.
See [docs/STORAGE.md](./STORAGE.md#querying-results) for query examples.
```

### Updating Docs

When code changes:
1. Update relevant phase doc (CRAWL.md, ASSESS.md, etc.)
2. Update examples & code blocks
3. Update `.github/copilot-instructions.md` if top-level command changed
4. Commit with message: `docs: update <module> for <change>`

---

## Troubleshooting & Common Errors

### Playwright Browser Issues

**Error**: `BrowserTypeError: Chromium is not installed`

**Solution**:
```bash
# Install system dependencies
sudo apt-get install -y chromium  # Ubuntu/Debian
brew install chromium             # macOS

# Or use Playwright's installer
python -m playwright install chromium
```

### spaCy Model Issues

**Error**: `OSError: [E050] Can't find model 'en_core_web_md'`

**Solution**:
```bash
# Download model
python -m spacy download en_core_web_md

# Or specify in config
export SPACY_MODEL="en_core_web_sm"  # lighter model
python -m src.cli crawl
```

### Claude API Rate Limits

**Error**: `RateLimitError: 429 Too Many Requests`

**Solution**:
- Already handled in `src/llm/provider.py` (`LLMProvider`) with exponential backoff
- Monitor cost tracking: `python -m src.cli stats --show-token-usage`
- Reduce job count per run: `python -m src.cli assess --cv data/cv.json --limit 5`

### Import Errors

**Error**: `ModuleNotFoundError: No module named 'src.llm'`

**Solution**:
```bash
# Ensure PYTHONPATH is set
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or run via module
python -m src.cli --help
# (not python src/cli.py)
```

### Type Check Failures

**Error**: `error: Argument "selectors" to "crawl_company" of "Crawler" has incompatible type "str"; expected "Dict[str, str]"`

**Solution**:
- Use proper types for all function arguments
- Run type check locally before committing: `mypy src/ tests/`
- Update function signature or cast value

### Test Failures

**Error**: `AssertionError: assert 0.95 == 0.96`

**Solution**:
- Use `pytest.approx()` for floating-point comparisons
- Use `assert result == expected` for exact matches
- Run `pytest -vv` for detailed output
- Check fixture data under the relevant module's fixtures directory (e.g. `tests/preprocessing/fixtures/`)

---

## Quick Reference: Common Commands

```bash
# Setup
uv sync
python -m spacy download en_core_web_md

# Development
python -m src.cli crawl --help
# Show assess options
python -m src.cli assess --help

# Testing
pytest tests/ -v
pytest tests/ -v --cov=src
pytest tests/test_llm.py -v

# Linting
black src/ tests/
ruff check src/ tests/
mypy src/ tests/

# Git
git checkout -b feature/my-feature
git commit -m "feat(cli): add new command"
git push origin feature/my-feature
```
