# #736 SPA-shell capture findings

Status: investigation record. No code change. Part of #736, tracked in #764.

## Scope

Static code read only. No live crawl and no network fetch of WorkSource were performed to produce this record. Line numbers were checked against `origin/main` at `6a5e6cd`.

## Findings (verified by code read)

1. `src/browser/crawler.py:86-91`: `page.wait_for_selector(wait_selector, timeout=10000)` is wrapped in `try/except`. On timeout it only calls `logger.warning("Selector ... not found")`. Extraction then continues with `page.query_selector_all(...)`. A missing selector does not abort the crawl or mark the page as failed.

2. `src/browser/crawler.py:228-281`: `_fetch_job_detail` returns `("", None)` on failure. The early return at 230-232 (no context) logs at debug. The `except` at 277-281 logs the error at debug, logs a full traceback at INFO level (`"DEBUG: Traceback: ..."`), then returns `("", None)`. The failure is logged, but the caller receives an empty description with no error signal. Downstream code cannot distinguish "page had no description" from "page was a shell or failed to load".

3. `src/poc/tweak/crawl_details.py:186`: `extract_description_from_detail_page(page, job_url, selectors, timeout_ms)` takes the first `description_selector` match and returns its content. A grep for `shell|loading|skeleton|spinner` in this file found no shell or loading-state check. The only related logic is the adaptive retry loop for "slow-loading description pages" (comments at lines 263 and 302). That loop retries on timing, not on shell detection.

4. WorkSource special-casing is code-only:
   - `src/poc/tweak/crawl_list.py:441`: `if link and company_key == "WorkSource":` triggers click, navigate, extract `jobId` from the detail URL, and navigate back.
   - `src/poc/tweak/crawl_list.py:617`: `if company_key == "WorkSource":` selects the `job_card` selector instead of `job_container`.
   - `config/companies.json` contains no `WorkSource` entry (grep returned no match). The key is supplied by config at runtime, and no matching entry is present in the repo.
   - Other `WorkSource` strings in `src/` are comments, docstrings, or log text at `crawl_list.py:356, 363, 366, 438-439, 444, 500, 615`.

## Unverified

- Whether the captured descriptions (reported lengths 16861 and 31591 characters in the originating investigation, #736) are real job content or SPA shell boilerplate. This record did not inspect those captures and did not fetch the pages, so it makes no claim either way.
- The `crawl_list.py` WorkSource paths were read but not executed.

## Recommendation

A human runs one live crawl of WorkSource with verbose logging enabled, then compares the captured description text against the real job page. Tracking: #761 (human-held live check of WorkSource detail pages, including `application/ld+json` `JobPosting` presence and URL stability). Note: #761's body describes a manual page inspection rather than a verbose crawl run. If a verbose-log run is wanted, it should be added to #761's steps.

Until that result is in, treat any WorkSource description length as unvalidated. Fixing the silent empty-string return at `crawler.py:277-281` or adding a shell guard is out of scope for this record and belongs to follow-up #736 work.
