## Draft a github issue which parent #100


- The following recommentaion is a scope.
- Write To './gh-issue-draft.md'


---

Reviewed PR #101 against issue #100 requirements:

Implemented:
- ✅ Database schema: crawled_at timestamp + index
- ✅ Storage query methods: assessment status, jobs needing assessment, score threshold, date filtering
- ✅ Reviewer filtering: should_skip_job() with status/date/assessment checks
- ✅ CLI filtering: --skip-before-date, --skip-rejected, --skip-assessed
- ✅ Tests: 24 new tests covering all filters
- ✅ Documentation: CLAUDE.md updated with examples

Not Implemented (from original proposal):
- ❌ Status visibility summaries (CLI output enhancements showing "Pending review: 8", etc.)
- ❌ --new-only / --all flags (replaced with --skip-* equivalents)
- ❌ --score-threshold flag for assess command
- ❌ Interactive re-review options (showing prior decisions + re-review choice)
- ❌ Job detail view with processed dates before review

Assessment:

Issue #100 is partially closable. Core problem solved (selective processing), but implementation diverged from proposal:

- Implemented: Skip filters (date, status, assessment)
- Proposed: --new-only/--all flags + score threshold + interactive re-review UI

Recommendation:
- Close as "Completed (partial)" if --skip-* flags m
  --skip-before-date/--skip-rejected/--skip-assessed satisfy original use case.
- Create follow-up issue for missing features (statueview, --score-threshold)
- PR #101 ready to merge as-is
