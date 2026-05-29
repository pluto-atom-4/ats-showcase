# Issue #19 Phase 4: CV-Based Job Assessment

**Phase**: 4 of 5
**Status**: Planning
**Objective**: Implement Claude 3.5 Sonnet API integration to assess user CV fit for confirmed jobs
**Estimated Time**: 40-50 minutes
**Dependencies**: Phase 1 ✅, Phase 2 ✅, Phase 3 ✅

---

## Overview

Phase 4 transforms preprocessed, user-confirmed job postings into AI-powered CV fit assessments. For each confirmed job, we send preprocessed job data to Claude 3.5 Sonnet, which scores the match across multiple dimensions (technical skills, seniority level, location preference, etc.) and provides actionable recommendations.

**Key Value**: Automates the manual job screening process—users get ranked recommendations instead of reading 20+ job descriptions.

**Cost Model**:
- Estimated: ~$0.002 per job (Phase 2 estimate)
- Actual: ~20 jobs × $0.002 = $0.040 after Phase 3 filtering
- Savings vs. unfiltered: 23% ($0.012 saved)

**Architecture**:
```
Confirmed Jobs (Phase 3 output)
    ↓
Claude 3.5 Sonnet API
    ├─ Input: Preprocessed job chunks (~700 tokens)
    ├─ Prompt: CV fit assessment by category
    ├─ Output: Scores + recommendations
    └─ Token tracking: Actual vs. estimated
    ↓
Assessment Results
    ├─ job_id, overall_score, category_scores
    ├─ recommendations, summary
    ├─ actual_tokens, actual_cost
    └─ assessed_date
    ↓
Database (job_assessments table)
```

---

## Phase 4 Tasks Breakdown

### Task 4.1: Implement Claude LLM Provider (25 min)

**Objective**: Create provider abstraction for Claude 3.5 Sonnet API integration.

**Acceptance Criteria**:
- [ ] LLMProvider class with __init__, assess_job() methods
- [ ] Configuration: API key from env, model name, pricing constants
- [ ] Error handling: Retries (max 3) with exponential backoff
- [ ] Rate limiting: Respect Claude limits (~10 RPM, ~50k TPM)
- [ ] Token counting: Track actual tokens from API response
- [ ] Logging: All API calls logged with request/response metadata

**Subtasks**:

1. **Create LLMProvider class** in `src/llm/provider.py` (if not exists)
   - Initialize with API key from `ANTHROPIC_API_KEY` env var
   - Use Anthropic Python SDK: `anthropic.Anthropic(api_key=...)`
   - Store model name: `claude-3-5-sonnet-20241022` (or latest)
   - Define pricing constants:
     - Input: $0.003 per 1M tokens
     - Output: $0.015 per 1M tokens

2. **Implement assess_job() method**
   - Signature: `assess_job(job_id: str, job_chunks: List[str], cv_text: str) -> AssessmentResult`
   - Inputs:
     - `job_id`: ID from job_reviews table
     - `job_chunks`: Preprocessed chunks from Phase 2 (~700 tokens total)
     - `cv_text`: User's CV as raw text
   - Outputs:
     - `AssessmentResult` (Pydantic model):
       - `job_id, overall_score (0-100)`
       - `tech_score, seniority_score, location_score (each 0-100)`
       - `recommendations: List[str]` (e.g., "Learn Kubernetes", "Strengthen Python")
       - `summary: str` (2-3 sentence assessment)
       - `tokens_used: int` (actual from Claude)
       - `actual_cost: float` (calculated from tokens)
       - `assessed_date: datetime`

3. **Error handling with retries**
   - Catch `anthropic.APIConnectionError`, `anthropic.RateLimitError`
   - Retry up to 3 times with exponential backoff: 2^attempt seconds
   - Final attempt failure: Log error, raise exception
   - Example:
     ```python
     for attempt in range(3):
         try:
             response = client.messages.create(...)
             break
         except anthropic.RateLimitError:
             if attempt < 2:
                 wait_time = 2 ** attempt
                 logger.warning(f"Rate limited, retrying in {wait_time}s")
                 time.sleep(wait_time)
             else:
                 raise
     ```

4. **Rate limiting awareness**
   - Add delay between API calls if needed (initially ~1s per call)
   - Log TPM/RPM tracking
   - In production, use queue pattern if scaling beyond ~10 jobs/min

5. **Token tracking**
   - Extract `usage.input_tokens` and `usage.output_tokens` from response
   - Calculate: `total_tokens = input + output`
   - Calculate: `actual_cost = (input × 0.000003) + (output × 0.000015)`
   - Compare to Phase 2 estimate: log variance for metrics

**Implementation Location**: `src/llm/provider.py`
**Lines of Code**: ~120 lines
**Dependencies**: `anthropic`, `src/models/assessment.py`

**Testing**:
- Unit test: Mock Anthropic API, verify assess_job() returns AssessmentResult
- Unit test: Verify retry logic on simulated RateLimitError
- Unit test: Verify token counting and cost calculation

---

### Task 4.2: Design Assessment Prompts (15 min)

**Objective**: Engineer effective prompts that extract structured, actionable assessments.

**Acceptance Criteria**:
- [ ] Main prompt template covers all scoring dimensions
- [ ] Prompt includes user CV context
- [ ] Output format is JSON-parseable
- [ ] Examples provided in prompt for consistency
- [ ] Token count: Prompt + response ~500-800 tokens total

**Subtasks**:

1. **Main Assessment Prompt**
   - Input: CV text (raw or preprocessed)
   - Input: Job chunks (preprocessed from Phase 2)
   - Scoring dimensions:
     - **Tech Skills Match** (0-100): Do they have required technologies?
     - **Seniority Level Match** (0-100): Years of exp vs. role expectations?
     - **Location Fit** (0-100): Remote/on-site preference alignment?
     - **Overall Score** (0-100): Weighted average + gut fit
   - Output format (JSON):
     ```json
     {
       "tech_score": 85,
       "seniority_score": 78,
       "location_score": 60,
       "overall_score": 75,
       "recommendations": ["Learn AWS", "Strengthen DevOps"],
       "summary": "Strong Python/backend skills, but junior on cloud infrastructure..."
     }
     ```

2. **Prompt Template Structure**
   - System: "You are a hiring expert evaluating CV fit for job openings..."
   - Context: Include brief user CV summary (name, key skills, years)
   - Job Data: Full preprocessed job text
   - Instructions: Score each dimension, explain reasoning
   - Format: "Respond with ONLY valid JSON, no extra text"

3. **Example in Prompt**
   - Show 1-2 example assessments in prompt body
   - Demonstrates scoring distribution (high/low/medium)
   - Improves consistency across jobs

4. **Fallback/Error Handling**
   - If Claude refuses or provides malformed JSON: Retry with clearer prompt
   - If still fails: Return AssessmentResult with default scores + error note
   - Log all failures for debugging

**Implementation Location**: `src/llm/prompts.py` (new file)
**Lines of Code**: ~80 lines (template + helpers)
**Format**: Python f-strings or Jinja2 templates

**Example Prompt** (simplified):
```
You are an expert recruiter evaluating job fit based on a candidate's CV.

Candidate CV Summary:
[CV TEXT HERE - ~200 tokens]

Job Opening:
[JOB TEXT HERE - ~500 tokens]

Score the candidate on:
1. Tech Skills Match (0-100): Do they have required technologies?
2. Seniority Match (0-100): Years of experience vs. role level?
3. Location Fit (0-100): Remote/on-site/hybrid alignment?
4. Overall Score (0-100): Holistic fit (weighted: 40% tech, 30% seniority, 30% location)

Provide recommendations for gaps or growth areas.

Respond with valid JSON only:
{
  "tech_score": <0-100>,
  "seniority_score": <0-100>,
  "location_score": <0-100>,
  "overall_score": <0-100>,
  "recommendations": ["gap1", "gap2"],
  "summary": "<2-3 sentence assessment>"
}
```

**Testing**:
- Unit test: Verify prompt template renders correctly
- Unit test: Verify JSON parsing from prompt output
- Integration test: Mock Claude, verify assessment scores populate

---

### Task 4.3: Implement Assessment CLI Command (20 min)

**Objective**: Create `assess-jobs` CLI command to orchestrate Phase 4 workflow.

**Acceptance Criteria**:
- [ ] Command: `uv run python -m src.cli assess assess-jobs`
- [ ] Arguments: `--cv <path>` (required), `--confirmed-only` (default: true)
- [ ] Load confirmed jobs from job_reviews table (Phase 3 output)
- [ ] Load CV from JSON file
- [ ] For each confirmed job: call LLMProvider.assess_job()
- [ ] Display progress: "Assessing 5/20..."
- [ ] Save assessments to database
- [ ] Summary: Total cost, avg score, failures
- [ ] Error handling: Skip failed jobs, continue with others

**Subtasks**:

1. **CLI Command Structure**
   ```python
   @assess_app.command()
   def assess_jobs(
       cv: str = typer.Option(..., help="Path to CV file (JSON or text)"),
       confirmed_only: bool = typer.Option(True, help="Only assess confirmed jobs"),
   ) -> None:
       """Assess user CV fit for confirmed jobs using Claude 3.5 Sonnet."""
   ```

2. **Workflow**
   - Load CV from file (support .json, .txt)
   - Initialize JobReviewer() to get confirmed jobs from DB
   - For each confirmed job:
     a. Retrieve job from job_reviews table
     b. Call LLMProvider.assess_job()
     c. Parse response → AssessmentResult
     d. Save to job_assessments table
     e. Display progress emoji
   - On API failure: Log error, skip job, continue
   - Display summary at end

3. **Progress Display**
   ```
   🤖 Starting CV assessment...
   📄 Loaded CV: John Doe (Python, DevOps, 7 years exp)

   Processing 20 confirmed jobs:

   ✅ Job 1/20: Senior Engineer
      Tech: 85/100 | Seniority: 78/100 | Location: 60/100 | Overall: 75/100
      Cost: $0.002 | Tokens: 650

   ✅ Job 2/20: Backend Developer
      Tech: 92/100 | Seniority: 85/100 | Location: 100/100 | Overall: 92/100
      Cost: $0.002 | Tokens: 680

   ❌ Job 3/20: DevOps Engineer
      Error: Rate limited, skipped. Will retry next session.

   ... (continue)

   📊 Assessment Summary:
      Total assessed: 19/20 (1 failed)
      Avg overall score: 76.5
      Total cost: $0.038
      Top match: Backend Developer (92/100)
   ```

4. **Database Integration**
   - Create job_assessments table (if not exists)
   - Schema:
     ```sql
     CREATE TABLE IF NOT EXISTS job_assessments (
         job_id TEXT PRIMARY KEY,
         title TEXT,
         overall_score INTEGER,
         tech_score INTEGER,
         seniority_score INTEGER,
         location_score INTEGER,
         recommendations TEXT,  -- JSON array
         summary TEXT,
         tokens_used INTEGER,
         actual_cost REAL,
         assessed_date TIMESTAMP
     )
     ```
   - Save each assessment with: INSERT OR REPLACE

5. **CV Loading**
   - If `.json`: Parse and extract text from `text` or `content` field
   - If `.txt`: Read raw text
   - If file missing: Error message + exit(1)
   - If CV empty: Warning + continue (may affect scores)

**Implementation Location**: `src/cli.py` (assess_app.command())
**Lines of Code**: ~100 lines
**Dependencies**: `src/llm/provider.py`, `src/verification/reviewer.py`, `src/storage/db.py`

**Testing**:
- Unit test: Mock LLMProvider, verify CLI loads CV correctly
- Unit test: Verify database saves assessments
- Integration test: Full workflow with 3 sample jobs

---

### Task 4.4: Implement Assessment Storage & Database (15 min)

**Objective**: Create database table and storage methods for assessment results.

**Acceptance Criteria**:
- [ ] Create job_assessments table if not exists
- [ ] Save assessment: save_assessment(assessment: AssessmentResult)
- [ ] Query methods: get_assessments_by_score(), get_top_matches()
- [ ] FTS5 search: Search by job title, company, recommendations
- [ ] Export: Structured query results for Phase 5
- [ ] Indices: Fast queries by job_id, overall_score

**Subtasks**:

1. **Database Table Schema**
   ```sql
   CREATE TABLE IF NOT EXISTS job_assessments (
       job_id TEXT PRIMARY KEY,
       title TEXT NOT NULL,
       company TEXT,
       location TEXT,
       overall_score REAL,
       tech_score REAL,
       seniority_score REAL,
       location_score REAL,
       recommendations TEXT,  -- JSON array as string
       summary TEXT,
       tokens_used INTEGER,
       actual_cost REAL,
       assessed_date TIMESTAMP,
       FOREIGN KEY (job_id) REFERENCES job_reviews(job_id)
   )
   ```

   **Indices**:
   - `CREATE INDEX IF NOT EXISTS idx_job_assessments_score ON job_assessments(overall_score DESC)`
   - `CREATE INDEX IF NOT EXISTS idx_job_assessments_job_id ON job_assessments(job_id)`

2. **Storage Methods** in `src/storage/db.py` or new `src/storage/assessment_store.py`:
   - `save_assessment(assessment: AssessmentResult) -> None`
     - Insert or replace into job_assessments
   - `get_top_matches(limit: int = 10) -> List[Assessment]`
     - Query by overall_score DESC, limit
   - `get_assessments_by_score(min_score: float = 70) -> List[Assessment]`
     - Filter where overall_score >= min_score
   - `get_assessment_by_job_id(job_id: str) -> Optional[Assessment]`
     - Single job lookup

3. **FTS5 Search Index**
   - Create FTS5 virtual table for full-text search:
     ```sql
     CREATE VIRTUAL TABLE IF NOT EXISTS job_assessments_fts USING fts5(
         job_id, title, company, summary, recommendations
     )
     ```
   - Populate from job_assessments on INSERT
   - Enable search: "Find jobs mentioning Python and DevOps"

4. **Metrics/Analytics Query**
   - `get_assessment_stats() -> Dict`:
     - avg_score, max_score, min_score
     - total_assessments, total_cost, avg_cost
     - distribution by score range (0-50, 50-70, 70-85, 85-100)

**Implementation Location**: `src/storage/assessment_store.py` (new file)
**Lines of Code**: ~150 lines
**Dependencies**: `sqlite3`, `src/models/assessment.py`

**Testing**:
- Unit test: Save assessment, retrieve by job_id
- Unit test: Query top matches, filter by score
- Unit test: FTS5 search for keywords
- Unit test: Analytics stats calculation

---

### Task 4.5: Integration Testing & Validation (10 min)

**Objective**: End-to-end testing for Phase 4 workflow.

**Acceptance Criteria**:
- [ ] Load 3-5 sample confirmed jobs from Phase 3
- [ ] Mock Claude API responses
- [ ] Verify assessments saved to database
- [ ] Verify cost tracking: estimate vs. actual
- [ ] Verify top-matches query works
- [ ] All tests passing (26 existing + new Phase 4 tests)
- [ ] Code formatted with Black
- [ ] Linting passes ruff

**Test Coverage**:

1. **Unit Tests** (~30 tests):
   - `test_assessment_result_model.py`: Pydantic validation
   - `test_llm_provider.py`: assess_job(), error handling, retries
   - `test_assessment_prompts.py`: Prompt rendering, JSON parsing
   - `test_assessment_store.py`: Save/load/query assessments
   - `test_cli_assess.py`: CLI command, CV loading, progress display

2. **Integration Tests** (~5 tests):
   - Load Phase 3 verified jobs → assess all → verify DB populated
   - Mock Claude, verify end-to-end flow
   - Verify cost tracking matches estimates
   - Verify top-matches ranked by score

3. **Coverage Target**: 80%+ for Phase 4 code

4. **Manual Validation** (if API key available):
   - Run with 1-2 real jobs + real Claude API
   - Verify response format, scores are reasonable
   - Verify token counts + costs match Claude response

**Implementation Location**: `tests/test_llm.py` (update), `tests/test_assessment_store.py` (new)
**Lines of Code**: ~200 lines of tests

**Success Criteria**:
- [ ] All 26+ tests passing
- [ ] 0 linting issues
- [ ] Code formatted
- [ ] Phase 4 integration verified with mocks

---

## Implementation Sequence

```
1. Task 4.1 (LLMProvider)
   └─ Create src/llm/provider.py
   └─ Implement assess_job() with error handling
   └─ Add unit tests
   └─ ~120 lines

2. Task 4.2 (Prompts)
   └─ Create src/llm/prompts.py
   └─ Design assessment prompt template
   └─ Add prompt rendering logic
   └─ ~80 lines

3. Task 4.3 (CLI)
   └─ Add assess-jobs command to src/cli.py
   └─ Implement workflow orchestration
   └─ Add progress display
   └─ ~100 lines

4. Task 4.4 (Storage)
   └─ Create src/storage/assessment_store.py
   └─ Create job_assessments table
   └─ Implement query/save methods
   └─ ~150 lines

5. Task 4.5 (Testing)
   └─ Add unit tests for all modules
   └─ Add integration tests
   └─ Verify coverage 80%+
   └─ Format + lint
   └─ ~200 lines of tests
```

**Total Implementation Time**: 40-50 minutes
**Total Lines of Code**: ~650 lines (source) + 200 lines (tests)

---

## Database Changes

### New Table: job_assessments

```sql
CREATE TABLE IF NOT EXISTS job_assessments (
    job_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT,
    location TEXT,
    overall_score REAL,
    tech_score REAL,
    seniority_score REAL,
    location_score REAL,
    recommendations TEXT,  -- JSON array
    summary TEXT,
    tokens_used INTEGER,
    actual_cost REAL,
    assessed_date TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES job_reviews(job_id)
);

CREATE INDEX idx_job_assessments_score
  ON job_assessments(overall_score DESC);

CREATE INDEX idx_job_assessments_job_id
  ON job_assessments(job_id);

CREATE VIRTUAL TABLE job_assessments_fts USING fts5(
    job_id, title, company, summary, recommendations
);
```

---

## Error Handling Strategy

| Error | Handling | Outcome |
|-------|----------|---------|
| API Connection Error | Retry 3x with exponential backoff | Skip job if all fail, log error |
| Rate Limit (429) | Wait 2^attempt seconds, retry | Continue after backoff |
| Invalid JSON Response | Retry with clearer prompt | Default scores if still fails |
| CV File Missing | Exit with error message | User provides valid path |
| DB Write Failure | Log error, continue | Manual retry later |
| Assessment Request Timeout | Retry up to 3 times | Skip job after 3 failures |

---

## Cost Estimation

**Phase 4 Cost Breakdown** (for 20 confirmed jobs):

| Item | Estimate |
|------|----------|
| Input tokens per job | ~600 (preprocessed chunks) |
| Output tokens per job | ~50 (JSON response) |
| Total tokens per job | ~650 |
| Cost per job @ Claude rates | ~$0.002 |
| **Total for 20 jobs** | **~$0.040** |

**Comparison**:
- Without Phase 3 filtering (26 jobs): $0.052
- **Savings from Phase 3**: $0.012 (23% reduction)
- **Scale benefit**: On 100 jobs, potential ~$0.05-0.06 savings

---

## Known Limitations & Considerations

1. **Token Count Variance**
   - Phase 2 estimates vs. actual Claude tokens may differ 5-10%
   - Recommendation: Track variance across jobs, adjust future estimates
   - Implementation: Store both estimate + actual in DB for metrics

2. **Prompt Tuning**
   - Current prompt assumes CV is raw text
   - May need tuning if user CVs vary widely in format
   - Recommendation: Collect feedback, refine prompt iteratively

3. **Rate Limiting**
   - Current implementation adds 1s delay between jobs
   - At 10 jobs/min limit, should be safe
   - For scaling: Implement queue-based pattern or batch API

4. **Score Calibration**
   - Claude's 0-100 scores are qualitative
   - Consider calibration after 10+ sample assessments
   - Recommendation: Collect user feedback (liked/disliked jobs) for calibration

5. **Location Scoring**
   - CV may not explicitly state location preferences
   - Current prompt makes best effort (remote-first companies = high score)
   - Limitation: May not capture full remote/relocation flexibility

6. **Multi-Language CVs**
   - Current implementation assumes English CV
   - Claude can handle other languages, but scoring may vary
   - Recommendation: Document assumption, test with diverse CVs

---

## Success Criteria

✅ Phase 4 is complete when:

- [ ] LLMProvider class fully implemented with error handling
- [ ] Assessment prompts engineered and tested
- [ ] assess-jobs CLI command working end-to-end
- [ ] job_assessments table created and indexed
- [ ] All 30+ tests passing (14 existing + ~16 new)
- [ ] Code formatted (Black) and linted (ruff)
- [ ] Phase 3 → Phase 4 workflow tested with 3-5 sample jobs
- [ ] Cost tracking validates Phase 2 estimates within 10%
- [ ] Top-matches query returns jobs ranked by overall_score DESC
- [ ] Ready for Phase 5 (export and reporting)

---

## Next Steps After Phase 4

**Phase 5 (Results Storage & Export)**:
- Implement markdown report generation
- Create ranked job list by score
- Add recommendation summary aggregation
- Implement keyword search across assessments
- Display analytics (cost breakdown, score distribution, etc.)

**Estimated Phase 5 Time**: 30-40 minutes

---

## References & Resources

- **Claude API**: https://docs.anthropic.com/claude/reference/getting-started
- **Token Counting**: https://github.com/openai/tiktoken (use for estimation)
- **Pydantic**: https://docs.pydantic.dev/latest/
- **SQLite**: https://www.sqlite.org/lang.html

---

**Document Version**: 1.0
**Created**: 2026-05-27
**Last Updated**: 2026-05-27
**Author**: Copilot CLI
**Status**: ✅ Ready for Implementation
