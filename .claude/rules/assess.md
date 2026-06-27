# Assess Phase Rules

Claude API integration, prompt design, rate limiting, error handling, cost tracking.

## Claude API Client Pattern

**Never hardcode API calls.** Use LLMProvider abstraction:

```python
from src.llm.provider import LLMProvider

provider = LLMProvider(api_key=os.getenv("ANTHROPIC_API_KEY"))
assessment = await provider.assess_job(cv_text, job_text)
```

**Provider interface:**
- `assess_job(cv, job)` → `Assessment` object
- Includes rate limiting, retries, token tracking
- Returns assessment + metadata (tokens used, cost)

## Prompt Design

**Assessment prompt structure:**
1. System: "You are an expert recruiter. Assess CV fit for this job."
2. Context: CV text + job description
3. Output format: JSON with match_score, categories, reasoning

**Example categories:**
- Technical skills match (0–100)
- Seniority alignment (0–100)
- Location preferences (yes/no)
- Overall fit (0–100)

**Always validate JSON output** before storing.

## Rate Limiting & Retries

**Claude limits:**
- ~10 RPM (requests per minute)
- ~50k TPM (tokens per minute)

**Retry strategy (built into LLMProvider):**
```python
# Max 3 attempts with exponential backoff
# Waits: 2s, then 4s, then 8s before retrying
```

**Catch transient errors:**
- 429 (rate limit): Backoff → retry
- 500, 502, 503 (server error): Backoff → retry
- 401 (auth): Fail immediately, check API key

## Cost Tracking

**Always log:**
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

## Verification Commands

```bash
# Assess confirmed jobs for a CV
uv run python -m src.cli assess --cv data/cv.json

# Show token usage stats
uv run python -m src.cli stats --show-token-usage

# Test on one job (for debugging)
uv run python -m src.cli assess --cv data/cv.json --limit 1
```

## Important Notes

- **Don't assess unconfirmed jobs**: Use `--confirmed-only` (default) to filter.
- **API key required**: Set `ANTHROPIC_API_KEY` in `.env`. Loaded automatically.
- **Cost estimates may differ**: tiktoken vs Claude's actual token count. Logged in cost_tracking.
