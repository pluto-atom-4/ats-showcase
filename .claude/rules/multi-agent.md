# Multi-Agent Phase Coordination

Phase-specific agent coordination patterns for ATS Playground workflow. How Architect, Coder, and Reviewer agents collaborate during crawl, preprocess, assess, and export phases.

---

## Crawl Phase Coordination

### Architect Role
- Define CSS selectors in `config/companies.json`
- Validate selector accuracy (test in browser DevTools first)
- Plan rate limiting strategy (crawl_delay per company)
- Document edge cases (JavaScript-heavy sites, login walls)

### Coder Role
- Implement `BrowserManager` + `Crawler` async loops
- Handle Playwright browser lifecycle (open/close)
- Implement fallback selectors if primary fails
- Add error handling for network timeouts, 429 responses
- Log extraction stats (jobs found, errors, time)

### Reviewer Role
- Verify crawled HTML is stored correctly
- Check extraction rate (should match expected job count)
- Test edge cases (pagination, dynamic loading, rate limits)
- Run: `uv run pytest tests/test_crawl.py -v`

**Handoff Artifacts:**
- Architect → Coder: `config/companies.json` with selectors + delays
- Coder → Reviewer: Crawled jobs in database + logs

---

## Preprocess Phase Coordination

### Architect Role
- Decide chunking strategy (target tokens per chunk)
- Document MarkItDown fallback behavior
- Set token count thresholds for cost estimation
- Plan cost transparency (show user estimates)

### Coder Role
- Implement `parse_html()` with MarkItDown primary + BeautifulSoup fallback
- Implement `chunk_by_sentences()` using spaCy (semantic boundaries)
- Implement token counting via tiktoken
- Add cost tracking in database
- Handle edge cases (empty text, missing markup)

### Reviewer Role
- Verify chunk sizes are reasonable (100–600 tokens, not uniform)
- Check cost estimates accuracy (compare tiktoken vs actual Claude tokens)
- Validate clean text quality (no HTML artifacts, readable)
- Run: `uv run pytest tests/test_preprocess.py -v`
- Spot-check output: `uv run python -m src.cli preprocess --show-estimates`

**Handoff Artifacts:**
- Architect → Coder: Chunking strategy + target token count
- Coder → Reviewer: Clean text chunks + token counts in database

---

## Verify (Review) Phase Coordination

### Architect Role
- Define review workflow (interactive prompt → confirm/reject/skip)
- Design cost transparency display (show tokens + USD)
- Specify filtering options (skip-rejected, skip-assessed, mode)
- Document user interaction flow

### Coder Role
- Implement `JobReviewer` with interactive CLI
- Implement filters (mode, skip_rejected, skip_assessed, skip_before_date)
- Implement database persistence (save status='confirmed'/'rejected'/'pending_review')
- Add re-review support (allow changing prior decisions)
- Handle skip action (persist with pending_review status)

### Reviewer Role
- Test interactive prompts (confirm/reject/skip all work)
- Verify status transitions (pending_review → confirmed/rejected)
- Test filtering combinations (mode + skip + date)
- Test re-review workflow (prior decisions display correctly)
- Run: `uv run pytest tests/test_verification.py -v`
- Test manually: `uv run python -m src.cli review --interactive`

**Handoff Artifacts:**
- Architect → Coder: Review workflow specification + filter logic
- Coder → Reviewer: Job review statuses saved to database

---

## Assess Phase Coordination

### Architect Role
- Define assessment prompt structure (CV + job → JSON scores)
- Set score categories (overall, tech, seniority, location)
- Specify filtering (score threshold, mode, date)
- Plan cost tracking (estimated vs actual tokens)

### Coder Role
- Implement `LLMProvider` with Claude 3.5 Sonnet
- Implement retries + rate limiting (exponential backoff)
- Implement assessment prompt formatting
- Validate JSON response parsing
- Implement cost tracking (tokens, USD)
- Add filtering (mode, skip_assessed, score_threshold, since)

### Reviewer Role
- Verify assessment JSON output is valid
- Check score ranges (0–100 for each category)
- Verify cost tracking (estimated vs actual tokens logged)
- Test rate limiting behavior (API should backoff on 429)
- Run: `uv run pytest tests/test_assess.py -v`
- Test manually: `uv run python -m src.cli assess --cv data/cv.json --limit 1`

**Handoff Artifacts:**
- Architect → Coder: Assessment prompt + score categories
- Coder → Reviewer: Assessment results + cost metrics in database

---

## Export Phase Coordination

### Architect Role
- Define report structure (title, summary, job table, sorting)
- Specify sorting + filtering (by score, location, company)
- Design markdown output format
- Plan metadata (date, CV used, total jobs assessed)

### Coder Role
- Implement `export_markdown()` function
- Implement markdown table generation (job data)
- Implement filtering/sorting before export
- Add summary stats (total jobs, avg score, top matches)
- Handle edge cases (no jobs, low scores)

### Reviewer Role
- Verify markdown output is readable (valid formatting)
- Check job sorting (highest scores first)
- Verify summary stats accuracy
- Run: `uv run pytest tests/test_export.py -v`
- Spot-check output: `uv run python -m src.cli export --output data/assessments/report.md && cat data/assessments/report.md`

**Handoff Artifacts:**
- Architect → Coder: Report specification + structure
- Coder → Reviewer: Markdown report + summary stats

---

## Cross-Phase Dependencies

```
CRAWL → PREPROCESS → VERIFY → ASSESS → EXPORT
  ↓        ↓           ↓        ↓        ↓
HTML    Clean+Chunks  Status   Scores  Report
        +Tokens       +DB      +Cost   +Markdown
```

**Database Schema Evolution:**
- After CRAWL: `jobs` table with raw_html, clean_text (empty)
- After PREPROCESS: clean_text, token_count, estimated_cost filled
- After VERIFY: job_reviews table with status (confirmed/rejected/pending_review)
- After ASSESS: job_assessments table with scores, actual_cost
- EXPORT: reads all tables, generates markdown

**Agent Handoff Order:**
1. Architect: designs all phases
2. Coder: implements crawl → preprocess → verify → assess → export
3. Reviewer: tests each phase in sequence
4. Coder: fixes any issues found by Reviewer
5. Reviewer: final verification before release

---

## Error Escalation per Phase

### Crawl Errors
- **Network timeout (3×)** → Escalate to Architect (check selectors or crawl_delay)
- **Invalid selector** → Log + skip job, continue crawl
- **Rate limited (429)** → Backoff built-in; if persists, increase crawl_delay

### Preprocess Errors
- **HTML parse failure (3×)** → Escalate to Architect (markup format changed?)
- **Invalid token count** → Log warning, continue with estimate
- **spaCy model missing** → Check `uv run python -m spacy download en_core_web_md`

### Verify Errors
- **Database locked** → Wait + retry (SQLite single-writer)
- **Invalid status value** → Escalate to Architect (enum changed?)
- **Circular re-review** → If user confirms/rejects 5× same job, escalate

### Assess Errors
- **API rate limit (429)** → Backoff built-in; monitor for patterns
- **Invalid JSON response (3×)** → Escalate to Architect (prompt may need update)
- **API auth error (401)** → Check ANTHROPIC_API_KEY immediately

### Export Errors
- **Permission denied on output file** → Check file permissions
- **Markdown encoding error** → Log + use fallback encoding
- **Database query fails** → Check schema (all tables exist?)

---

## Communication Protocol

### Architect → Coder (via tasks.md + comments)
```
- Design decision: "Use semantic chunking at sentence boundaries"
- Context: "spaCy has built-in sentence segmentation"
- Acceptance criteria: "Chunks should be 100–600 tokens"
```

### Coder → Reviewer (via PR + commit)
```
- Implementation complete: "Added save_review() method"
- Testing done: "Unit tests pass (8/8)"
- Ready for review: "Needs database schema validation"
```

### Reviewer → Coder (via test output + issues)
```
- Test failure: "test_skip_persists_across_sessions failed"
- Root cause: "skip action not calling save_review()"
- Fix: "Add _handle_skip_action() method"
```

---

## Single-Writer Database Rule

**Only one phase can write to database at a time.**

- Crawl → Preprocess → Verify → Assess → Export (sequential by phase)
- Within a phase: Multiple Coder tasks may write (handled by Typer async)
- If conflict: Add database lock (SQLite) or use task queue

**Implementation:**
```python
def acquire_db_lock(phase: str) -> None:
    """Acquire exclusive database lock for phase."""
    # TODO: Implement database locking if concurrent writes needed
    pass
```

---

## Status

- Created: 2026-07-10
- Phase Coordination: Ready
- Referenced in: AGENTS.md, CLAUDE.md § Workflows
