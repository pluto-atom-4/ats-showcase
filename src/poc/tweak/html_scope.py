"""HTML scoping via CSS selector for description fragments (Issue #363).

Extracts a description fragment from HTML using a CSS selector,
enabling batch_processor to scope input to specific job description elements.

No external dependencies beyond BeautifulSoup4, which is already required.
"""

from typing import NamedTuple, Optional

from bs4 import BeautifulSoup


class ScopeResult(NamedTuple):
    """Result of scoping HTML to a CSS selector.

    Attributes:
        fragment: The first matched element's inner HTML (decoded contents),
                  or None if selector matched zero elements or fragment is empty.
        match_count: Total number of elements matching the selector.
    """

    fragment: Optional[str]
    match_count: int


def scope_to_selector(html: str, selector: str) -> ScopeResult:
    """Extract a description fragment from HTML using a CSS selector.

    Parses HTML, searches for elements matching the CSS selector,
    and returns the inner content (decoded contents) of the first match.
    If zero matches or empty fragment, returns fragment=None.

    Args:
        html: Raw HTML string
        selector: CSS selector string (e.g., ".job-description", "article")

    Returns:
        ScopeResult with fragment (inner HTML or None) and match_count

    Raises:
        ValueError: If CSS selector is invalid (caught by BeautifulSoup.select())
    """
    if not html or not selector:
        return ScopeResult(fragment=None, match_count=0)

    try:
        soup = BeautifulSoup(html, "html.parser")
        matches = soup.select(selector)
        match_count = len(matches)

        if match_count == 0:
            return ScopeResult(fragment=None, match_count=0)

        # Get inner HTML (decoded contents) of first match
        first_match = matches[0]
        fragment = first_match.decode_contents().strip()

        # Empty fragment -> return None
        if not fragment:
            return ScopeResult(fragment=None, match_count=match_count)

        return ScopeResult(fragment=fragment, match_count=match_count)

    except Exception as e:
        # BeautifulSoup.select() raises ValueError for invalid selectors
        raise ValueError(f"Invalid CSS selector '{selector}': {e}") from e
