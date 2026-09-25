"""HTML scoping via CSS selector for description fragments (Issue #363, #367).

Extracts a description fragment from HTML using a CSS selector,
enabling batch_processor to scope input to specific job description elements.

Supports multiple matching strategies: first match, all matches, or longest match.

No external dependencies beyond BeautifulSoup4, which is already required.
"""

from typing import NamedTuple, Optional

from bs4 import BeautifulSoup


class ScopeResult(NamedTuple):
    """Result of scoping HTML to a CSS selector.

    Attributes:
        fragment: The matched element's inner HTML (decoded contents) based on strategy,
                  or None if selector matched zero elements or fragment is empty.
        match_count: Total number of elements matching the selector.
    """

    fragment: Optional[str]
    match_count: int


def scope_to_selector(html: str, selector: str, strategy: str = "first") -> ScopeResult:
    """Extract a description fragment from HTML using a CSS selector.

    Parses HTML, searches for elements matching the CSS selector,
    and returns the inner content (decoded contents) based on the strategy.

    Strategies:
    - "first": Return the first match's inner HTML (default, current behavior)
    - "all": Join all non-empty matches with separator "\n\n---\n\n"
    - "longest": Return the match with longest stripped inner-HTML fragment

    If zero matches or empty fragment, returns fragment=None.
    Unknown strategy is treated as "first".

    Args:
        html: Raw HTML string
        selector: CSS selector string (e.g., ".job-description", "article")
        strategy: Match selection strategy ("first", "all", or "longest").
                  Default "first". Unknown values treated as "first".

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

        # Strategy "first": return first match's fragment (even if empty -> None)
        if strategy == "first":
            first_match = matches[0]
            fragment = first_match.decode_contents().strip()
            # Empty fragment -> return None
            if not fragment:
                return ScopeResult(fragment=None, match_count=match_count)
            return ScopeResult(fragment=fragment, match_count=match_count)

        # For "all" and "longest": collect all non-empty fragments
        fragments = []
        for match in matches:
            fragment = match.decode_contents().strip()
            if fragment:
                fragments.append(fragment)

        # If no non-empty fragments found, return None
        if not fragments:
            return ScopeResult(fragment=None, match_count=match_count)

        # Strategy "all": join all non-empty fragments in document order
        if strategy == "all":
            combined = "\n\n---\n\n".join(fragments)
            return ScopeResult(fragment=combined, match_count=match_count)

        # Strategy "longest": pick the match with longest stripped inner-HTML
        if strategy == "longest":
            longest_fragment = max(fragments, key=len)
            return ScopeResult(fragment=longest_fragment, match_count=match_count)

        # Unknown strategy: treat as "first"
        first_match = matches[0]
        fragment = first_match.decode_contents().strip()
        if not fragment:
            return ScopeResult(fragment=None, match_count=match_count)
        return ScopeResult(fragment=fragment, match_count=match_count)

    except Exception as e:
        # BeautifulSoup.select() raises ValueError for invalid selectors
        raise ValueError(f"Invalid CSS selector '{selector}': {e}") from e
