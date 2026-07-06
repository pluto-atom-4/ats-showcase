# Bug Report: Company Name Not Stored During Job Review Confirmation

## Summary

When users confirm jobs during the interactive review phase (`uv run python -m src.cli review --merge-all`), the company name is not being inserted into the `job_reviews` table. This causes data loss and prevents proper company tracking for confirmed positions.

## Steps to Reproduce

1. Run the preprocessing step:
   ```bash
   uv run python -m src.cli preprocess --batch-size 10 --show-estimates
   ```

2. Start the interactive review:
   ```bash
   uv run python -m src.cli review --merge-all
   ```

3. Confirm several jobs by pressing `c` when prompted:
   ```
   Action (c=confirm/r=reject/s=skip/q=quit): c
   ✓ Confirmed (1/X confirmed)
   ```

4. Query the database to verify:
   ```bash
   sqlite3 data/ats_playground.db "SELECT job_id, title, company, status FROM job_reviews WHERE status='confirmed';"
   ```

## Expected Behavior

- All confirmed jobs should have the company name stored in the `job_reviews` table
- Database query should show company names like "Boeing", "Blue Origin", "CarbonRobotics", etc.

## Actual Behavior

- Company field is **NULL** for most confirmed jobs (except the first one)
- Database query shows:
  ```
  workday:4ef4b2c80f31ee08|Test Job|Blue Origin|confirmed
  workday:9d65d988f4604477|Senior Software Engineer||confirmed
  workday:750bc3d000206be6|Software Engineer–Developer (Development)||confirmed
  workday:dfb8dce0e623a8fa|Associate/Experienced Software Engineer–Developer||confirmed
  greenhouse:bc6e32a68ce33a45||confirmed
  ```

## Evidence from Current Session

**Confirmed Jobs (4 total):**
- Job 5 (Boeing): Senior Software Engineer - ✓ Confirmed
- Job 6 (Boeing): Software Engineer–Developer (Development) - ✓ Confirmed
- Job 8 (Boeing): Associate/Experienced Software Engineer–Developer (Development) - ✓ Confirmed
- Job 9 (CarbonRobotics): Deep Learning Engineer - ✓ Confirmed

**Database Status:**
- Total jobs in `job_reviews`: 7
- Jobs with company field populated: 1
- Jobs with company field NULL: 6
- Confirmed jobs missing company: 3 Boeing + 1 CarbonRobotics = 4 jobs

## Root Cause Analysis

**Source Code Location:** `src/verification/reviewer.py` (lines 205-207)

When a job is confirmed via the `review_job_interactive()` method, the `company` parameter is passed to `save_review()`:

```python
if action == "c":
    self.save_review(
        job_id, title, location, status="confirmed", tokens=tokens, estimated_cost=cost, company=company
    )
```

The `company` value is extracted from the preprocessed job data (line 175):
```python
company = preprocessed.get("company")
```

**Issue:** The preprocessed jobs data structure may not consistently include the company field in all cases, or the field name may differ. This causes `company` to be `None` when `save_review()` is called.

## Impact

- **Data Loss:** Company information is lost during review, making it impossible to track which employer posted each job
- **Downstream Issues:** Phase 4 (Assessment) cannot correlate jobs back to companies
- **Reporting:** Markdown export and analytics cannot group results by company
- **User Experience:** Users lose track of job origins during multi-company review workflows

## Affected Code Paths

1. **Review Phase:** `src/verification/reviewer.py`
   - `review_job_interactive()` method (lines 152-231)
   - `save_review()` method (lines 109-141)

2. **Database Schema:** `src/verification/reviewer.py` (lines 64-77)
   - `job_reviews` table has `company TEXT` column (defined but not reliably populated)

3. **Data Flow:**
   ```
   extracted_jobs.json (company: "Boeing")
     ↓
   preprocessed_jobs.json (company: field may be missing or misnamed)
     ↓
   review_job_interactive() (company = preprocessed.get("company") → None)
     ↓
   job_reviews table (company: NULL ❌)
   ```

## Possible Root Causes

1. **Preprocessed data missing company field:** The `preprocess` command may not be including the company field from source jobs when creating `preprocessed_jobs.json`

2. **Field name mismatch:** The preprocessing step may use a different field name (e.g., `company_name`, `employer`, etc.)

3. **Data structure inconsistency:** Extracted jobs from different sources may have the company field in different locations or with different naming conventions

## Test Data

- Extracted jobs files show company field present:
  - `data/extracted_jobs/boeing_jobs.json` - company: "Boeing" ✓
  - `data/extracted_jobs/blue origin_jobs.json` - company: "Blue Origin" ✓
  - `data/extracted_jobs/carbonrobotics_jobs.json` - company: "CarbonRobotics" ✓
  - `data/extracted_jobs/uw_jobs.json` - company: "UW" ✓

- Preprocessed jobs file shows inconsistent company field:
  - First job has company: "Blue Origin" ✓
  - Subsequent jobs missing company field ❌

## Files Involved

- `src/verification/reviewer.py` - Review logic
- `src/preprocessing/` (or equivalent) - Preprocessing logic
- `data/extracted_jobs/boeing_jobs.json` - Source data
- `data/extracted_jobs/blue\ origin_jobs.json` - Source data
- `data/extracted_jobs/carbonrobotics_jobs.json` - Source data
- `data/extracted_jobs/uw_jobs.json` - Source data
- `data/extracted_jobs/preprocessed_jobs.json` - Processed data with issue
- `data/ats_playground.db` - SQLite database showing NULL company values

## Suggested Fix

1. **Verify company field in preprocessed data:** Ensure `preprocessed_jobs.json` consistently includes the company field from source jobs

2. **Fallback mechanism:** Add a fallback in `review_job_interactive()` to retrieve company from original extracted jobs if missing from preprocessed data

3. **Validation:** Add pre-check before `review_batch()` to ensure all jobs have company field populated

4. **Error logging:** Add debug logging to track why company field is None for specific jobs

## Acceptance Criteria

- [ ] All confirmed jobs have company name stored in `job_reviews.company` column
- [ ] NULL values in company field are eliminated for multi-company workflows
- [ ] Database query returns proper company names for all reviewed jobs
- [ ] Company field is populated during initial review confirmation
- [ ] Preprocessed jobs file includes company field from source

## CLI Commands Affected

- `uv run python -m src.cli review --merge-all` ❌
- `uv run python -m src.cli review --interactive` ❌
- `uv run python -m src.cli --all` (full workflow) ❌

## Environment

- **OS:** Linux
- **Python:** 3.13.5
- **Date Reported:** 2026-07-05
- **Branch:** feat/issue-93-multi-config-pipeline
