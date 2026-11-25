# Parsing Job Postings: Crawler and Selector Contract

**Last Updated**: 2026-11-25
**Scope**: Listing-page crawl and optional detail-page fetch in `src/browser/crawler.py`, driven by `config/companies.json`

---

## Overview

`Crawler` loads each enabled company's career page in Chromium (Playwright), selects job containers with the CSS selectors in that company's `selectors` block, and returns `JobPosting` objects with `status="pending_review"`. If the company's `crawler` block sets `fetch_detail`, it also opens each job link and reads the description and requirements from the detail page.

The crawler does not clean HTML. For HTML-to-text conversion, see the `clean_html()` docstring in `src/parsers/html_to_markdown.py`.

Run it with:

```bash
uv run python -m src.cli crawl --config config/companies.json
uv run python -m src.cli crawl --config-dir config
```

---

## Component Architecture

### Crawler (`src/browser/crawler.py`)

| Method | Purpose |
|--------|---------|
| `__init__(headless=True, timeout_ms=30000)` | Store settings; no browser is started |
| `initialize()` | Start Playwright, launch Chromium, create one browser context |
| `close()` | Close context, browser, and Playwright |
| `crawl_company(company_name, url, selectors, crawler_config=None)` | Crawl one listing page; returns `[]` if the page-level flow fails |
| `crawl_multiple(companies)` | Crawl each company in turn; calls `initialize()` and `close()` itself |
| `_extract_job_from_container(page, container, company_name, selectors, base_url, crawler_config)` | Build one `JobPosting` from a container; returns `None` if there is no title |
| `_extract_text(element, selector)` | Stripped `text_content()` of the first match |
| `_extract_link(element, selector)` | `href` attribute of the first match |
| `_extract_html(element, selector)` | `inner_html()` of the first match; defined but not called by the crawl path |
| `_fetch_job_detail(job_url, selectors)` | Open the detail page; returns `(description, requirements)` |
| `_fetch_iframe_via_frame(page, inner_selector=None)` | Read iframe content through the Playwright frame API |
| `_extract_from_frame_element(frame, frame_index, selector)` | Fallback chain for an element inside a frame |
| `_extract_from_frame_body(frame, frame_index)` | Fallback chain for a frame's `<body>` |

### Crawler Configuration (`crawler` block)

The `crawl_multiple` method passes each company's `crawler` block (or `{}`) to `crawl_company`. The crawler reads exactly these four keys:

| Key | Default | Effect |
|-----|---------|--------|
| `wait_for_selector` | `selectors["job_container"]` | Waited for up to 10 s after page load. A timeout logs a warning and the crawl continues. |
| `delay_ms` | `2000` | Fixed sleep after the wait, for client-side rendering |
| `fetch_detail` | off | When truthy, each job with a link gets a detail-page fetch |
| `max_jobs_debug` | no cap | Stops processing a company's containers after this many |

The 10 s wait timeout is hardcoded. Navigation always uses `wait_until="networkidle"`, which is not configurable.

### Browser Lifecycle

```python
self.playwright = await async_playwright().start()
self.browser = await self.playwright.chromium.launch(headless=self.headless)
self.context = await self.browser.new_context()
```

- **Headless**: taken from the constructor; the CLI passes `--headless` (default on).
- **One context** is shared by all companies. Each listing page and each detail page is a separate `Page`.
- **Timeout**: `page.set_default_timeout(timeout_ms)` is set on every page. The default is 30 000 ms, and the CLI `--timeout` option (default 30000) is passed through.
- `crawl_company` calls `initialize()` only when the browser or context is missing. `crawl_multiple` always calls it.
- The listing page is closed only on the success path. If navigation fails, the page stays open until `close()` closes the context.

---

### Per-Company Selectors

Selectors come from the `selectors` object of each company entry in `config/companies.json`.

| Key | Required in code | Read by | Used for |
|-----|------------------|---------|----------|
| `job_container` | Yes | `selectors["job_container"]` | One match per job. A missing key raises `KeyError`, which `crawl_company` logs; the company returns `[]`. |
| `title` | No | `.get()` | Job title. A container with no title is skipped. |
| `location` | No | `.get()` | Job location. Defaults to `"Not specified"`. |
| `link` | No | `.get()` | Job URL from `href`, made absolute with `urljoin` against the company `url`. `url` is `None` if absent. |
| `description_selector` | No | `.get()`, detail fetch only | Detail-page description. A plain element gives its `inner_html()`. An `<iframe>` goes through the frame path. |
| `inner_description_selector` | No | `.get()`, detail fetch only | Selector inside the iframe. Used only when `description_selector` matches an iframe. |
| `requirements_selector` | No | `.get()`, detail fetch only | Detail-page requirements from `text_content()`. See the known issue under Error Handling. |

The `description_selector`, `inner_description_selector`, and `requirements_selector` keys are read only when `fetch_detail` is truthy.

## Cleaning Raw HTML

The crawler stores HTML as it finds it. `description` is the raw `inner_html()` of the detail element, or raw HTML from the iframe frame API. Nothing in `src/browser/crawler.py` converts it to text.

- Conversion and boilerplate removal: `clean_html()` in `src/parsers/html_to_markdown.py`. Its docstring lists the pipeline.
- `src/parsers/html_cleaner.py` is deprecated and is not imported by the crawler.

---

## Data Flow: Listing Page to Job Postings

```
crawl_company(company_name, url, selectors, crawler_config)
  ↓
new Page; set_default_timeout(timeout_ms)
  ↓
goto(url, wait_until="networkidle")
  ↓
wait_for_selector(wait_selector, timeout=10 s)     [timeout: warning, continue]
  ↓
wait_for_timeout(delay_ms)
  ↓
query_selector_all(selectors["job_container"])       → containers
  ↓
for each container (stop after max_jobs_debug, if set):
  _extract_job_from_container(page, container, company_name, selectors, url, crawler_config)
    ├─ title, location, link     (_extract_text / _extract_link)
    ├─ no title → return None
    ├─ link = urljoin(url, link) when link is set
    ├─ fetch_detail and link → _fetch_job_detail(link, selectors)
    │     → (description, requirements); ("", None) on any failure
    ├─ id = generate_job_id(company, title, location or "Not specified", link)
    └─ return JobPosting(status="pending_review", crawled_at=utcnow)
  ↓
page.close(); return jobs
```

The crawl has no second pass. Detail pages are fetched inline, one job at a time, during the listing loop.

---

## Worked Example: TechCorp

`config/companies.json` is tracked. Its `TechCorp` entry, unchanged (the URL is a placeholder domain):

```json
{
  "companies": {
    "TechCorp": {
      "enabled": true,
      "name": "Tech Corp",
      "url": "https://techcorp.example.com/careers",
      "selectors": {
        "job_container": ".job-posting",
        "title": ".job-title",
        "description_selector": ".job-description",
        "location": ".job-location",
        "requirements_selector": ".job-requirements",
        "link": "a.job-link"
      },
      "crawler": {
        "fetch_detail": false
      }
    }
  }
}
```

What a run does with this entry:

1. `enabled: true` passes the CLI filter (`filter_enabled_companies`). The crawler never reads `enabled`.
2. `wait_for_selector` and `delay_ms` are not set, so the crawler waits for `.job-posting` (up to 10 s) and then sleeps 2000 ms.
3. For each `.job-posting`, `title`, `location`, and `link` are read. The link is made absolute against `https://techcorp.example.com/careers`.
4. `fetch_detail` is `false`, so `description_selector` and `requirements_selector` are not used. Each `JobPosting` has `description=""` and `requirements=None`.

To get descriptions and requirements, set `"fetch_detail": true`. The detail pages are then read through `description_selector` and `requirements_selector`.

**Illustrative only (not in the tracked config).** A description inside an iframe uses `inner_description_selector`:

```json
"selectors": {
  "job_container": "li.job",
  "title": "h3",
  "link": "a",
  "description_selector": "iframe#job-frame",
  "inner_description_selector": "div.job-body"
},
"crawler": {
  "fetch_detail": true
}
```

---

## Selector Discovery

1. Open the career page in DevTools (F12).
2. Pick selectors that match one element per job. Prefer `data-*` attributes and stable class names. Avoid generated class names.
3. Check each selector in the console. The container count must equal the number of jobs on the page:

```javascript
document.querySelectorAll(".job-posting").length            // one per job
document.querySelectorAll(".job-posting .job-title").length // should equal the line above
document.querySelector(".job-posting a.job-link")?.getAttribute("href")
```

A title count below the container count means some jobs will be dropped, because a container with no title is skipped.

---

## Error Handling

### Crawler-Level

| Scenario | What the code does |
|----------|--------------------|
| `goto` fails or times out | Outer `except` logs an error; `crawl_company` returns `[]`. Other companies still run. |
| `job_container` key missing | `KeyError` is caught by the same outer `except`; returns `[]`. |
| `wait_for_selector` times out | Warning is logged; the crawl continues with the delay and query. |
| Zero containers matched | `Found 0 job containers` is logged at info level; the loop does nothing; returns `[]`. |
| Container has no title | Warning `No title found in container`; the job is dropped. |
| Any other per-container exception | Warning `Failed to extract job i`; that job is skipped. |
| Detail fetch fails | `_fetch_job_detail` returns `("", None)`; the job is kept with an empty description. |
| Iframe content not found | Returns `""`, so the description is empty. |

The selector wait (`crawler.py:86-91`):

```python
try:
    await page.wait_for_selector(wait_selector, timeout=10000)
except Exception as e:
    logger.warning(f"Selector {wait_selector} not found: {e}")
```

The per-container call (`crawler.py:104-112`):

```python
try:
    job = await self._extract_job_from_container(
        page, container, company_name, selectors, url, crawler_config
    )
    if job:
        jobs.append(job)
except Exception as e:
    logger.warning(f"Failed to extract job {i}: {e}")
```

### Known Issue: `requirements` Type

When `fetch_detail` is on and `requirements_selector` matches, `_fetch_job_detail` returns a `str`. `JobPosting.requirements` is declared `Optional[List[str]]` (`src/models/job.py`). Pydantic rejects a `str` for that field. The `ValidationError` is caught in `_extract_job_from_container`, which returns `None`, so the job is dropped. This was confirmed offline with pydantic 2 against the same field type. It was not reproduced end-to-end.

---

## Performance

- **Companies run sequentially.** `crawl_multiple` creates one coroutine per company and awaits them one at a time in a `for` loop. There is no `asyncio.gather`, `create_task`, or semaphore in the crawler, so there is no concurrency limit, and there is no concurrency at all.
- **Jobs run sequentially within a company.** Each container is processed in turn.
- **Fixed waits per listing page:** `networkidle` load, then the `wait_for_selector` wait (up to 10 s), then `delay_ms` (default 2000 ms).
- **Fixed waits per detail page** (when `fetch_detail` is on): `networkidle` load, then 1000 ms. An iframe adds `networkidle` plus 500 ms.
- **One extra `Page` per job** with `fetch_detail`. It is closed in a `finally` block.
- **`max_jobs_debug`** caps the number of containers processed per company. Use it when testing.

---

## Data Model

### JobPosting Fields Set by the Crawler

The crawler constructs `JobPosting` (`src/models/job.py`) with these values:

| Field | Value |
|-------|-------|
| `id` | `generate_job_id(company, title, location, url)`, computed before the object is built |
| `title` | Stripped text of `title` selector |
| `company` | Company name key from the config |
| `location` | Stripped text of `location` selector, or `"Not specified"` |
| `url` | Absolute URL from `link`, or `None` |
| `description` | Detail-page raw HTML (or plain text from the iframe fallback), or `""` when detail fetch is off or fails |
| `requirements` | Detail-page text, or `None` (see the known issue above) |
| `salary_min`, `salary_max` | Always `None` |
| `posted_date` | Always `None` |
| `status` | `"pending_review"` |
| `crawled_at` | `datetime.utcnow()` at extraction |


### Job ID

`generate_job_id` (`src/id_generation/hash_generator.py`) normalizes company, title, and location, and takes the URL as an anchor. It hashes the result with SHA-256 and returns `{portal}:{hash[:16]}`, where `portal` comes from the URL (or `custom`). The same posting gets the same ID across runs.

### Status Lifecycle

```
crawler writes:  pending_review  →  confirmed | rejected
```

- The crawler writes `pending_review`. The `job_reviews` status column defaults to `'pending'` in `src/storage/schema.py`, but the crawler always sets `pending_review` explicitly.
- `assessed` is not stored in a column. `AssessmentStore.get_assessment_status` derives it at read time: it returns `"assessed"` when a `job_assessments` row exists for the job.

---

## Future Enhancements

Not implemented. None of these keys or code paths exist in `src/browser/crawler.py`:

- **Pagination.** No next-page selector or page limit is read. Only one listing page is loaded per company.
- **Salary and posted date.** `salary_min`, `salary_max`, and `posted_date` are always `None`.
- **Configurable wait strategies.** Only `wait_for_selector` and `delay_ms` are configurable. `networkidle` is hardcoded.
- **Concurrent companies.** Companies run one after another (see Performance).

---

## Debugging Guide

### Check Selectors Against the Live Page

Use the console snippets in [Selector Discovery](#selector-discovery). If a count is wrong, the container or title selector is the usual cause.

### Enable Debug Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("src.browser.crawler").setLevel(logging.DEBUG)
```

The crawler logs `Found N job containers`, per-job extraction, and `fetch_detail` decisions at debug level.

### Test One Company

Illustrative. Replace the URL with a real career page, and do not run it against a site you have not been asked to test.

```python
import asyncio

from src.browser.crawler import Crawler


async def main() -> None:
    crawler = Crawler(headless=False)
    try:
        jobs = await crawler.crawl_company(
            "TechCorp",
            "https://techcorp.example.com/careers",
            {
                "job_container": ".job-posting",
                "title": ".job-title",
                "location": ".job-location",
                "link": "a.job-link",
            },
            {"max_jobs_debug": 3},
        )
        for job in jobs:
            print(f"{job.title} @ {job.company}")
    finally:
        await crawler.close()


asyncio.run(main())
```

`crawl_company` returns `[]` on page-level failure without raising, so an empty result can mean either no jobs or a failed load. Check the log.

---

## Summary

The crawler in `src/browser/crawler.py`:

1. Loads each enabled company's listing page in headless Chromium.
2. Extracts title, location, and link from each `job_container` match using the company's selectors.
3. Optionally fetches each job's detail page for description and requirements (`fetch_detail`).
4. Returns `JobPosting` objects with `status="pending_review"`.

HTML-to-text conversion is `clean_html()` in `src/parsers/html_to_markdown.py`.

**Known gaps:**
- Companies are crawled sequentially.
- `requirements` from the detail page is a `str` but the model expects `List[str]`, so those jobs are dropped.
- Pagination, salary extraction, and posted-date extraction are not implemented.
