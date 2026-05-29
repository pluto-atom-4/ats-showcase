"""HTML parsing and cleaning for job postings."""

import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class HTMLCleaner:
    """Convert HTML to clean text for preprocessing."""

    # Common boilerplate patterns in job postings
    BOILERPLATE_PATTERNS = [
        r"equal\s+opportunity\s+employer",
        r"EEO\s*statement",
        r"equal\s+employment\s+opportunity",
        r"we\s+are\s+an\s+equal\s+opportunity",
        r"apply\s+now",
        r"job\s+id\s*[:=]",
        r"posted\s+on\s*:",
        r"job\s+posted",
        r"share\s+this\s+job",
        r"job\s+details",
    ]

    def __init__(self, prefer_markitdown: bool = True):
        """
        Initialize HTML cleaner.

        Args:
            prefer_markitdown: Use MarkItDown (primary) or BeautifulSoup (fallback)
        """
        self.prefer_markitdown = prefer_markitdown
        self.markitdown_available = self._check_markitdown()

    def _check_markitdown(self) -> bool:
        """Check if MarkItDown is available."""
        try:
            import markitdown  # noqa: F401

            logger.debug("MarkItDown available")
            return True
        except ImportError:
            logger.debug("MarkItDown not available, will use BeautifulSoup")
            return False

    def clean(self, html: str) -> str:
        """
        Convert HTML to clean text.

        Tries MarkItDown first, falls back to BeautifulSoup if unavailable.

        Args:
            html: Raw HTML string

        Returns:
            Clean text content
        """
        if not html or not isinstance(html, str):
            return ""

        if self.prefer_markitdown and self.markitdown_available:
            return self._clean_with_markitdown(html)
        else:
            return self._clean_with_beautifulsoup(html)

    def _clean_with_markitdown(self, html: str) -> str:
        """Clean HTML using MarkItDown."""
        try:
            import markitdown

            logger.debug("Cleaning with MarkItDown")
            md = markitdown.MarkItDown()
            result = md.convert(html)
            clean_text = result.text_content
            return self._postprocess_text(clean_text)
        except Exception as e:
            logger.warning(f"MarkItDown failed: {e}, falling back to BeautifulSoup")
            return self._clean_with_beautifulsoup(html)

    def _clean_with_beautifulsoup(self, html: str) -> str:
        """Clean HTML using BeautifulSoup and lxml."""
        try:
            logger.debug("Cleaning with BeautifulSoup")
            soup = BeautifulSoup(html, "lxml")

            for script in soup(["script", "style"]):
                script.decompose()

            text = soup.get_text()
            return self._postprocess_text(text)
        except Exception as e:
            logger.error(f"BeautifulSoup failed: {e}")
            return ""

    def _postprocess_text(self, text: str) -> str:
        """Clean up text after HTML removal."""
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(chunk for chunk in chunks if chunk)

        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)

        for pattern in self.BOILERPLATE_PATTERNS:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        text = text.strip()
        return text

    def extract_text(self, html: str, selector: Optional[str] = None) -> str:
        """
        Extract text from HTML, optionally using CSS selector.

        Args:
            html: Raw HTML string
            selector: Optional CSS selector to extract specific element

        Returns:
            Extracted text content
        """
        if not html:
            return ""

        try:
            soup = BeautifulSoup(html, "lxml")

            if selector:
                elements = soup.select(selector)
                if elements:
                    text = " ".join(el.get_text() for el in elements)
                    return self._postprocess_text(text)

            return self.clean(html)
        except Exception as e:
            logger.warning(f"Selector extraction failed: {e}")
            return self.clean(html)

    def remove_boilerplate(self, text: str) -> str:
        """
        Remove common boilerplate text (legal, EOE, etc).

        Args:
            text: Text to clean

        Returns:
            Text with boilerplate removed
        """
        for pattern in self.BOILERPLATE_PATTERNS:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
