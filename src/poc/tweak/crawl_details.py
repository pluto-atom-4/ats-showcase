#!/usr/bin/env python3
"""Crawler module to extract job descriptions from detail pages (Issue #309).

Reads selected.json with job listings, fetches detail pages, extracts descriptions,
handles iframe vs direct-DOM extraction, writes enriched JSON to output file.

Supports:
  - Greenhouse iframe-based job descriptions
  - Workday direct-DOM job descriptions
  - Graceful fallback to original job if extraction fails

Usage:
    python -m src.poc.tweak.crawl_details \\
        --input data/work/selected.json \\
        --output data/work/details.json \\
        --config-dir config_test \\
        --headless
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlencode, urlparse

from playwright.async_api import Browser, Page, Playwright

from src.poc.tweak.common import (
    GENERIC_FALLBACK_SELECTORS,
    close_browser,
    init_browser,
    load_all_company_configs,
    resolve_company_selectors,
    retry_goto,
    setup_logging,
)

logger = logging.getLogger(__name__)


# ============================================================================
# IFRAME EXTRACTION
# ============================================================================


async def extract_from_frame_element(
    frame: Any,
    frame_index: int,
    selector: str,
) -> str:
    """Extract content from specific element in frame using fallback chain."""
    try:
        elem = await frame.query_selector(selector)
        if not elem:
            return ""

        # Fallback chain: innerHTML → outerHTML → innerText
        content: Optional[str] = await elem.inner_html()
        if not content or len(content.strip()) < 50:
            content = await elem.evaluate("el => el.outerHTML")
        if not content or len(content.strip()) < 50:
            content = await elem.text_content()

        content_str = content.strip() if content else ""
        if content_str:
            logger.debug(f"Found selector in frame {frame_index}: {len(content_str)} chars")
            return content_str
        return ""
    except Exception as e:
        logger.debug(f"Error extracting from frame element: {e}")
        return ""


async def extract_from_frame_body(frame: Any, frame_index: int) -> str:
    """Extract content from frame body using fallback chain."""
    try:
        # Get raw HTML from frame body (preferred for preprocessing)
        # Fallback chain: innerHTML → outerHTML → innerText
        content: Optional[str] = await frame.evaluate("() => document.body.innerHTML")
        if not content or len(content.strip()) < 100:
            content = await frame.evaluate("() => document.body.outerHTML")
        if not content or len(content.strip()) < 100:
            content = await frame.evaluate("() => document.body.innerText")

        if isinstance(content, str):
            content_len = len(content.strip())
            if content_len > 100:
                logger.debug(f"Using frame {frame_index} with {content_len} chars")
                return content.strip()
        return ""
    except Exception as e:
        logger.debug(f"Error extracting from frame body: {e}")
        return ""


async def fetch_iframe_content(
    page: Page,
    inner_selector: Optional[str] = None,
) -> str:
    """
    Extract content from iframe via Playwright frame API.

    Handles Greenhouse and similar platforms using iframes for job descriptions.
    Uses fallback chain: innerHTML → outerHTML → innerText.

    Args:
        page: Playwright page object
        inner_selector: Optional CSS selector to find content within iframe

    Returns:
        Raw HTML or text content from iframe, or empty string if extraction fails
    """
    try:
        # Wait for iframe to load
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(500)

        frames = page.frames
        logger.debug(f"Found {len(frames)} frames on page")

        # Try each frame to find content
        for i, frame in enumerate(frames):
            try:
                if inner_selector:
                    result = await extract_from_frame_element(frame, i, inner_selector)
                    if result:
                        return result
                else:
                    result = await extract_from_frame_body(frame, i)
                    if result:
                        return result
            except Exception as e:
                logger.debug(f"Frame {i} error: {e}")
                continue

        logger.debug("No substantial content found in any frame")
        return ""

    except Exception as e:
        logger.debug(f"Error accessing iframe: {e}")
        return ""


# ============================================================================
# SELECTOR PRESENCE WAITING
# ============================================================================


async def selector_present(page: Page, selector: Optional[str], timeout_ms: int) -> bool:
    """
    Actively wait for a selector to attach to the page DOM.

    Waits for up to timeout_ms for the selector to be found via wait_for_selector.
    Useful for slow-loading job description pages where selector exists but content
    hasn't loaded yet.

    Args:
        page: Playwright page object
        selector: CSS selector to wait for (None returns False)
        timeout_ms: Maximum time to wait in milliseconds

    Returns:
        True if selector found within timeout, False otherwise or if selector is None
    """
    if not selector:
        logger.debug("No selector provided to selector_present()")
        return False

    try:
        await page.wait_for_selector(selector, timeout=timeout_ms)
        logger.debug(f"Selector found: {selector}")
        return True
    except Exception as e:
        logger.debug(f"Selector '{selector}' not found after {timeout_ms}ms: {e}")
        return False


# ============================================================================
# DESCRIPTION EXTRACTION
# ============================================================================


# WorkSource (Issue #765). No JSON-LD exists on WorkSource: primary source is the
# getJobDetails Apex response; fallback is the DOM at the stable job-details URL.
WORKSOURCE_COMPANY_KEY = "WorkSource"
WORKSOURCE_API_PATH = "/webruntime/api/apex/execute"
WORKSOURCE_API_METHOD = "getJobDetails"
WORKSOURCE_DETAIL_URL = "https://worksource.my.site.com/worksourcewa/job-search/job-details"

# Shell = WorkSource search-list page (rendered when the job-search URL with jobId is loaded).
# Length cannot discriminate: the shell (~15.5k text chars) is longer than a real detail page
# (~6.7k text chars). These phrases appear on the shell and on NO real detail page capture
# (verified against .playwright-mcp worksource_shell_search.json / worksource_real_detail.json).
# Two distinct hits are required so one phrase in ordinary prose is not treated as shell.
WORKSOURCE_SHELL_MARKERS = ("Refine your search", "Clear filters", "Viewing 1 - 20 of")
SHELL_MARKER_MIN_HITS = 2


def is_shell_content(html: str) -> bool:
    """
    Return True if html looks like the WorkSource search-list shell, not a job description.

    Empty or whitespace-only input counts as shell. Otherwise checks for at least
    SHELL_MARKER_MIN_HITS distinct WORKSOURCE_SHELL_MARKERS. Real detail pages carry none
    of these markers, so the check does not depend on content length.
    """
    if not html or not html.strip():
        return True
    hits = sum(1 for marker in WORKSOURCE_SHELL_MARKERS if marker in html)
    return hits >= SHELL_MARKER_MIN_HITS


def _is_get_job_details_request(response: Any) -> bool:
    """
    Predicate for page.expect_response(): POST to the Apex execute endpoint whose JSON body
    names method getJobDetails. Never matches on the `classname` query param (build hash).
    """
    request = response.request
    if WORKSOURCE_API_PATH not in response.url or request.method != "POST":
        return False
    try:
        body = json.loads(request.post_data or "")
    except (TypeError, ValueError):
        return False
    return isinstance(body, dict) and body.get("method") == WORKSOURCE_API_METHOD


async def fetch_worksource_job_via_api(
    page: Page,
    job_url: str,
    api_timeout_ms: int = 10000,
) -> Optional[Dict[str, Any]]:
    """
    Navigate to a WorkSource job URL and intercept its getJobDetails Apex response.

    Does not wait for networkidle (WorkSource is an SPA where it never settles).

    Args:
        page: Playwright page object
        job_url: WorkSource job URL (job-search URL carrying jobId)
        api_timeout_ms: Max wait for the getJobDetails response in milliseconds

    Returns:
        The response's returnValue dict, or None on timeout, non-OK status,
        JSON decode error, missing returnValue, or any other exception
    """
    try:
        async with page.expect_response(_is_get_job_details_request, timeout=api_timeout_ms) as info:
            await page.goto(job_url, wait_until="commit")
        response = await info.value
        if not response.ok:
            logger.debug(f"getJobDetails returned status {response.status} for {job_url}")
            return None
        payload = await response.json()
        return_value = payload.get("returnValue") if isinstance(payload, dict) else None
        if not isinstance(return_value, dict):
            logger.debug(f"getJobDetails response had no returnValue object for {job_url}")
            return None
        return return_value
    except Exception as e:
        logger.debug(f"getJobDetails intercept failed for {job_url}: {e}")
        return None


def _worksource_detail_url(job_url: str) -> str:
    """Build the stable job-details URL from the jobId query param of job_url."""
    job_id = parse_qs(urlparse(job_url).query).get("jobId", [""])[0]
    if not job_id:
        logger.warning(f"No jobId in WorkSource URL; using as-is: {job_url}")
        return job_url
    return f"{WORKSOURCE_DETAIL_URL}?{urlencode({'jobId': job_id})}"


async def _extract_dom_description(page: Page, selectors: Dict[str, str]) -> Optional[str]:
    """Read description from the DOM via description_selector (iframe or direct element)."""
    try:
        desc_selector = selectors.get("description_selector")
        if not desc_selector:
            logger.debug("No description selector configured")
            return None

        desc_elem = await page.query_selector(desc_selector)
        if not desc_elem:
            logger.debug("Description selector not found on page")
            return None

        # Check if element is an iframe
        try:
            tag_name = await desc_elem.evaluate("el => el.tagName.toLowerCase()")
        except Exception:
            tag_name = "unknown"

        if tag_name == "iframe":
            logger.debug("Detected iframe for job description")
            inner_selector = selectors.get("inner_description_selector")
            description = await fetch_iframe_content(page, inner_selector)
        else:
            # Regular element - extract HTML
            logger.debug(f"Detected direct DOM description (tag: {tag_name})")
            description = ""
            try:
                desc_html = await desc_elem.inner_html()
                description = desc_html.strip() if desc_html else ""
            except Exception as e:
                logger.debug(f"Error extracting inner HTML: {e}")

        return description if description else None

    except Exception as e:
        logger.debug(f"Error extracting description: {e}")
        return None


async def _extract_worksource_description(
    page: Page,
    job_url: str,
    selectors: Dict[str, str],
    timeout_ms: int,
    api_timeout_ms: int,
) -> Optional[str]:
    """API intercept first; on any failure or shell content, read the DOM at job-details?jobId=."""
    return_value = await fetch_worksource_job_via_api(page, job_url, api_timeout_ms=api_timeout_ms)
    api_description = return_value.get("jobDescription") if return_value else None
    if isinstance(api_description, str) and api_description.strip() and not is_shell_content(api_description):
        return api_description.strip()

    logger.warning(f"WorkSource API description unavailable for {job_url}; falling back to DOM")
    detail_url = _worksource_detail_url(job_url)
    try:
        await page.goto(detail_url, wait_until="domcontentloaded", timeout=timeout_ms)
    except Exception as e:
        logger.warning(f"WorkSource DOM fallback navigation failed for {detail_url}: {e}")
        return None

    if not await selector_present(page, selectors.get("description_selector"), timeout_ms):
        return None
    return await _extract_dom_description(page, selectors)


async def extract_description_from_detail_page(
    page: Page,
    job_url: str,
    selectors: Dict[str, str],
    timeout_ms: int = 30000,
    company_key: str = "",
    api_timeout_ms: int = 10000,
) -> Optional[str]:
    """
    Extract job description from detail page.

    Handles both:
    1. Iframe-based descriptions (Greenhouse)
    2. Direct-DOM descriptions (Workday, etc.)

    For company_key "WorkSource" (Issue #765), tries the getJobDetails API intercept first
    and falls back to the job-details DOM. Any description matching is_shell_content() is
    rejected for every company (returns None) so shell pages are not stored as descriptions.

    Args:
        page: Playwright page object (already navigated to job URL)
        job_url: Job URL (for logging)
        selectors: CSS selectors with description_selector, inner_description_selector
        timeout_ms: Page navigation timeout in milliseconds
        company_key: Config key of the company (source_config); "" for default behaviour
        api_timeout_ms: Max wait for the WorkSource getJobDetails response in milliseconds

    Returns:
        Extracted description HTML/text, or None if extraction failed
    """
    try:
        if company_key == WORKSOURCE_COMPANY_KEY:
            description = await _extract_worksource_description(page, job_url, selectors, timeout_ms, api_timeout_ms)
        else:
            description = await _extract_dom_description(page, selectors)

        if description and is_shell_content(description):
            logger.warning(f"Shell content detected instead of description for {job_url}; discarding")
            return None
        return description if description else None

    except Exception as e:
        logger.debug(f"Error extracting description: {e}")
        return None


# ============================================================================
# JOB DETAIL FETCHING
# ============================================================================


async def fetch_job_details(
    browser: Browser,
    job: Dict[str, Any],
    merged_config: Dict[str, Any],
    timeout_ms: int = 30000,
) -> Dict[str, Any]:
    """
    Fetch and enrich a single job with description from detail page.

    Uses adaptive retry logic with increasing timeouts (500ms → 1000ms → 2000ms)
    for slow-loading job description pages.

    Args:
        browser: Playwright browser instance
        job: Job dict from selected.json with url, company, etc.
        merged_config: Merged company configurations
        timeout_ms: Page navigation timeout in milliseconds

    Returns:
        Original job dict with description field populated (or appended original on failure)
    """
    job_copy = job.copy()
    job_url = job.get("url")
    company_name = job.get("company", "")
    job_id = job.get("id")
    job_title = job.get("title", "")
    # Config key set by crawl_list (source_config = company_key); identifies WorkSource (Issue #765)
    company_key = str(job.get("source_config") or "").strip()

    if not job_url:
        logger.warning(f"Job has no URL: {job_title}")
        return job_copy

    try:
        logger.debug(f"Fetching details for {job_title} ({company_name})")

        detail_page = await browser.new_page()
        detail_page.set_default_timeout(timeout_ms)

        # Navigate to detail page
        if not await retry_goto(
            detail_page,
            job_url,
            max_attempts=3,
            timeout_ms=timeout_ms,
            logger=logger,
        ):
            logger.warning(f"Failed to navigate to detail page: {job_url}")
            await detail_page.close()
            return job_copy

        # Adaptive retry loop for slow-loading description pages
        description: Optional[str] = None
        attempt_timeouts = [500, 1000, 2000]  # ms for attempts 1, 2, 3

        for attempt in range(1, 4):
            attempt_timeout = attempt_timeouts[attempt - 1]
            logger.info(f"Extraction attempt {attempt}/3 for {job_title}")
            start_time = time.time()

            # Resolve selectors for company
            selectors = resolve_company_selectors(company_name, merged_config)
            if not selectors:
                selectors = GENERIC_FALLBACK_SELECTORS

            # Check if description selector is present
            desc_selector = selectors.get("description_selector")
            selector_found = await selector_present(detail_page, desc_selector, attempt_timeout)

            # WorkSource: the listing page has no description node, so the selector gate would
            # skip the getJobDetails intercept entirely. Always attempt extraction for it (#765).
            if selector_found or company_key == WORKSOURCE_COMPANY_KEY:
                # Attempt extraction
                description = await extract_description_from_detail_page(
                    detail_page,
                    job_url,
                    selectors,
                    timeout_ms=timeout_ms,
                    company_key=company_key,
                )
                if description:
                    job_copy["description"] = description
                    elapsed = time.time() - start_time
                    logger.debug(
                        f"Extraction succeeded on attempt {attempt} after {elapsed:.2f}s, "
                        f"extracted {len(description)} chars"
                    )
                    break

            elapsed = time.time() - start_time
            logger.debug(
                f"Attempt {attempt} failed or no content after {elapsed:.2f}s (selector_found={selector_found})"
            )

        # If extraction failed on all attempts
        if not description:
            logger.warning(f"Failed to extract description for {job_title} after 3 attempts")
            if "description" not in job_copy or not job_copy["description"]:
                job_copy["description"] = ""

        await detail_page.close()
        return job_copy

    except Exception as e:
        logger.error(f"Error fetching details for {job_url}: {e}")
        logger.warning(
            "Cleanup notice for job id=%s title=%r company=%r url=%s: %s",
            job_id,
            job_title,
            company_name,
            job_url,
            str(e),
        )
        # Return original job unchanged on error
        return job_copy


# ============================================================================
# MAIN DETAIL FETCHING FUNCTION
# ============================================================================


async def fetch_all_job_details(
    input_file: str,
    output_file: str,
    config_dir: str = "config_test",
    headless: bool = True,
    timeout_ms: int = 30000,
    max_jobs: Optional[int] = None,
) -> int:
    """
    Fetch job details for all jobs in input file and write enriched JSON to output.

    Args:
        input_file: Path to input JSON file (selected.json)
        output_file: Path to output JSON file
        config_dir: Directory containing company config JSON files
        headless: If True, run browser in headless mode
        timeout_ms: Page navigation timeout in milliseconds
        max_jobs: Optional limit on number of jobs to process (for testing)

    Returns:
        Exit code: 0 = success, 1 = config/input error, 2 = system/browser error
    """
    logger.info("Starting job detail crawler")
    logger.info(f"Input file: {input_file}")
    logger.info(f"Output file: {output_file}")

    # Load input jobs
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            jobs = json.load(f)
        logger.info(f"Loaded {len(jobs)} jobs from {input_file}")
    except FileNotFoundError:
        logger.error(f"Input file not found: {input_file}")
        return 1
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {input_file}: {e}")
        return 1

    if not jobs:
        logger.warning("No jobs found in input file")
        return 1

    # Limit jobs for testing
    if max_jobs:
        jobs = jobs[:max_jobs]
        logger.info(f"Limited to first {max_jobs} jobs for testing")

    # Load config
    try:
        merged_config = load_all_company_configs(config_dir)
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Config loading failed: {e}")
        return 1

    # Initialize browser
    playwright: Optional[Playwright] = None
    browser: Optional[Browser] = None
    try:
        playwright, browser = await init_browser(headless=headless)
    except RuntimeError as e:
        logger.error(f"Browser initialization failed: {e}")
        return 2

    try:
        # Fetch details for each job sequentially
        enriched_jobs: List[Dict[str, Any]] = []
        for i, job in enumerate(jobs, 1):
            try:
                enriched_job = await fetch_job_details(
                    browser,
                    job,
                    merged_config,
                    timeout_ms=timeout_ms,
                )
                enriched_jobs.append(enriched_job)
                logger.info(f"Processed {i}/{len(jobs)}: {job.get('title')[:50]}...")
            except Exception as e:
                logger.error(f"Error processing job {i}: {e}")
                logger.warning(
                    "Cleanup notice for job id=%s title=%r company=%r url=%s: %s",
                    job.get("id"),
                    job.get("title"),
                    job.get("company"),
                    job.get("url"),
                    str(e),
                )
                # Append original job on error
                enriched_jobs.append(job)

        # Write output JSON
        output_path = Path(output_file)
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(enriched_jobs, f, indent=2, ensure_ascii=False)
            logger.info(f"Wrote {len(enriched_jobs)} enriched jobs to {output_path}")
        except Exception as e:
            logger.error(f"Failed to write output file {output_file}: {e}")
            return 1

        logger.info("Detail fetching completed successfully")
        return 0

    finally:
        await close_browser(playwright, browser)


# ============================================================================
# CLI ENTRY POINT
# ============================================================================


def main() -> int:
    """Parse CLI arguments and run detail crawler."""
    parser = argparse.ArgumentParser(
        description="Extract job descriptions from detail pages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch details for all jobs in selected.json
  python -m src.poc.tweak.crawl_details \\
    --input data/work/selected.json \\
    --output data/work/details.json

  # Test with first 5 jobs
  python -m src.poc.tweak.crawl_details \\
    --input data/work/selected.json \\
    --output data/work/details_test.json \\
    --max-jobs 5 \\
    --no-headless
        """,
    )

    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to input JSON file (e.g., selected.json)",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Path to output JSON file with enriched job details",
    )
    parser.add_argument(
        "--config-dir",
        type=str,
        default="config_test",
        help="Directory containing company config JSON files (default: config_test)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run browser in headless mode (default: True)",
    )
    parser.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        help="Run browser in headed mode (for debugging)",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=30000,
        help="Page navigation timeout in milliseconds (default: 30000)",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=None,
        help="Optional: limit number of jobs to process (for testing)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(__name__, level=args.log_level)

    # Run detail crawler
    try:
        exit_code = asyncio.run(
            fetch_all_job_details(
                input_file=args.input,
                output_file=args.output,
                config_dir=args.config_dir,
                headless=args.headless,
                timeout_ms=args.timeout_ms,
                max_jobs=args.max_jobs,
            )
        )
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Detail crawling interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(2)


if __name__ == "__main__":
    main()
