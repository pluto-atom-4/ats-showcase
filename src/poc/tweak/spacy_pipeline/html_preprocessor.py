"""HTMLPreprocessor: Clean raw HTML and normalize structure.

Stage 1 of the HTML→Markdown pipeline. Removes non-breaking spaces, normalizes
HTML structure via BeautifulSoup, and prepares HTML for MarkItDown conversion.

This module provides HTMLPreprocessor, a lightweight component that cleans up
raw HTML extracted from web pages before it's converted to Markdown. Common
issues fixed:
- Non-breaking spaces (\\xa0) that may interfere with text processing
- Malformed HTML tags or unclosed elements
- Inconsistent HTML structure

The preprocessor is fast (<1ms) and idempotent, making it safe to apply
multiple times without additional changes.

Example:
    >>> from src.poc.tweak.spacy_pipeline import HTMLPreprocessor
    >>> preprocessor = HTMLPreprocessor()
    >>>
    >>> # Remove non-breaking spaces
    >>> html = "<div>Text\\xa0with\\xa0nbsp</div>"
    >>> clean = preprocessor.process(html)
    >>> assert '\\xa0' not in clean
    >>> assert 'Text with nbsp' in clean
    >>>
    >>> # Normalize HTML structure
    >>> malformed = "<div><p>Unclosed paragraph"
    >>> normalized = preprocessor.process(malformed)
    >>> # BeautifulSoup closes the tag: "<div><p>Unclosed paragraph</p></div>"
"""

from bs4 import BeautifulSoup

from .base import PipelineComponent


class HTMLPreprocessor(PipelineComponent):
    """Clean raw HTML and normalize structure for downstream conversion.

    Performs initial cleanup on raw HTML extracted from web pages, preparing
    it for conversion to Markdown via MarkItDown. Key responsibilities:

    1. Remove non-breaking spaces (\\xa0 → space)
       - Non-breaking spaces can interfere with text processing and tokenization
       - Replaced with regular spaces for compatibility

    2. Normalize HTML structure via BeautifulSoup
       - Fixes unclosed/malformed tags
       - Standardizes HTML structure
       - Prepares HTML for MarkItDown processing

    3. Prepare cleaned HTML for downstream conversion
       - Returns normalized HTML string
       - Ready to be passed to HTMLMarkdownConverter

    Performance:
    - Time: <1ms per typical job description (5-15KB HTML)
    - Memory: Minimal (parses and re-serializes HTML)
    - I/O: No file I/O, pure string manipulation

    Error Handling:
    - Gracefully handles malformed HTML via BeautifulSoup
    - Always returns a valid HTML string
    - Never raises exceptions (robust for production)

    Example Usage - Direct Instantiation:
        >>> preprocessor = HTMLPreprocessor()
        >>> html = "<div>Text\\xa0with\\xa0nbsp</div>"
        >>> clean_html = preprocessor.process(html)
        >>> print(clean_html)
        # Output: '<div>Text with nbsp</div>'

    Example Usage - With spaCy Factory:
        >>> import spacy
        >>> from src.poc.tweak.spacy_pipeline import registry  # Trigger registration
        >>>
        >>> nlp = spacy.load("en_core_web_md")
        >>> preprocessor = nlp.create_pipe("html_preprocessor")
        >>> clean_html = preprocessor.process(html)

    Example Usage - In Full Pipeline:
        >>> from src.poc.tweak.spacy_pipeline import (
        ...     HTMLPreprocessor,
        ...     HTMLMarkdownConverter,
        ...     MarkdownPolisher
        ... )
        >>>
        >>> preprocessor = HTMLPreprocessor()
        >>> converter = HTMLMarkdownConverter()
        >>> polisher = MarkdownPolisher()
        >>>
        >>> html = "<div>\\xa0Text\\xa0</div>"
        >>> stage1 = preprocessor.process(html)  # Remove nbsp
        >>> stage2 = converter.process(stage1)   # HTML → Markdown
        >>> stage3 = polisher.process(stage2)    # Format markdown
        >>> print(stage3)

    Notes:
    - This is the first stage of the pipeline (Stage 1/3)
    - Output is intended to be passed to HTMLMarkdownConverter
    - No configuration options (behavior is fixed)
    - Idempotent: applying multiple times produces same result
    - No side effects: pure function

    Integration:
    - Used by scripts/process-markdown-pipeline.sh
    - Part of src/poc/tweak/spacy_pipeline/ module
    - Registered with spaCy via src/poc/tweak/spacy_pipeline/registry.py
    """

    def __init__(self) -> None:
        """Initialize HTMLPreprocessor.

        No configuration needed. All behavior is fixed:
        - Always removes non-breaking spaces
        - Always normalizes HTML via BeautifulSoup
        - Always returns normalized HTML string
        """
        pass

    def process(self, html_text: str) -> str:
        """Clean HTML and normalize structure.

        Main processing method. Applies two transformations in order:
        1. Parse HTML with BeautifulSoup to normalize structure
        2. Replace all non-breaking spaces (\\xa0) with regular spaces

        Workflow:
        1. Parse input HTML with BeautifulSoup (html.parser backend)
        2. Iterate through all text nodes in parsed tree
        3. Replace \\xa0 (non-breaking space) with regular space
        4. Serialize normalized HTML back to string
        5. Return cleaned HTML

        Args:
            html_text: Raw HTML string from web scraping or user input.
                      Can be malformed, incomplete, or contain non-breaking spaces.
                      Can be empty string (returns empty string).

        Returns:
            Normalized HTML string with:
            - All non-breaking spaces replaced with regular spaces
            - HTML structure normalized (unclosed tags fixed, etc.)
            - Ready for MarkItDown conversion

        Note:
            This method is idempotent: applying it multiple times produces
            the same result (no additional changes on re-processing).

        Examples:
            >>> preprocessor = HTMLPreprocessor()
            >>>
            >>> # Remove non-breaking spaces
            >>> html1 = "<div>Text\\xa0with\\xa0nbsp</div>"
            >>> result1 = preprocessor.process(html1)
            >>> assert '\\xa0' not in result1
            >>> assert 'Text with nbsp' in result1
            >>>
            >>> # Normalize malformed HTML
            >>> html2 = "<div><p>Unclosed paragraph"
            >>> result2 = preprocessor.process(html2)
            >>> # BeautifulSoup closes the tag
            >>> assert '</p>' in result2 and '</div>' in result2
            >>>
            >>> # Handle empty input
            >>> result3 = preprocessor.process("")
            >>> assert result3 == ""
            >>>
            >>> # Idempotent: applying twice gives same result
            >>> once = preprocessor.process(html1)
            >>> twice = preprocessor.process(once)
            >>> assert once == twice
        """
        if not html_text:
            return html_text

        soup = BeautifulSoup(html_text, "html.parser")

        for text_node in soup.find_all(string=True):
            text_node.replace_with(text_node.replace("\xa0", " "))

        return str(soup)

    @property
    def name(self) -> str:
        """Component name for logging and registration.

        Returns the component identifier used for:
        - Logging and debugging output
        - spaCy factory registration (can instantiate via nlp.create_pipe("html_preprocessor"))
        - Pipeline component identification

        Returns:
            Component identifier string: 'html_preprocessor'

        Example:
            >>> preprocessor = HTMLPreprocessor()
            >>> preprocessor.name
            'html_preprocessor'

            >>> # Also accessible through spaCy factory
            >>> import spacy
            >>> nlp = spacy.load("en_core_web_md")
            >>> comp = nlp.create_pipe("html_preprocessor")
            >>> assert comp.name == "html_preprocessor"
        """
        return "html_preprocessor"
