# Parent Issue: Enhanced Pipeline Control & User Visibility (Tracking #100 follow-ups)

## Summary

Issue #100 delivered core **selective processing** via `--skip-*` filters (date, status, assessment). This follow-up issue captures remaining features from the original proposal that improve **user visibility**, **workflow flexibility**, and **interactive re-review capabilities**.

**Related**: Supersedes features not implemented in PR #101 → Issue #100

## Context

PR #101 closed issue #100 with a partial implementation:

### ✅ Implemented
- Database schema: `crawled_at` timestamp + index
- Storage query methods: assessment status, jobs needing assessment, date filtering
- Reviewer filtering: `should_skip_job()` with status/date/assessment checks
- CLI filtering: `--skip-before-date`, `--skip-rejected`, `--skip-assessed`
- Tests: 24 new tests covering all filters
- Documentation: CLAUDE.md updated with examples

**Current Usage Example:**
```bash
uv run python -m src.cli review --merge-all --skip-before-date 2026-07-01 --skip-rejected --skip-assessed
```

### ❌ Not Implemented (scope for this issue)
- Status visibility summaries (CLI output showing "Pending review: 8", "Already assessed: 42", etc.)
- `--new-only` / `--all` convenience flags (replaced by `--skip-*` equivalents)
- `--score-threshold` flag for assess command (filter jobs by min CV match score)
- Interactive re-review options (show prior decisions + allow re-review choice)
- Job detail view with processed dates before review (show when job was crawled/reviewed/assessed)

## Goals

### Goal 1: Pipeline Visibility (High Priority)
Show users what jobs will be processed before filtering:

**Example Output:**
```
Pipeline Status:
  Total jobs: 127
  Pending review: 8         ← Ready for review
  Already assessed: 92      ← Would be skipped
  Rejected: 23              ← Would be skipped
  Duplicates: 4             ← Marked as duplicate

Applying filters: --skip-before-date 2026-07-01 --skip-assessed
→ Will process: 8 jobs
→ Will skip: 119 jobs
```

### Goal 2: Quality-Based Assessment Filtering (Medium Priority)
Skip jobs below confidence threshold during assessment:

**Use Case**: "I only want to review jobs where CV match ≥ 75% before assessment"

```bash
uv run python -m src.cli assess --cv data/cv.json --score-threshold 75
# Only assesses jobs with prior_match_score >= 75
```

### Goal 3: Interactive Re-Review Workflow (Medium Priority)
Allow users to revisit prior decisions:

**Current Behavior**: Review → confirm/reject → locked
**Proposed Behavior**: Show prior decisions with option to re-review

```bash
uv run python -m src.cli review --interactive --allow-re-review
# When showing job:
#   [Prior: confirmed on 2026-07-01]
#   Confirm / Reject / Re-review: _
```

### Goal 4: Job Timeline Visibility (Low Priority)
Show full lifecycle before review:

```
Job: Machine Learning Engineer @ TechCorp
─────────────────────────────────────────
Crawled:     2026-07-01 14:22 UTC
Preprocessed: 2026-07-01 14:23 UTC
Status:      pending_review
Tokens:      742 (estimated $0.002)
─────────────────────────────────────────
[Confirm] [Reject] [Skip]
```

## Technical Approach

### 1. Pipeline Visibility (CLI Output)
- Add `--show-stats` flag to `review` command
- Query counts: `get_stats()` in JobStore
- Display before processing:
  ```sql
  SELECT status, COUNT(*) as count FROM jobs GROUP BY status;
  SELECT assessment_id IS NOT NULL as assessed, COUNT(*) FROM jobs GROUP BY assessed;
  ```

### 2. Score Threshold Filtering
- Add `--score-threshold` to `assess` command
- Query: Filter jobs by `match_score >= threshold` before API calls
- Update `get_jobs_needing_assessment()` to accept optional `min_score` parameter

### 3. Interactive Re-Review
- Add `--allow-re-review` flag to `review` command
- Track prior review decision in `job_reviews` table (add `reviewed_at`, `prior_status`)
- When processing: Check for prior decision, show it, ask user
- Store re-review in separate audit table

### 4. Job Timeline
- Add computed fields in response: `crawled_at`, `preprocessed_at`, `reviewed_at`, `assessed_at`
- Display in interactive review view (before confirmation prompt)

## Files to Modify

| File | Change |
|------|--------|
| `src/storage/db.py` | Add `get_stats()`, update `get_jobs_needing_assessment()` with min_score param |
| `src/cli.py` | Add `--show-stats`, `--score-threshold`, `--allow-re-review` flags |
| `src/verification/verify.py` | Display job timeline; show prior decisions if re-review enabled |
| `src/models/job.py` | Add `preprocessed_at`, `reviewed_at`, `assessed_at` timestamps (optional fields) |
| `tests/test_storage.py` | Add tests for filtering by score, stats queries |
| `tests/test_cli.py` | Add tests for new flags (--show-stats, --score-threshold, --allow-re-review) |
| `CLAUDE.md` | Document new flags, workflow examples |

## Success Criteria

- [ ] `--show-stats` displays job counts by status before processing
- [ ] `--score-threshold` filters assess jobs by min CV match score
- [ ] `--allow-re-review` shows prior decisions + allows user choice to re-review
- [ ] Job timeline visible in interactive review (crawled_at, reviewed_at, assessed_at)
- [ ] 10+ new tests covering filtering, stats, re-review logic
- [ ] CLAUDE.md updated with workflow examples for each feature
- [ ] No breaking changes to existing CLI commands
- [ ] All existing tests passing

## Acceptance Criteria

**PR ready to merge when:**
1. ✅ All success criteria met
2. ✅ GitHub Actions passing (tests, linting, type checking)
3. ✅ Code review approved
4. ✅ Documentation updated

## Related Issues

- **Closes context**: Issue #100 (partial) - core filtering implemented, these features are follow-up
- **Related**: PR #101 - current partial implementation

## Implementation Phases

**Phase 1** (Priority: High): Pipeline Visibility
- Add `--show-stats` flag
- Implement `get_stats()` query
- Display before review starts

**Phase 2** (Priority: Medium): Score Threshold Filtering
- Add `--score-threshold` to assess command
- Filter jobs pre-API
- Add tests

**Phase 3** (Priority: Medium): Interactive Re-Review
- Add `--allow-re-review` flag
- Track prior decisions
- Show choice to user

**Phase 4** (Priority: Low): Job Timeline
- Add computed timestamps
- Display in review view
- Document in CLAUDE.md

## Notes

- This is a follow-up to issue #100 (not a blocker)
- Recommended approach: Implement Phase 1 (visibility) first, then phases 2-3 (interactivity)
- Phase 4 (timeline) can ship independently or with Phase 1
- Estimated effort: 2-3 days for full feature set
- Can be split into multiple PRs if preferred (one per phase)
