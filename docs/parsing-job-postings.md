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

