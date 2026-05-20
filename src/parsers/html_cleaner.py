"""HTML parsing and cleaning for job postings."""

from typing import Optional
import logging

logger = logging.getLogger(__name__)


class HTMLCleaner:
    """Convert HTML to clean text for preprocessing."""
    
    def __init__(self, prefer_markitdown: bool = True):
        """
        Initialize HTML cleaner.
        
        Args:
            prefer_markitdown: Use MarkItDown (primary) or BeautifulSoup (fallback)
        """
        self.prefer_markitdown = prefer_markitdown
    
    def clean(self, html: str) -> str:
        """
        Convert HTML to clean text.
        
        Tries MarkItDown first, falls back to BeautifulSoup if unavailable.
        
        Args:
            html: Raw HTML string
        
        Returns:
            Clean text content
        """
        # TODO: Implement with MarkItDown primary, BeautifulSoup fallback
        logger.debug("Cleaning HTML content")
        return ""
    
    def extract_text(self, html: str, selector: Optional[str] = None) -> str:
        """
        Extract text from HTML, optionally using CSS selector.
        
        Args:
            html: Raw HTML string
            selector: Optional CSS selector to extract specific element
        
        Returns:
            Extracted text content
        """
        # TODO: Implement selector-based extraction
        return ""
    
    def remove_boilerplate(self, text: str) -> str:
        """
        Remove common boilerplate text (legal, EOE, etc).
        
        Args:
            text: Text to clean
        
        Returns:
            Text with boilerplate removed
        """
        # TODO: Implement boilerplate removal patterns
        return text
