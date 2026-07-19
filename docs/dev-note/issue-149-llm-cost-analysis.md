# Issue #149: LLM Cost Optimization Analysis

**Date**: 2026-07-18  
**Branch**: `feat/issue-149-llm-cost-optimization`  
**Issue**: https://github.com/pluto-atom-4/ats-showcase/issues/149

## Executive Summary

Current project uses **Claude Opus 4.1** ($15/1M input tokens) for job assessment. Testing whether cheaper models (Haiku, Sonnet) maintain accuracy.

## Cost Comparison

| Model | Cost | Savings | Use Case |
|-------|------|---------|----------|
| Claude Opus 4.1 | $15/1M | Baseline | Current (complex reasoning) |
| Claude Sonnet 5 | $3/1M | 80% | Good balance |
| Claude Haiku 4.5 | $0.80/1M | 95% | Fast, straightforward tasks |

## Task Analysis

Job assessment workflow:
```
Input:  CV (text) + Job Description (chunked)
↓
Process: Pattern match + score (4 categories)
↓
Output: JSON (overall, tech, seniority, location scores + reasoning)
```

**Complexity**: Medium
- Not open-ended reasoning
- Structured output required
- Quantitative scoring (0-100)
- No multi-step inference chains

**Haiku Risks**:
- May miss subtle tech skill nuances
- Seniority judgment less precise on edge cases
- Shorter summaries/reasoning
- But: Human review phase catches major errors

## Test Plan

**Script**: `tests/test_llm_comparison.py`

Tests on 1 sample job + CV:
1. Run assessment with Haiku, Sonnet, Opus
2. Compare scores (overall, tech, seniority, location)
3. Calculate variance
4. Evaluate summaries

**Criteria**:
- ✅ Variance ≤5 points → Use Haiku (95% savings)
- ⚠️ Variance 5-10 points → Use Sonnet (80% savings)
- ❌ Variance >10 points → Keep Opus

## Expected Outcomes

### Scenario 1: Haiku Viable (prob ~60%)
Switch to Haiku, reduce costs 95%. Requires:
- Update `src/llm/provider.py` MODEL constant
- Update pricing in LLMProvider
- Run full test suite to verify quality
- Update CLAUDE.md

### Scenario 2: Sonnet Viable (prob ~30%)
Switch to Sonnet, reduce costs 80%. Requires:
- Update MODEL to Sonnet 5
- Update pricing
- Test suite
- CLAUDE.md update

### Scenario 3: Opus Required (prob ~10%)
Stay with Opus. Requires:
- Fix pricing (currently $3 for 3.5, should be $15 for Opus 4.1)
- Document decision

## Files Changed

- `tests/test_llm_comparison.py` — New comparison test script
- `src/llm/provider.py` — Will update MODEL + pricing based on results
- `CLAUDE.md` — Will update tech stack section

## Running Tests

Requires ANTHROPIC_API_KEY:
```bash
export ANTHROPIC_API_KEY='sk-ant-...'  # pragma: allowlist secret
uv run pytest tests/test_llm_comparison.py -v -s
```

## Next Steps

1. Run comparison test (manual via pytest)
2. Analyze variance + reasoning quality
3. Decide on model
4. Update provider.py
5. Run full test suite
6. Update CLAUDE.md
7. Commit + PR

---

**Status**: Testing phase  
**Assigned**: @claude  
**Depends on**: None
