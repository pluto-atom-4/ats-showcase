# Issue #22: Fix Mock Response Parsing in LLM Assessment Tests

**Issue**: Fix mock response parsing in LLM assessment tests
**Status**: Planning
**Priority**: Medium (blocking quality gates, but not production)
**Estimated Time**: 30-45 minutes
**Dependencies**: PR #21 merged (import/fixture fixes complete)

---

## Overview

Three tests in `tests/test_assessment.py` are currently marked as `xfail` (expected failures) because mock Anthropic API responses are not being parsed correctly by `LLMProvider.assess_job()`. When JSON parsing fails, the code returns fallback scores (overall_score=50, actual_cost=0.0) instead of expected values.

**Current State:**
- ✅ Tests marked as `@pytest.mark.xfail` (CI passes, tests noted as expected to fail)
- ✅ 71 tests passing, 3 xfailed (total 74 tests)
- ⚠️ Real issue: mock responses don't simulate actual Claude API responses correctly

**Expected Outcome:**
- Remove xfail markers
- All 3 tests pass with actual assessment values
- 74 tests passing (71 + 3 previously xfailed)

---

## Problem Analysis

### Failing Tests

| Test | Location | Current Error | Root Cause |
|------|----------|---------------|-----------|
| `test_assess_job_success` | test_assessment.py:115 | assert 50 == 78 | Mock response not parsed; fallback returned |
| `test_assess_job_with_markdown_json` | test_assessment.py:131 | assert 50 == 78 | Markdown JSON wrapper parsing failure |
| `test_assess_job_token_cost_calculation` | test_assessment.py:164 | assert 0.0 == 2.55e-06 | Cost calculation on fallback (0) instead of real |

### Code Flow

```
Mock Setup (conftest.py)
    ↓
Mock Response Created (test_assessment.py)
    ├─ response.usage.input_tokens = 600
    ├─ response.usage.output_tokens = 50
    ├─ response.content[0].text = JSON (or markdown-wrapped JSON)
    └─ client.messages.create.return_value = response
    ↓
LLMProvider.assess_job() Called
    ├─ Attempts JSON parsing
    ├─ If parsing fails:
    │   ├─ Log: WARNING "Failed to parse response..."
    │   ├─ Retry with fallback logic
    │   └─ Return AssessmentResult(overall_score=50, actual_cost=0.0)
    └─ If parsing succeeds:
        ├─ Extract scores from JSON
        ├─ Calculate actual_cost
        └─ Return AssessmentResult(overall_score=78, actual_cost=0.002)
    ↓
Test Assertion
    ├─ Expected: overall_score == 78
    └─ Actual: overall_score == 50 (fallback)
```

### Suspected Issues

1. **Mock response structure doesn't match real Anthropic response**
   - Real response: `response.content[0].text` contains the model's text
   - Mock setup: May not properly simulate this structure
   - Issue: Mock client may not be patched correctly at the right level

2. **JSON extraction logic mismatch**
   - Provider expects: Direct JSON in response.content[0].text
   - Test provides: Markdown-wrapped JSON in test_assess_job_with_markdown_json
   - May be: JSON extraction regex doesn't match actual response format

3. **Patch target is incorrect**
   - Current: `@patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})`
   - Issue: May not be patching the actual anthropic.Anthropic() constructor
   - Need to verify: Where is the client being instantiated in LLMProvider?

4. **Mock client doesn't behave like real client**
   - Real anthropic.Anthropic().messages.create() returns specific response object
   - Mock: May return MagicMock that doesn't have all required attributes
   - Need to verify: Are all attributes (usage, content, content[0].text) properly set?

---

## Investigation Checklist

### Step 1: Understand Current Mock Setup

**Files to Review:**
- [ ] `tests/conftest.py` - Look for `mock_anthropic` fixture definition
- [ ] `tests/test_assessment.py:100-115` - Find where fixture is used
- [ ] `src/llm/provider.py:40-60` - Check how client is instantiated

**Questions to Answer:**
- [ ] How is `@patch` being applied? (module path correct?)
- [ ] Does mock have all required attributes? (usage, content, content[0].text)
- [ ] Is the response structure exactly matching real Anthropic API?

### Step 2: Debug JSON Parsing

**Files to Review:**
- [ ] `src/llm/provider.py:150-180` - JSON extraction logic
- [ ] Check for regex patterns that extract JSON from responses
- [ ] Look for markdown handling (`\`\`\`json....\`\`\``)

**Debug Steps:**
- [ ] Add print() statements in tests to show actual mock response
- [ ] Verify mock.content[0].text is set correctly
- [ ] Check if JSON is being wrapped in markdown
- [ ] Trace through parsing logic to find exact failure point

### Step 3: Compare with Real Response

**Check:**
- [ ] Real Anthropic API response structure (from docs or live call)
- [ ] Token calculation: Does response.usage contain input_tokens + output_tokens?
- [ ] Content structure: Is content always [0]? What about content_type?

### Step 4: Fix Mock Setup

**Options:**
1. **Option A: Fix mock response structure**
   - Ensure mock exactly matches real Anthropic response
   - May need: `response.content = [MagicMock(text=json_str, type="text")]`

2. **Option B: Use real client with cassette/recording**
   - Use pytest-vcr to record real API call
   - Replay in tests (no live API calls)
   - More realistic but requires setup

3. **Option C: Patch at lower level**
   - Patch `anthropic.Anthropic.messages.create()` instead of constructor
   - May be more robust

---

## Implementation Plan

### Phase 1: Investigation (10 min)

1. **Review conftest.py**
   - Find `mock_anthropic` fixture
   - Understand current patch strategy
   - Document fixture code

2. **Add debug output to tests**
   - Temporarily add print statements
   - Show what mock.content[0].text actually contains
   - Run tests to see exact error point

3. **Check LLMProvider parsing logic**
   - Find JSON extraction code
   - Identify where parsing fails
   - Note any regex patterns or markdown handling

### Phase 2: Fix Mock (15-20 min)

1. **Update mock response structure**
   - Fix response.content to be list with proper MagicMock
   - Ensure text field contains valid JSON (or markdown-wrapped JSON)
   - Test with both JSON and markdown-wrapped variants

2. **Verify patch target**
   - Ensure @patch is targeting correct module path
   - May need to patch `src.llm.provider.Anthropic` instead of `anthropic.Anthropic`

3. **Test each variant**
   - test_assess_job_success: Plain JSON
   - test_assess_job_with_markdown_json: Markdown-wrapped JSON
   - test_assess_job_token_cost_calculation: Verify cost calculation

### Phase 3: Validation (5-10 min)

1. **Remove xfail markers**
   ```python
   # Before:
   @pytest.mark.xfail(reason="Mock response parsing not working correctly. See issue #22.")
   def test_assess_job_success(self, mock_anthropic):

   # After:
   def test_assess_job_success(self, mock_anthropic):
   ```

2. **Run tests locally**
   ```bash
   export PYTHONPATH="/path/to/src:$PYTHONPATH"
   uv run pytest tests/test_assessment.py::TestLLMProvider::test_assess_job_success -v
   ```

3. **Verify all 3 pass**
   ```bash
   uv run pytest tests/test_assessment.py::TestLLMProvider -v
   # Expected: 3 passed (not xfailed)
   ```

4. **Run full suite**
   ```bash
   uv run pytest tests/ -q
   # Expected: 74 passed (not "71 passed, 3 xfailed")
   ```

---

## Files to Modify

| File | Change | Reason |
|------|--------|--------|
| `tests/conftest.py` | Update `mock_anthropic` fixture | Fix mock response structure |
| `tests/test_assessment.py` | Remove `@pytest.mark.xfail` from 3 tests | Tests should now pass |
| `docs/implementation-planning/issue-22-mock-parsing-fix.md` | Update status when complete | Track progress |

---

## Success Criteria

- [ ] Mock response structure verified to match real Anthropic API
- [ ] test_assess_job_success passes with overall_score == 78
- [ ] test_assess_job_with_markdown_json passes with markdown parsing
- [ ] test_assess_job_token_cost_calculation passes with correct cost
- [ ] All 3 tests pass locally (not xfailed)
- [ ] Full test suite: 74 tests passing (no xfails)
- [ ] Pre-commit hooks pass (black, ruff, mypy)
- [ ] GitHub Actions passes with Python 3.11 and 3.12

---

## Related Files & References

**Core Files:**
- `src/llm/provider.py` - LLMProvider.assess_job() implementation
- `tests/test_assessment.py` - The 3 failing tests
- `tests/conftest.py` - Mock fixture setup

**Documentation:**
- `docs/ASSESS.md` - Phase 4 assessment details
- `docs/dev-note/issue-19-poc-evaluation-guide.md` - POC guide (references all 74 tests)

**Issue #22:**
- GitHub: https://github.com/pluto-atom-4/ats-playground/issues/22
- Commit introducing xfail: b325203 (in feat/issue-19)

---

## Estimated Effort Breakdown

| Task | Time | Effort |
|------|------|--------|
| Investigation (debug, understand issue) | 10 min | Low |
| Fix mock response structure | 15 min | Medium |
| Validation & testing | 5 min | Low |
| Pre-commit & final checks | 5 min | Low |
| **Total** | **35 min** | **Medium** |

---

## Next Session Checklist

- [ ] Clone latest main (with PR #21 merged)
- [ ] Read this plan
- [ ] Run failing tests locally to reproduce
- [ ] Follow Investigation Checklist (Phase 1)
- [ ] Implement fixes (Phase 2)
- [ ] Validate (Phase 3)
- [ ] Push to new branch (e.g., `fix/issue-22-mock-parsing`)
- [ ] Create PR with explanation
- [ ] Update this document with resolution

---

**Document Version**: 1.0
**Created**: 2026-05-29
**Status**: Planning
**Last Updated**: 2026-05-29
