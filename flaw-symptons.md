## Draft a github issue to investigate the flaw of sub command review

- Draft the issue to ./gh-issue-draft.md


## Reproduce steps

When: run ' uv run python -m src.cli review --allow-re-review'
Then: a user response the skip for the first job review out of four
Expected: the user can check the second job
Actual: the system outputs the summary and exits


## sub command review outputs

```text
➜ uv run python -m src.cli review --allow-re-review
⚠  Using hardcoded default for review. For multi-company workflows, use: review --merge-all

👀 Starting job review (4 jobs total)


🔍 Job 1 of 4: Deep Learning Quality Specialist
   Company: CompanyD
   Location: Seattle, WA
   Tokens: 1273 | Cost: $0.000005
   Status: pending_review | Crawled: not processed | Reviewed: 2026-07-09 21:10
   Content: The Carbon Robotics LaserWeeder™ leverages advanced robotics, computer vision, A...

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
   Skipped:         4

   Ready for Phase 4 Assessment:
     • Jobs: 0
     • Est. LLM cost: $0.000000
     • Avg tokens/job: 0

```

## reference

- 'src/verification/reviewer.py'
