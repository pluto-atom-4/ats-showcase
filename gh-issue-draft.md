# Bug: Review subcommand exits after first job skip instead of continuing to next job

**Status**: Open
**Priority**: High (Blocks interactive review workflow)
**Severity**: Critical (Prevents users from reviewing jobs after skipping any job)

## Overview

When using the `review` subcommand with `--allow-re-review` flag, after a user chooses **skip** for the first job, the command displays the review summary and exits instead of continuing to the second job. This prevents users from reviewing the full batch of jobs interactively.

## Reproduction Steps

### Environment
- Repository: ATS Playground
- Python: 3.11+
- Database: SQLite with 4+ extracted jobs

### Command
```bash
uv run python -m src.cli review --allow-re-review
```

### Steps
1. Run the review command (uses default hardcoded: `carbonrobotics_jobs.json`)
2. First job displays: "Job 1 of 4: Deep Learning Quality Specialist"
3. When prompted for action, enter: `s` (skip)
4. System should show the second job ("Job 2 of 4"), but instead shows summary and exits

## Expected Behavior

After the user selects **skip** for any job:
- Job should be saved to database with status: `pending_review`
- Review loop should **continue** to the next job
- Display next job: "Job 2 of 4"
- Continue until all jobs are reviewed or user chooses **quit** (`q`)

## Actual Behavior

After the user selects **skip** for the first job:
```
🔍 Job 1 of 4: Deep Learning Quality Specialist
   Company: CompanyD
   Location: Seattle, WA
   Tokens: 1273 | Cost: $0.000005
   Status: pending_review | Crawled: not processed | Reviewed: 2026-07-09 21:10
   Content: The Carbon Robotics LaserWeeder™ leverages advanced robotics...

   📅 Timeline:
      Crawled: not processed
      Preprocessed: not processed
      Reviewed: 2026-07-09 21:10
      Assessed: not processed
   Action (c=confirm/r=reject/s=skip/q=quit/e=re-review): s
   ⊘ Skipped (will review later)

📊 Review Summary:
   Total reviewed:  1
   Confirmed:       0 (0%)
   Rejected:        0 (0%)
   Skipped:         4          ← Shows 4 skipped, but user only skipped 1!

   Ready for Phase 4 Assessment:
     • Jobs: 0
     • Est. LLM cost: $0.000000
     • Avg tokens/job: 0
```

**Observations:**
- Only Job 1 is displayed (should show Jobs 1-4)
- Summary shows "Skipped: 4" (user only manually skipped 1; suggests 3 more were auto-filtered)
- Loop exits instead of continuing
- User cannot review jobs 2-4

## Root Cause Analysis

### Suspected Issues

The bug likely stems from one of these scenarios in `src/verification/reviewer.py`:

1. **Job Counter Increment Logic (Line 771)**
   - `job_counter` is incremented AFTER `review_job_interactive()` is called
   - When jobs are filtered (via `should_skip_job`), the `continue` statement (line 761) skips the increment
   - This may cause display index to become misaligned between displayed job and loop iteration

2. **Skip Status Filtering Issue (Lines 750-761)**
   - After user skips job 1 with status `"pending_review"`, remaining jobs may be incorrectly filtered
   - `_check_mode_filter()` in "new-only" mode should skip only "confirmed" or "rejected" jobs (line 385)
   - But somehow jobs 2-4 are being marked as skipped (stats.skipped incremented 3 more times)

3. **Job Counter vs Total Jobs Mismatch**
   - Display shows "Job X of Y", but if job_counter doesn't increment consistently, displays could show same job number repeatedly
   - After skipping job 1, job_counter should be 1, and next display should show "Job 2 of 4"
   - But the command exits instead

4. **Early Loop Exit**
   - `review_job_interactive()` may be raising an exception or returning prematurely after skip action
   - Line 768-769 catches `typer.Exit` but other exceptions may not be handled

### Investigation Needed

- [ ] Check if job_counter is incremented correctly after skip action
- [ ] Verify should_skip_job() logic for jobs 2-4 (why are they being skipped?)
- [ ] Confirm that review_job_interactive() loop correctly breaks and returns control to review_batch()
- [ ] Check if there's a database state issue (e.g., all jobs except first incorrectly marked as "rejected" or "confirmed")
- [ ] Verify that stats.total is incremented correctly and matches displayed job count
- [ ] Test with --mode="all" to see if filtering is the culprit

## Code References

**Main review loop**: `src/verification/reviewer.py:745-771`
```python
for extracted_path, extracted_jobs in all_extracted_jobs:
    source_name = extracted_path.stem
    for idx, job in enumerate(extracted_jobs):
        job_id = job.get("id", f"{source_name}_{idx + 1}")
        preprocessed = preprocessed_map.get(job_id, {})

        # Phase 3: Check if job should be skipped based on filters
        should_skip, skip_reason = self.should_skip_job(...)
        if should_skip:
            stats.add_skipped()
            logger.debug(f"Skipped job {job_id}: {skip_reason}")
            continue  # ← Continues WITHOUT incrementing job_counter

        try:
            self.review_job_interactive(
                job_counter, total_jobs, job, preprocessed, stats,
                allow_re_review=allow_re_review
            )
        except typer.Exit:
            raise

        job_counter += 1  # ← Only incremented for reviewed jobs, not filtered
```

**Skip action handling**: `src/verification/reviewer.py:661-664`
```python
elif action == "s":
    self._handle_skip_action(job_id, title, location, company, stats)
    typer.echo("   ⊘ Skipped (will review later)")
    return True  # ← Breaks inner while loop in review_job_interactive()
```

**Skip action saves status**: `src/verification/reviewer.py:569-571`
```python
def _handle_skip_action(self, job_id, title, location, company, stats):
    """Handle skip action. Preserves job as pending_review for future review."""
    self.save_review(job_id, title, location, status="pending_review", company=company)
    stats.add_skipped()
```

**Mode filter logic**: `src/verification/reviewer.py:369-388`
```python
def _check_mode_filter(self, job_id: str, mode: str) -> tuple[bool, Optional[str]]:
    if mode == "all":
        return False, None
    if mode == "new-only":
        cursor = self.conn.cursor()
        cursor.execute("SELECT status FROM job_reviews WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        if row and row["status"] in ("confirmed", "rejected"):
            return True, "already_reviewed"
    return False, None
```

## Impact

- **Scope**: Interactive review workflow is broken
- **Affected Users**: Anyone using `review --allow-re-review` or reviewing multiple jobs interactively
- **Data Loss Risk**: Low (skip saves to DB, but user can't complete review session)
- **Related Issues**: #102, #116, #119 (all involved review command changes)

## Testing

To verify the fix:

```bash
# Command that reproduces the issue
uv run python -m src.cli review --allow-re-review

# Expected: After skipping job 1, display "Job 2 of 4"
# Expected: Can skip multiple jobs in sequence
# Expected: Final summary shows correct total reviewed

# Also test:
uv run python -m src.cli review --allow-re-review --mode all
uv run python -m src.cli review --allow-re-review --merge-all  # Multi-file
```

## Suggested Fix Areas

1. **Review `job_counter` increment logic**
   - Ensure it increments for every job displayed, not just reviewed ones
   - Consider using `idx + 1` directly instead of separate counter

2. **Check filtering logic after skip**
   - Debug why stats.skipped shows 4 instead of 1
   - Add logging to track which jobs are being skipped and why

3. **Verify loop flow**
   - Ensure `review_job_interactive()` returns correctly after skip
   - Check for unexpected exceptions causing early exit

4. **Add integration test**
   - Test interactive review with 4+ jobs
   - Simulate skip, confirm, reject actions in sequence
   - Verify all jobs are processed

## Files Likely Affected

- `src/verification/reviewer.py` - Main issue in review loop logic
- `tests/test_review.py` - May need additional test coverage
- `src/cli.py` - May need debugging output

## Related Issues

- #102 - Interactive re-review feature
- #116 - Mode flag implementation
- #119 - Persist skipped jobs
- #100 - Pipeline control filters

---

## Additional Context

The issue appears after changes to the review command in #119 and earlier refactoring in #102-#116. The `skip` action should preserve jobs as "pending_review" in the database but should NOT stop the interactive loop. Instead, the loop should continue to the next job until the user explicitly chooses "quit" or all jobs are processed.

The fact that stats shows "Skipped: 4" suggests either:
1. The remaining 3 jobs are being auto-skipped by filters (but should not be in "new-only" mode)
2. The job counter is being incremented incorrectly, causing the same job to be counted multiple times
3. An exception is being raised after the first skip, causing the loop to exit

**Priority for investigation**: Check review loop iteration and job filtering logic in `src/verification/reviewer.py:745-771`.
