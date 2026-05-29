# Issue #19: POC - Test Crawl Workflow Implementation Plan

**Issue**: #19 🕷️ POC: Test Crawl Workflow on Real Career Page
**Target**: https://carbonrobotics.com/job-openings
**Objective**: Validate end-to-end 6-phase ATS Playground workflow on real data
**Status**: Planning & Phase 1 Implementation
**Time Estimate**: 25–40 minutes (Phase 1) + 20–30 minutes per subsequent phase

---

## Executive Summary

This POC tests the complete ATS Playground workflow (crawl → preprocess → verify → assess → store → export) on a real company career page (Carbon Robotics). The goal is to:

1. Validate all 6 phases work end-to-end
2. Identify and fix any extraction/parsing issues
3. Improve CSS selector documentation
4. Provide a reusable template for similar sites
5. Gather cost metrics (token savings, API costs)

**Key Challenge**: Squarespace-based careers page with JavaScript-based rendering

---

## Phase 1: Configuration & Crawl Setup (ACTIVE)

### Objective
Configure the crawler to extract job openings from Carbon Robotics careers page using CSS selectors discovered via Playwright browser inspection.

### Tasks

#### Task 1.1: HTML Structure Analysis
**Status**: In Progress

**Approach**:
1. Fetch raw HTML to understand initial structure
2. Use Playwright to render page with full JavaScript execution
3. Save rendered HTML for manual inspection
4. Identify potential job container selectors

**Key Findings**:
- **Platform**: Squarespace (detected from HTML metadata)
- **Rendering**: JavaScript-based (no job listings in static HTML)
- **Structure**: Likely uses `.collection-item` or `.product-item` pattern
- **Wait Strategy**: Need to wait for networkidle before extraction

**Commands**:
```bash
# Render page with Playwright and inspect structure
cd /home/pluto-atom-4/Documents/full-stack/ats-playground
uv run python << 'EOF'
import asyncio
from playwright.async_api import async_playwright

async def inspect():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://carbonrobotics.com/job-openings", wait_until="networkidle")

        # Save rendered content
        content = await page.content()
        with open("/tmp/carbon_rendered.html", "w") as f:
            f.write(content)

        # Find potential job containers
        items = await page.query_selector_all('[class*="item"], [class*="job"], [class*="position"]')
        print(f"Found {len(items)} potential job containers")

        # Try to find links to job details
        links = await page.query_selector_all('a[href*="job"], a[href*="position"], a[href*="careers"]')
        print(f"Found {len(links)} potential job links")

        await browser.close()

asyncio.run(inspect())
EOF
```

**Expected Output**:
- Rendered HTML saved to `/tmp/carbon_rendered.html`
- Count of job containers and links
- Identification of main container class/id

---

#### Task 1.2: CSS Selector Discovery ✅ COMPLETE

**Key Discovery**: Carbon Robotics uses **Greenhouse Job Board** (not static Squarespace content)

**Actual Target URL**: `https://job-boards.greenhouse.io/embed/job_board?for=carbonrobotics`

**Job Structure Found**:
```html
<tr class="job-post">
  <td class="cell">
    <a href="https://carbonrobotics.com/job-openings?gh_jid=4673637006" target="_top">
      <p class="body body--medium">Deep Learning Engineer</p>
      <p class="body body__secondary body--metadata">Seattle, WA</p>
    </a>
  </td>
</tr>
```

**CSS Selectors Discovered**:
```json
{
  "container": "tr.job-post",
  "link": "tr.job-post a[href*='gh_jid']",
  "title": "p.body.body--medium",
  "location": "p.body__secondary.body--metadata"
}
```

**Job Count**: 26 jobs available
**Departments**: Deep Learning, Electrical Engineering, Mechanical Engineering, Software Engineering, Field Operations, Manufacturing, People Operations, Sales, Software Support

**Implementation Simplification**:
- Don't parse complex Squarespace + iframe
- Target Greenhouse embed directly (standard HTML structure)
- Selectors are simple and stable (used across Greenhouse boards)

**Command** (after manual inspection or browser DevTools):
```bash
# Test selectors with Playwright
uv run python << 'EOF'
import asyncio
from playwright.async_api import async_playwright

async def test_selectors():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://carbonrobotics.com/job-openings", wait_until="networkidle")

        # Test container selector
        containers = await page.query_selector_all(".collection-item")  # REPLACE WITH ACTUAL
        print(f"Found {len(containers)} containers with .collection-item")

        # Test each container for required fields
        for i, container in enumerate(containers[:3]):  # Test first 3
            title = await container.query_selector("h2")
            desc = await container.query_selector("p")
            link = await container.query_selector("a")

            if title:
                title_text = await title.inner_text()
                print(f"Job {i+1} Title: {title_text[:50]}...")

            if link:
                url = await link.get_attribute("href")
                print(f"Job {i+1} URL: {url}")

        await browser.close()

asyncio.run(test_selectors())
EOF
```

---

#### Task 1.3: Configuration Entry

**File**: `config/companies.json`

**Template** (to be filled with discovered selectors):
```json
{
  "id": "carbon_robotics",
  "name": "Carbon Robotics",
  "url": "https://carbonrobotics.com/job-openings",
  "enabled": true,
  "description": "Laser weeding robotics company based in Seattle, WA. Squarespace-based careers page with JavaScript rendering.",

  "crawler": {
    "type": "single_page",
    "headless": true,
    "timeout_ms": 30000,
    "delay_between_pages_ms": 2000,
    "max_pages": 1
  },

  "job_selectors": {
    "container": "SELECTOR_FROM_TASK_1.2",
    "title": "SELECTOR_FROM_TASK_1.2",
    "description": "SELECTOR_FROM_TASK_1.2",
    "url": "SELECTOR_FROM_TASK_1.2",
    "location": "SELECTOR_FROM_TASK_1.2 (optional)"
  },

  "selectors_fallback": [
    {
      "container": "FALLBACK_CONTAINER_SELECTOR",
      "title": "FALLBACK_TITLE_SELECTOR",
      "description": "FALLBACK_DESCRIPTION_SELECTOR"
    }
  ],

  "wait_for": {
    "selector": "FIRST_JOB_CONTAINER_SELECTOR",
    "timeout_ms": 30000
  },

  "cleanup_patterns": [
    "Apply Now",
    "Share this job",
    "Job ID:",
    "Posted:"
  ]
}
```

**Steps**:
1. Copy `config/companies.json` locally if not already done
2. Add the Carbon Robotics entry with discovered selectors
3. Verify JSON syntax is valid
4. Commit to feature branch

---

#### Task 1.4: Validation & Testing

**Objective**: Verify crawl command successfully extracts jobs

**Steps**:
```bash
# Ensure all dependencies are installed
cd /home/pluto-atom-4/Documents/full-stack/ats-playground
uv sync

# Run crawl command
uv run python -m src.cli crawl --config config/companies.json

# Check extracted jobs
ls -la data/extracted_jobs/

# Inspect extracted data
head -100 data/extracted_jobs/carbon_robotics*.json

# Verify counts
cat data/extracted_jobs/carbon_robotics*.json | grep -c "title"
```

**Success Criteria**:
- ✅ Crawl command completes without errors
- ✅ At least 3 job files created in data/extracted_jobs/
- ✅ Each job has populated fields: title, description, url
- ✅ No obvious parsing errors or truncation
- ✅ JSON is valid (can be parsed)

**Expected Output**:
```
$ uv run python -m src.cli crawl --config config/companies.json
[INFO] Starting crawl for Carbon Robotics...
[INFO] Browser launched (headless mode)
[INFO] Navigating to https://carbonrobotics.com/job-openings
[INFO] Waiting for job listings...
[INFO] Found 5 job openings
[INFO] Extracted jobs saved to data/extracted_jobs/
[SUCCESS] Crawl complete: 5 jobs extracted
```

---

## Phase 2: Preprocessing & Cost Analysis

**Objective**: Clean HTML, chunk text, count tokens, estimate costs

**Tasks**:
1. Run preprocess command on extracted jobs
2. Verify token count estimates vs raw HTML
3. Document token reduction percentage (target: 80–90%)
4. Review semantic chunking quality

**Expected Metrics**:
- Raw HTML: ~5,000–8,000 tokens per job
- Cleaned text: ~600–1,000 tokens per job
- Savings: ~85% of tokens
- Cost reduction: $0.60 → $0.07 per 100 jobs

**Command**:
```bash
uv run python -m src.cli preprocess --show-estimates
```

---

## Phase 3: User Verification

**Objective**: Review extracted jobs and confirm before expensive LLM calls

**Tasks**:
1. Run interactive review
2. Confirm/reject each job
3. Document any extraction issues
4. Mark approved jobs as "confirmed"

**Command**:
```bash
uv run python -m src.cli review --interactive
```

**Expected Output**: Jobs marked as "confirmed" in database

---

## Phase 4: Assessment

**Objective**: Score jobs against user CV using Claude 3.5 Sonnet

**Tasks**:
1. Prepare sample CV (data/cv.json)
2. Run assessment command
3. Verify Claude API integration works
4. Check cost tracking and token counts

**Command**:
```bash
uv run python -m src.cli assess --cv data/cv.json
```

---

## Phase 5: Storage & Export

**Objective**: Store results in SQLite and export reports

**Tasks**:
1. Verify jobs stored in ats_playground.db
2. Test FTS5 full-text search
3. Export markdown report
4. Validate report structure

**Commands**:
```bash
# Query jobs
uv run python -m src.cli query --keyword "robot"

# Export report
uv run python -m src.cli export --format md --output data/assessments/carbon_report.md
```

---

## Success Criteria

### Phase 1 (Crawl Setup)
- ✅ At least 3 job openings successfully extracted
- ✅ CSS selectors discovered and tested
- ✅ Configuration entry added to config/companies.json
- ✅ Crawl command runs without errors
- ✅ All job fields populated (title, description, URL)
- ✅ Fallback selectors documented (optional)

### Overall POC (All Phases)
- ✅ End-to-end workflow completes without intervention
- ✅ Token reduction ≥80% verified
- ✅ Assessment report generated successfully
- ✅ No data loss or corruption between phases
- ✅ Cost tracking shows expected savings

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| JavaScript rendering fails | No jobs extracted | Use Playwright headless + networkidle wait |
| Selectors break on page update | Maintenance burden | Test multiple items, use data attributes, fallbacks |
| Rate limiting | Crawl blocked | Add reasonable delays (2s between requests) |
| No pagination needed | Assumption wrong | Check for "load more" or multiple pages |
| Dynamic content | Jobs not visible | Wait for all content to load before extraction |

---

## Documentation References

- [ARCHITECTURE.md](../ARCHITECTURE.md) — 6-phase workflow overview
- [CRAWL.md](../CRAWL.md) — Configuration schema, CSS selector tips, Squarespace patterns
- [CLI.md](../CLI.md) — Command reference and usage
- [VERIFY.md](../VERIFY.md) — User verification flow
- [PREPROCESS.md](../PREPROCESS.md) — Token counting and chunking
- [STORAGE.md](../STORAGE.md) — Database schema and export formats

---

## Timeline

| Phase | Tasks | Estimated Time | Status |
|-------|-------|-----------------|--------|
| **1** | Crawl setup & validation | 25–40 min | IN PROGRESS |
| **2** | Preprocessing | 5–10 min | Pending |
| **3** | User verification | 5–10 min | Pending |
| **4** | Assessment | 10–15 min | Pending |
| **5** | Storage & export | 5–10 min | Pending |
| **Total** | All phases | 50–85 min | 0% complete |

---

## Implementation Notes

### Squarespace-Specific Gotchas

1. **Dynamic class names**: Squarespace often generates unique class names (e.g., `_q1a2b3c4`). Use:
   - Substring matching: `[class*="item"]`
   - Data attributes: `[data-item-id]`
   - Tag-based selectors: `div > h2` (positional)

2. **CORS & mixed content**: May have issues loading external assets. Not a problem for our crawler since we render server-side.

3. **Lazy loading**: Images might be lazy-loaded. Not relevant for job text extraction.

4. **SEO optimization**: Job data might be in `<script type="application/ld+json">` (structured data). Could be alternative extraction method if CSS selectors fail.

### Selector Testing Best Practices

- Test on **multiple items** (not just first item)
- Verify **text extraction** (inner_text, not just element count)
- Check for **partial matches** (ensure selectors don't over-match)
- Test **fallback selectors** separately
- Document **edge cases** (empty fields, missing fields)

### Cost Tracking

Expected costs for this POC:

```
Phase 1 (Crawl): $0.00 (no API calls)
Phase 2 (Preprocess): $0.00 (local processing)
Phase 3 (Verify): $0.00 (user decision)
Phase 4 (Assess): ~$0.005–0.010 (Claude API for 3–5 jobs)
Phase 5 (Export): $0.00 (local processing)

Total: ~$0.01 (negligible)
```

Compare to raw HTML approach: ~$0.06–0.10 for same 3–5 jobs

**Savings**: ~75–80% 💰

---

## Blockers & Open Questions

1. **Does Carbon Robotics have pagination?**
   - How many jobs total? (affects time estimate)
   - Single page or multiple pages?

2. **Are there any rate limits?**
   - Test with single crawl, then verify repeated requests allowed

3. **Job types/departments?**
   - E.g., Engineering, Sales, Ops
   - Affects grouping/filtering in reports

---

## Next Steps

1. **Execute Task 1.1**: Browser inspection with Playwright
2. **Document selectors**: Create task 1.2 selector list
3. **Add config entry**: Update config/companies.json
4. **Test crawl**: Run validation command
5. **Document findings**: Add to this file
6. **Move to Phase 2**: Preprocessing once crawl validated

---

## Author & History

- **Created**: 2026-05-27
- **Status**: Phase 1 Planning
- **Issue**: #19
- **Target**: Carbon Robotics POC
