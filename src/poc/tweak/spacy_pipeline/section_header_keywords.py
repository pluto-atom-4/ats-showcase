"""POC-side copy of the section-header phrases found only in production.

Copied by hand from ``_SECTION_HEADER_KEYWORDS`` in ``src/parsers/html_to_markdown.py``.
Holds only the phrases that appear there and in neither ``heading_promoter`` nor
``heading_text``. This is a one-time, one-directional copy: no production module
imports this one, and this module imports no production module. Drift from the
production list is accepted.

Issue #733: copied section-header keyword vocabulary.
"""

from typing import FrozenSet

# Phrases present in production _SECTION_HEADER_KEYWORDS but absent from the POC
# promoter union (KNOWN_PLAIN_HEADINGS). All entries are lowercase.
SECTION_HEADER_KEYWORDS_ONLY: FrozenSet[str] = frozenset(
    [
        "accountabilities",
        "background",
        "competencies",
        "duties",
        "education",
        "must haves",
        "must-have",
        "must-haves",
        "needed",
        "nice to have",
        "nice to haves",
        "nice-to-have",
        "nice-to-haves",
        "understanding",
        "what we're looking for",
        "what you'll do",
    ]
)
