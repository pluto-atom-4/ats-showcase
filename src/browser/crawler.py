"""Playwright-based web crawler for extracting job postings from company websites."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from src.models.job import JobPosting

logger = logging.getLogger(__name__)


class Crawler:
    """Multi-site job crawler using Playwright."""

    def __init__(self, headless: bool = True, timeout_ms: int = 30000):
        """
        Initialize the Crawler.

        Args:
            headless: Run browser in headless mode
            timeout_ms: Navigation timeout in milliseconds
        """
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

    async def initialize(self) -> None:
        """Initialize Playwright browser and context."""
        logger.info("Initializing Playwright browser")
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context()

    async def close(self) -> None:
        """Close browser and context."""
        logger.info("Closing Playwright browser")
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()

    async def crawl_company(
        self,
        company_name: str,
        url: str,
        selectors: Dict[str, str],
        crawler_config: Optional[Dict[str, Any]] = None,
    ) -> List[JobPosting]:
        """
        Crawl a company's career page and extract job postings.

        Args:
            company_name: Name of company
            url: Career page URL
            selectors: CSS selectors for job elements {job_container, title, location, link}
            crawler_config: Optional config with wait_for_selector, delay_ms, etc.

        Returns:
            List of extracted JobPosting objects
        """
        if not self.browser or not self.context:
            await self.initialize()

        crawler_config = crawler_config or {}
        wait_selector = crawler_config.get("wait_for_selector", selectors.get("job_container"))
        delay_ms = crawler_config.get("delay_ms", 2000)

        try:
            logger.info(f"Crawling {company_name} at {url}")
            page = await self.context.new_page()
            page.set_default_timeout(self.timeout_ms)

            await page.goto(url, wait_until="networkidle")
            logger.debug(f"Page loaded for {company_name}")

            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=10000)
                    logger.debug(f"Found selector: {wait_selector}")
                except Exception as e:
                    logger.warning(f"Selector {wait_selector} not found: {e}")

            await page.wait_for_timeout(delay_ms)

            job_containers = await page.query_selector_all(selectors["job_container"])
            logger.info(f"Found {len(job_containers)} job containers")

            jobs: List[JobPosting] = []
            for i, container in enumerate(job_containers, 1):
                try:
                    job = await self._extract_job_from_container(
                        page, container, company_name, selectors
                    )
                    if job:
                        jobs.append(job)
                        logger.debug(f"Extracted job {i}/{len(job_containers)}: {job.title}")
                except Exception as e:
                    logger.warning(f"Failed to extract job {i}: {e}")

            await page.close()
            logger.info(f"Successfully crawled {len(jobs)} jobs from {company_name}")
            return jobs

        except Exception as e:
            logger.error(f"Error crawling {company_name}: {e}")
            return []

    async def _extract_job_from_container(
        self, page: Page, container, company_name: str, selectors: Dict[str, str]
    ) -> Optional[JobPosting]:
        """Extract job details from a single job container element."""
        try:
            title = await self._extract_text(container, selectors.get("title"))
            location = await self._extract_text(container, selectors.get("location"))
            link = await self._extract_link(container, selectors.get("link"))

            if not title:
                logger.warning("No title found in container")
                return None

            return JobPosting(
                title=title,
                company=company_name,
                location=location or "Not specified",
                url=link,
                description="",
                status="pending_review",
                crawled_date=datetime.utcnow(),
            )
        except Exception as e:
            logger.warning(f"Error extracting job from container: {e}")
            return None

    async def _extract_text(self, element, selector: Optional[str]) -> Optional[str]:
        """Extract text from element using selector."""
        if not selector:
            return None
        try:
            sub_element = await element.query_selector(selector)
            if sub_element:
                text = await sub_element.text_content()
                return text.strip() if text else None
        except Exception as e:
            logger.debug(f"Error extracting text with selector {selector}: {e}")
        return None

    async def _extract_link(self, element, selector: Optional[str]) -> Optional[str]:
        """Extract href from element using selector."""
        if not selector:
            return None
        try:
            sub_element = await element.query_selector(selector)
            if sub_element:
                href = await sub_element.get_attribute("href")
                return href
        except Exception as e:
            logger.debug(f"Error extracting link with selector {selector}: {e}")
        return None

    async def crawl_multiple(
        self, companies: Dict[str, Dict[str, Any]]
    ) -> Dict[str, List[JobPosting]]:
        """
        Crawl multiple companies concurrently.

        Args:
            companies: Dict of company_name -> {url, selectors, crawler}

        Returns:
            Dict of company_name -> list of JobPosting objects
        """
        logger.info(f"Crawling {len(companies)} companies")
        await self.initialize()

        results: Dict[str, List[JobPosting]] = {}
        tasks = []

        for company_name, company_config in companies.items():
            task = self.crawl_company(
                company_name=company_name,
                url=company_config["url"],
                selectors=company_config.get("selectors", {}),
                crawler_config=company_config.get("crawler", {}),
            )
            tasks.append((company_name, task))

        for company_name, task in tasks:
            try:
                results[company_name] = await task
            except Exception as e:
                logger.error(f"Error crawling {company_name}: {e}")
                results[company_name] = []

        await self.close()
        return results
