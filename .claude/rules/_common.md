# Shared Patterns & Templates

Reusable error handling, verification commands, and patterns across all phases.

---

## Error Handling Pattern

### Transient Error Handling (API)

```python
# Max 3 attempts with exponential backoff
# Waits: 2s, then 4s, then 8s before retrying
try:
    response = await llm_provider.call(...)
except RateLimitError:  # 429
    # Backoff → retry
    await asyncio.sleep(2 ** attempt)
except ServerError:  # 500, 502, 503
    # Backoff → retry
    await asyncio.sleep(2 ** attempt)
except AuthError:  # 401
    # Fail immediately, check API key
    raise
```

### Crawl-Phase Error Handling

- **Page timeout**: Increase timeout in config, check selectors
- **Login required**: Move to config; don't automate login in code
- **Rate limited (429)**: Backoff strategy built in; wait & retry
- **Invalid selector**: Logs error, skips job, continues crawling

---

## Verification Commands Template

### Preprocessing (Token Estimates)

```bash
# Token estimates for all jobs
uv run python -m src.cli preprocess --show-estimates

# Query by keyword
uv run python -m src.cli query --keyword "python" --min-score 0

# Run tokenization tests
uv run pytest tests/tokenization/ -v
```

### Assessment (API)

```bash
# Assess confirmed jobs for a CV
uv run python -m src.cli assess --cv data/cv.json

# Show token usage stats
uv run python -m src.cli stats --show-token-usage

# Test on one job (for debugging)
uv run python -m src.cli assess --cv data/cv.json --limit 1
```

### Crawling (Extraction)

```bash
# Test crawler on single config
uv run python -m src.cli crawl --config config/companies.json

# Crawl entire directory
uv run python -m src.cli crawl --config-dir ./config

# Watch logs for errors
tail -f logs/app.log
```

### Verification (Interactive)

```bash
# Interactive review (shows each job, prompts confirm/reject)
uv run python -m src.cli review --interactive

# Show cost estimates for pending jobs
uv run python -m src.cli preprocess --show-estimates

# Query by status
uv run python -m src.cli query --keyword "python" --status confirmed
```

### Database

```bash
# Initialize database
uv run python src/storage/db.py --init

# Export markdown report
uv run python -m src.cli export --output data/assessments/report.md

# Query database
uv run python -m src.cli query --keyword "python" --min-score 75

# Show stats (job count, avg score)
uv run python -m src.cli stats --show-token-usage
```

### Testing & Quality

```bash
# Pre-commit checks + mypy
bash .claude/scripts/run-local-ci.sh

# All tests
uv run pytest tests/ -v

# With coverage
uv run pytest tests/ -v --cov=src
```

---

## Cost Transparency Pattern

**Always log before LLM calls:**

```
Title: Senior Python Developer
Location: Remote
Estimated tokens: 650
Estimated cost: $0.002
Proceed? [y/n]
```

**Track after assessment:**

```python
{
  "job_id": "...",
  "estimated_tokens": 650,
  "actual_tokens": 673,
  "estimated_cost": 0.00195,
  "actual_cost": 0.00202,
  "api_call_time_ms": 1250
}
```

Compare actual vs estimated. Use for future token prediction refinement.

---

## Database Access Pattern

**Always use JobStore for queries (never raw SQL):**

```python
from src.storage.db import JobStore

store = JobStore("data/ats_playground.db")

# Query by keyword
results = store.query_by_keyword("python", min_score=75)

# Get assessment for job
assessment = store.get_assessment(job_id)

# Update job status
store.update_job_status(job_id, "confirmed")
```

---

## Async Context Manager Pattern

**Always use for resource cleanup:**

```python
# Good: Ensures cleanup even if errors occur
async with BrowserManager() as browser:
    jobs = await browser.fetch_jobs(config)

# Good: Ensures proper state management
async with LLMProvider(api_key=...) as provider:
    assessment = await provider.assess_job(cv, job)
```

---

**Last Updated:** 2026-08-09 (Issue #245 Phase A)
