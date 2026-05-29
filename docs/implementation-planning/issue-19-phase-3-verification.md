# Issue #19 Phase 3: User Verification & Review 👀

**Parent Issue**: #19 - POC: Test Crawl Workflow on Real Career Page
**Phase**: 3 of 5
**Status**: Planning
**Time Estimate**: 25–35 minutes

---

## Objective

Create an interactive CLI that allows users to review, confirm, or reject extracted/preprocessed jobs **before expensive LLM API calls**. Display cost estimates and get explicit user approval for each job.

### Success Criteria
- ✅ All 26 preprocessed jobs loaded from Phase 2 output
- ✅ Interactive review CLI with clear job previews
- ✅ User can: Confirm, Reject, or Edit each job
- ✅ Cost transparency: show estimated LLM cost before assessment
- ✅ Approved jobs marked as "confirmed" and persisted
- ✅ Verification results saved to database or JSON
- ✅ Resume capability: can skip reviewed jobs on re-run
- ✅ All tests passing, code quality maintained

---

## Background: Why User Verification Matters

**Cost Risk**: Without verification, all 26 jobs would send to Claude API
- Unreviewed jobs might be irrelevant (wrong location, wrong seniority level)
- Failed extraction attempts waste money
- User has no visibility into what's being assessed

**Solution**: Interactive verification gate before LLM calls
- User reviews each job once before assessment
- Cost estimate shown: user decides if assessment is worth it
- Approval saved: prevents re-review on future runs
- Transparency: user controls what gets expensive API calls

**Expected Cost Impact**:
- 26 jobs × ~$0.002 per job = **$0.052 total for all assessments**
- User can reject obviously wrong jobs, saving 20–40% on API costs
- Verification adds ~1–2 minutes per 26 jobs (negligible cost vs. LLM savings)

---

## Phase 3 Tasks

### Task 3.1: Create JobReviewer Class & Database Schema

**Objective**: Store user verification decisions (confirm/reject/pending).

#### Implementation Strategy

**New Module**: `src/verification/reviewer.py`
- Class: `JobReviewer`
- Methods: `load_jobs()`, `review_job()`, `save_decision()`, `get_confirmed_jobs()`

**Database Schema** (SQLite):
```sql
CREATE TABLE job_reviews (
    job_id TEXT PRIMARY KEY,
    title TEXT,
    location TEXT,
    status TEXT DEFAULT 'pending',  -- pending, confirmed, rejected
    reason TEXT,                     -- rejection reason (optional)
    estimated_tokens INTEGER,
    estimated_cost REAL,
    reviewed_at DATETIME,
    notes TEXT
);
```

#### Steps

1. **Create verification module directory** (if not exists)
   ```bash
   mkdir -p src/verification
   touch src/verification/__init__.py
   ```

2. **Implement JobReviewer class**
   - Load preprocessed jobs from `data/extracted_jobs/preprocessed_jobs.json`
   - Load review history from database (if exists)
   - Track: job_id, status (pending/confirmed/rejected), reason, cost estimate

3. **Create SQLite schema**
   - Database: `data/ats_playground.db` (or new if needed)
   - Table: `job_reviews` with fields above
   - Indexes: (job_id, status) for fast filtering

4. **Expected Output**
   ```python
   reviewer = JobReviewer("data/ats_playground.db")
   pending_jobs = reviewer.get_pending_jobs()  # Returns [PreprocessedJob, ...]

   # Load already-reviewed jobs from database
   confirmed_jobs = reviewer.get_confirmed_jobs()  # Skip on re-review
   ```

---

### Task 3.2: Implement Interactive Review CLI

**Objective**: Build user-friendly CLI for reviewing jobs one-by-one.

#### Implementation Strategy

**New Module**: `src/cli.py` (add `review` command)
- Command: `uv run python -m src.cli review review-jobs`
- Options: `--interactive`, `--auto-approve` (dangerous!), `--resume`

#### Review Flow

```
🔍 Job 1 of 26: Deep Learning Engineer
   Location: Seattle, WA
   Tokens: 7
   Est. Cost: $0.000015

   Action (c=confirm, r=reject, e=edit, s=skip, q=quit): _
```

#### Steps

1. **Load preprocessing output**
   ```python
   from src.tokenization.counter import TokenCounter
   from pathlib import Path

   counter = TokenCounter()
   preprocessed_file = Path("data/extracted_jobs/preprocessed_jobs.json")
   jobs = json.load(open(preprocessed_file))
   ```

2. **Display job preview**
   - Title (bold)
   - Location
   - Token count & estimated cost
   - Optional: first 100 chars of description

3. **Prompt for user action**
   ```
   Actions:
   c = Confirm job (mark for assessment)
   r = Reject job (skip assessment)
   e = Edit job (modify details)
   s = Skip for now (review later)
   q = Quit

   Current: Pending (1/26)  Confirmed (0/26)  Rejected (0/26)
   ```

4. **Handle each action**
   - **Confirm**: Mark status="confirmed", save to DB
   - **Reject**: Mark status="rejected", ask for reason, save to DB
   - **Edit**: Show text editor for job details (optional)
   - **Skip**: Move to next job, come back later
   - **Quit**: Save progress, exit gracefully

5. **Resume capability**
   ```bash
   # First run: review all pending
   uv run python -m src.cli review review-jobs

   # Later: resume where you left off
   uv run python -m src.cli review review-jobs --resume
   ```

#### Expected Output

```
👀 Starting job review (26 jobs total)

🔍 Job 1 of 26: Deep Learning Engineer
   Location: Seattle, WA
   Tokens: 7 | Cost: $0.000015
   Status: pending_review

   Action (c/r/e/s/q): c
   ✓ Confirmed

🔍 Job 2 of 26: Performance Quality Technician
   Location: Remote - Europe
   Tokens: 7 | Cost: $0.000015
   Status: pending_review

   Action (c/r/e/s/q): r
   Reason (optional): Wrong location preference
   ✓ Rejected

... (continue through all jobs)

📊 Summary:
   Total reviewed: 26
   Confirmed: 20
   Rejected: 6
   Skipped: 0

   Next step: Run assessment on 20 confirmed jobs
   Estimated LLM cost: $0.0003
```

---

### Task 3.3: Implement Verification Storage

**Objective**: Persist user decisions to database for reproducibility and resumability.

#### Implementation Strategy

**Database Operations**:
- Save decision when user confirms/rejects
- Load decisions on resume to skip already-reviewed jobs
- Query: get confirmed jobs (for Phase 4)
- Query: get rejection reasons (for analytics)

#### Steps

1. **Create database helper functions**
   ```python
   def save_review(job_id, status, reason=None, cost=None):
       """Save user review decision to database."""
       # INSERT OR UPDATE job_reviews

   def load_review(job_id):
       """Load existing review for job."""
       # SELECT from job_reviews

   def get_confirmed_jobs():
       """Get all confirmed jobs for Phase 4."""
       # SELECT WHERE status = 'confirmed'

   def get_rejection_stats():
       """Get stats on rejections."""
       # SELECT reason, COUNT(*) GROUP BY reason
   ```

2. **Implement in JobReviewer class**
   - Initialize DB connection in `__init__`
   - Call `save_review()` after each user action
   - Call `load_review()` to check if already reviewed

3. **Schema with indices**
   ```sql
   CREATE INDEX idx_job_status ON job_reviews(status);
   CREATE INDEX idx_reviewed_at ON job_reviews(reviewed_at);
   ```

---

### Task 3.4: Implement Review Statistics & Summary

**Objective**: Show aggregate metrics and analytics on review session.

#### Implementation Strategy

**Statistics to Track**:
- Total jobs reviewed: 26
- Confirmed: N (ready for assessment)
- Rejected: M (with reasons)
- Pending: 26 - N - M (skipped for later)
- Total estimated cost: $X (for N confirmed jobs)

#### Steps

1. **Implement statistics calculation**
   ```python
   def get_review_stats():
       return {
           "total": 26,
           "confirmed": count where status='confirmed',
           "rejected": count where status='rejected',
           "pending": count where status='pending',
           "total_confirmed_cost": sum(cost) where status='confirmed',
           "avg_tokens_confirmed": avg(tokens) where status='confirmed',
       }
   ```

2. **Display at end of review session**
   ```
   📊 Review Session Summary:

   Jobs Reviewed:     26/26 ✓
   Confirmed:         20 (77%)
   Rejected:          6 (23%)

   Rejection Reasons:
     • Wrong location: 3
     • Wrong seniority: 2
     • Duplicate: 1

   LLM Assessment Ready:
     • Jobs: 20
     • Estimated tokens: 140
     • Estimated cost: $0.00042
     • Next: uv run python -m src.cli assess --cv data/cv.json
   ```

---

### Task 3.5: Validation & Testing

**Objective**: Verify review workflow works end-to-end with good UX.

#### Validation Checklist

- ✅ All 26 jobs load from preprocessed output
- ✅ Interactive prompts work correctly
- ✅ User actions (c/r/e/s/q) handled properly
- ✅ Decisions saved to database
- ✅ Resume skips already-reviewed jobs
- ✅ Statistics calculated correctly
- ✅ Cost estimates match Phase 2 output
- ✅ CLI command runs without errors
- ✅ Edge cases handled (empty input, invalid action, etc.)

#### Test Commands

```bash
# Run interactive review
uv run python -m src.cli review review-jobs

# Run with mock input (automated test)
echo -e "c\nc\nr\nWrong location\nq" | uv run python -m src.cli review review-jobs

# Resume and skip already-reviewed
uv run python -m src.cli review review-jobs --resume

# Query results
sqlite3 data/ats_playground.db "SELECT status, COUNT(*) FROM job_reviews GROUP BY status"
```

#### Test Scenarios

1. **Happy path**: Confirm 20, reject 6, no errors
2. **Resume**: Start, confirm 10, quit; resume and continue
3. **Edge case**: Invalid input (spam keys), should re-prompt
4. **Edge case**: Empty file, should error gracefully
5. **Edge case**: Database corruption, should fail cleanly

#### Success Metrics

| Metric | Target | Note |
|--------|--------|------|
| Jobs loaded | 26/26 | 100% |
| Review time/job | <5 sec | UX should be snappy |
| Database consistency | 100% | All decisions persisted |
| Confirmed jobs | 15–25 | Reasonable acceptance rate |
| Test coverage | 80%+ | For new verification module |

---

## Known Limitations & Unknowns

### Limitation 1: Edit Functionality
**Issue**: Allowing users to edit job details adds complexity

**Recommended Approach**: Skip for now (Task 3.2 has "e" as placeholder)
- Can be implemented in future if needed
- Focus on confirm/reject for MVP
- Editing descriptions requires fetching full job detail pages

### Limitation 2: Resume State
**Issue**: If user quits mid-review, resuming should skip completed jobs

**Mitigation**: Always save decision immediately to DB
- No risk of losing work
- Resume checks DB before showing job
- Transparent: user sees (e.g.) "Job 5 of 26 (3 already reviewed, 2 skipped)"

### Unknown 1: Performance at Scale
**Unknown**: How fast is interactive CLI for 100+ jobs?

**Test During Phase 3**: Time full 26-job review, extrapolate to 100+
- Goal: <100ms per job (including DB operations)

### Unknown 2: User Experience
**Unknown**: Is the prompt UX clear enough?

**Validate During Testing**: Get feedback on:
- Action keys (c/r/e/s/q) intuitive?
- Job preview sufficient?
- Cost display clear?
- Status display helpful?

---

## File Structure After Phase 3

```
src/
  verification/
    __init__.py                 ← New
    reviewer.py                 ← New (JobReviewer class)
  cli.py                        ← Update with review-jobs command

data/
  extracted_jobs/
    carbonrobotics_jobs.json         (from Phase 1)
    preprocessed_jobs.json           (from Phase 2)
  ats_playground.db                  ← Updated with job_reviews table

tests/
  test_verification.py          ← New (review unit tests)

docs/
  implementation-planning/
    issue-19-phase-3-verification.md  ← This file
```

---

## Implementation Order

1. **Task 3.1**: Create JobReviewer class + database schema
2. **Task 3.2**: Implement interactive review CLI
3. **Task 3.3**: Implement verification storage (DB operations)
4. **Task 3.4**: Implement statistics & summary display
5. **Task 3.5**: Validation, testing, edge cases

---

## Acceptance Criteria

Phase 3 is complete when:

- ✅ All 26 preprocessed jobs reviewed interactively
- ✅ User actions (c/r/s/q) working correctly
- ✅ Review decisions persisted to database
- ✅ Resume works: skips already-reviewed jobs
- ✅ Statistics and summary displayed correctly
- ✅ CLI command works end-to-end without errors
- ✅ Unit tests passing (80%+ coverage)
- ✅ Code formatted (Black) and linting passes (ruff)
- ✅ Ready for Phase 4 (Claude API assessment)

---

## Next Phase (Phase 4)

After user verification succeeds, Phase 4 will:
- Load confirmed jobs from DB (20–25 expected)
- Prepare Claude API prompts with job details
- Call Claude API for each confirmed job
- Parse: overall_score, tech_score, seniority_score, location_score, recommendations
- Track actual tokens used vs estimates from Phase 2
- Store assessments in database for Phase 5

---

## CLI Design: Interactive Flow

```
┌─────────────────────────────────────────────┐
│  Start: uv run python -m src.cli review    │
│         review-jobs [--resume]              │
└────────────────┬────────────────────────────┘
                 │
                 ▼
    ┌─────────────────────────────┐
    │ Load preprocessed jobs      │
    │ Check DB for reviews        │
    └────────┬────────────────────┘
             │
             ▼
    ┌─────────────────────────────┐
    │ Show first pending job      │
    │ Display: title, location    │
    │          cost estimate      │
    └────────┬────────────────────┘
             │
             ▼
    ┌─────────────────────────────┐
    │ Prompt user action          │
    │ (c/r/e/s/q)                 │
    └────────┬────────────────────┘
             │
      ┌──────┼──────┬──────┬──────┬─────┐
      │      │      │      │      │     │
      ▼      ▼      ▼      ▼      ▼     ▼
    [Confirm][Reject][Edit][Skip][Quit]
      │      │      │      │      │     │
      │      └─────►└──┬───┘      │     │
      │               │          │     │
      ▼               ▼          ▼     ▼
   Save to DB    Save + Reason  Skip  Exit
   (confirmed)   (rejected)          Save
      │               │          │    Progress
      └───────┬───────┘          │
              │                  │
         ┌────┴──────────┬───────┘
         │               │
         ▼               ▼
   More jobs?      → Quit
      YES              (resume later)
       │
       ▼
   Next job
    (loop)
       │
       NO
       ▼
   Display Summary
   Stats & Next Steps
```

---

## References

- **Phase 2 Output**: `data/extracted_jobs/preprocessed_jobs.json`
- **Models**: `src/models/job.py::PreprocessedJob`
- **Storage Patterns**: `src/storage/db.py` (if exists)
- **CLI Framework**: Typer (already used in Phase 1 & 2)

---

## Cost Impact Analysis

**Phase 3 Cost**:
- Database operations: ~$0 (SQLite local, no API calls)
- CLI UX: ~$0 (all local)
- Total Phase 3: **$0**

**Phase 4 Cost** (prepared by Phase 3):
- 26 jobs × ~$0.002 each = **~$0.052**
- User can reduce by rejecting irrelevant jobs
- Phase 3 saves money by letting user review before spending on API

---

**Last Updated**: 2026-05-27
**Status**: Ready for Implementation
**Estimated Duration**: 25–35 minutes
