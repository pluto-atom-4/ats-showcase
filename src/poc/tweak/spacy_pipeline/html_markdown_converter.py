"""HTMLMarkdownConverter: Convert HTML to Markdown using MarkItDown.

Stage 2 of the HTML→Markdown pipeline. Converts raw HTML to Markdown format
with robust error handling and optional fallback modes for graceful degradation.

This module provides HTMLMarkdownConverter, the core conversion component that
uses the MarkItDown library to intelligently transform HTML to clean Markdown.
Key features:

- Robust error handling with configurable fallback modes
- Temp file management (write → convert → cleanup)
- Automatic cleanup even on exceptions (ensures no temp files left behind)
- Graceful degradation (can return original HTML on conversion failure)

Performance:
- Time: ~50ms per typical job description (5-15KB HTML)
- Dominated by MarkItDown library performance
- File I/O overhead minimized by using temp files

Fallback Modes:
- "html" (default): Return original HTML on conversion failure (graceful)
- "raise": Raise exception on conversion failure (fail-fast for debugging)

Example:
    >>> from src.poc.tweak.spacy_pipeline import HTMLMarkdownConverter
    >>>
    >>> # Standard usage (graceful degradation)
    >>> converter = HTMLMarkdownConverter()
    >>> html = "<div><p>Hello <strong>World</strong></p></div>"
    >>> markdown = converter.process(html)
    >>> print(markdown)
    # Output: "Hello **World**\\n"
    >>>
    >>> # Fail-fast mode for debugging
    >>> converter_strict = HTMLMarkdownConverter(fallback_mode="raise")
    >>> try:
    ...     markdown = converter_strict.process(invalid_html)
    ... except Exception as e:
    ...     print(f"Conversion failed: {e}")
"""

import logging
import os
import tempfile
from typing import Literal

from bs4 import BeautifulSoup
from markitdown import MarkItDown

from .base import PipelineComponent

logger = logging.getLogger(__name__)


class HTMLMarkdownConverter(PipelineComponent):
    """Convert HTML to Markdown using MarkItDown with robust error handling.

    Stage 2 of the HTML→Markdown pipeline. Transforms HTML (from HTMLPreprocessor)
    into clean, readable Markdown suitable for further processing or display.

    Key Responsibilities:
    1. Convert HTML to Markdown via MarkItDown library
       - Intelligent HTML structure interpretation
       - Preserves formatting (bold, italics, links, lists, etc.)
       - Handles tables, code blocks, images

    2. Manage temporary files robustly
       - Write HTML to temp file (MarkItDown requires file input)
       - Convert via MarkItDown
       - Always clean up temp file (even on exception)
       - No temp file leaks, even if conversion fails

    3. Handle MarkItDown exceptions gracefully
       - Catch conversion errors
       - Support configurable fallback modes
       - Log warnings for debugging

    4. Support fallback modes for error recovery
       - "html" (default): Return original HTML if conversion fails
         → Graceful degradation, pipeline continues
       - "raise": Raise exception if conversion fails
         → Fail-fast for debugging, catch in calling code

    Performance:
    - Time: ~50ms per typical job description (dominated by MarkItDown)
    - Memory: Minimal (temp file is OS-managed)
    - I/O: One temp file write/read, automatic cleanup

    Fallback Modes Detail:

    Mode "html" (default, recommended for production):
        - If conversion fails, return original HTML
        - Pipeline continues without breaking
        - Allows processing to complete even if some docs fail
        - Original HTML can be converted later or manually reviewed
        - Example:
            >>> converter = HTMLMarkdownConverter(fallback_mode="html")
            >>> result = converter.process(malformed_html)
            >>> # If conversion fails, result will be malformed_html (unchanged)

    Mode "raise" (recommended for debugging):
        - If conversion fails, raise exception
        - Calling code must handle the exception
        - Allows debugging/fixing converter issues
        - Example:
            >>> converter = HTMLMarkdownConverter(fallback_mode="raise")
            >>> try:
            ...     result = converter.process(malformed_html)
            ... except Exception as e:
            ...     print(f"Conversion failed: {e}")
            ...     # Debug and fix the HTML

    Error Handling Workflow:
    1. Pre-process HTML with BeautifulSoup (normalize structure)
    2. Write to temp file
    3. Convert via MarkItDown
    4. Clean up temp file (in finally block, always executes)
    5. Return markdown or apply fallback mode

    Example Usage - Direct Instantiation:
        >>> from src.poc.tweak.spacy_pipeline import HTMLMarkdownConverter
        >>>
        >>> # Graceful degradation (default)
        >>> converter = HTMLMarkdownConverter()
        >>> html = "<div><p>Hello <strong>World</strong></p></div>"
        >>> markdown = converter.process(html)
        >>> print(markdown)
        # Output: "Hello **World**\\n"
        >>>
        >>> # Fail-fast mode
        >>> converter_strict = HTMLMarkdownConverter(fallback_mode="raise")
        >>> try:
        ...     markdown = converter_strict.process(html)
        ... except Exception as e:
        ...     print(f"Error: {e}")

    Example Usage - With Full Pipeline:
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
        >>> html = "<div><p>Hello\\xa0World</p></div>"
        >>> stage1 = preprocessor.process(html)  # Clean HTML
        >>> stage2 = converter.process(stage1)   # HTML → Markdown
        >>> stage3 = polisher.process(stage2)    # Format Markdown
        >>> print(stage3)

    Example Usage - With spaCy Factory:
        >>> import spacy
        >>> from src.poc.tweak.spacy_pipeline import registry
        >>>
        >>> nlp = spacy.load("en_core_web_md")
        >>> converter = nlp.create_pipe("html_markdown_converter")
        >>> markdown = converter.process(html)

    Notes:
    - This is Stage 2 of the 3-stage pipeline (after HTMLPreprocessor)
    - Output is intended for MarkdownPolisher (Stage 3)
    - MarkItDown library required (see requirements.txt)
    - Robust temp file cleanup prevents disk space issues
    - Suitable for production: graceful error handling, no data loss

    Dependencies:
    - MarkItDown: Library for HTML-to-Markdown conversion
    - BeautifulSoup: HTML parsing/normalization
    - tempfile: Standard library for temp file management
    """

    def __init__(self, fallback_mode: Literal["html", "raise"] = "html") -> None:
        """Initialize HTMLMarkdownConverter.

        Args:
            fallback_mode: Behavior on conversion failure:
                - "html" (default): Return original HTML on failure
                  → Graceful degradation, pipeline continues
                - "raise": Raise exception on failure
                  → Fail-fast for debugging, caller handles error

        Raises:
            ValueError: If fallback_mode is not "html" or "raise"

        Example:
            >>> # Default (graceful degradation)
            >>> converter = HTMLMarkdownConverter()
            >>>
            >>> # Fail-fast for debugging
            >>> converter = HTMLMarkdownConverter(fallback_mode="raise")
            >>>
            >>> # Invalid fallback_mode
            >>> converter = HTMLMarkdownConverter(fallback_mode="invalid")
            # Raises: ValueError: fallback_mode must be 'html' or 'raise', got invalid
        """
        if fallback_mode not in ("html", "raise"):
            raise ValueError(f"fallback_mode must be 'html' or 'raise', got {fallback_mode}")
        self.fallback_mode = fallback_mode
        self.md_converter = MarkItDown()

    def process(self, html_text: str) -> str:
        """Convert HTML to Markdown with robust error handling.

        Main processing method. Converts HTML to Markdown via MarkItDown with
        graceful error handling and guaranteed temp file cleanup.

        Workflow:
        1. Pre-process HTML via BeautifulSoup (normalize structure)
        2. Write to temporary file (MarkItDown requires file input)
        3. Convert via MarkItDown library
        4. Clean up temporary file (always, even on exception)
        5. Return markdown or fallback to original HTML

        Args:
            html_text: Raw HTML string (typically from HTMLPreprocessor).
                      Can be malformed HTML or empty string.

        Returns:
            Markdown string on success. On failure:
            - If fallback_mode="html": Returns original HTML_text
            - If fallback_mode="raise": Raises exception

        Raises:
            Exception: Only if fallback_mode="raise" and conversion fails.
                Otherwise, exceptions are caught and handled gracefully.

        Side Effects:
            - Creates temporary file during conversion
            - Temp file is always deleted (even on exception)
            - Logs warnings on conversion failure

        Examples:
            >>> from src.poc.tweak.spacy_pipeline import HTMLMarkdownConverter
            >>>
            >>> # Standard usage (fallback to HTML on error)
            >>> converter = HTMLMarkdownConverter()
            >>>
            >>> # Simple HTML
            >>> html1 = "<p>Hello</p>"
            >>> md1 = converter.process(html1)
            >>> assert "Hello" in md1
            >>>
            >>> # Complex HTML with formatting
            >>> html2 = "<div><p>Hello <strong>World</strong></p></div>"
            >>> md2 = converter.process(html2)
            >>> assert "**World**" in md2
            >>>
            >>> # Empty input
            >>> html3 = ""
            >>> md3 = converter.process(html3)
            >>> assert md3 == ""
            >>>
            >>> # With lists
            >>> html4 = "<ul><li>Item 1</li><li>Item 2</li></ul>"
            >>> md4 = converter.process(html4)
            >>> assert "- Item 1" in md4 or "* Item 1" in md4
            >>>
            >>> # Fail-fast mode
            >>> converter_strict = HTMLMarkdownConverter(fallback_mode="raise")
            >>> try:
            ...     result = converter_strict.process(bad_html)
            ... except Exception as e:
            ...     print(f"Conversion error: {e}")
        """
        if not html_text:
            return html_text

        temp_path = None
        try:
            html_text = self._preprocess_html(html_text)

            temp_path = self._write_temp_file(html_text)

            markdown = self._convert_to_markdown(temp_path)

            return markdown

        except Exception as e:
            logger.warning(f"HTML to Markdown conversion failed: {e}")

            if self.fallback_mode == "raise":
                raise

            return html_text

        finally:
            if temp_path is not None:
                self._cleanup_temp_file(temp_path)

    def _preprocess_html(self, html_text: str) -> str:
        """Pre-process HTML: normalize structure and replace non-breaking spaces.

        Helper method for pre-processing before MarkItDown conversion.
        Handles exceptions gracefully: if preprocessing fails, returns original.

        Args:
            html_text: Raw HTML string

        Returns:
            Normalized HTML string, or original if preprocessing fails

        Note:
            This is separate from HTMLPreprocessor for convenience.
            If HTMLPreprocessor was already run, this is redundant but harmless.
        """
        try:
            soup = BeautifulSoup(html_text, "html.parser")

            for text_node in soup.find_all(string=True):
                text_node.replace_with(text_node.replace("\xa0", " "))

            return str(soup)
        except Exception as e:
            logger.debug(f"BeautifulSoup preprocessing failed: {e}")
            return html_text

    def _write_temp_file(self, html_text: str) -> str:
        """Write HTML to temporary file.

        Creates a temporary file in the OS temp directory and writes HTML to it.
        MarkItDown requires file input, so we must write to disk.

        Args:
            html_text: HTML string to write

        Returns:
            Path to temporary file (string)

        Raises:
            IOError: If file writing fails (disk full, permission denied, etc.)

        Note:
            Temporary file is created with suffix=".html" for clarity.
            Actual cleanup is handled in process() finally block.
        """
        tf = tempfile.NamedTemporaryFile(suffix=".html", mode="w", encoding="utf-8", delete=False)
        try:
            tf.write(html_text)
            temp_path = tf.name
        finally:
            tf.close()

        return temp_path

    def _convert_to_markdown(self, temp_path: str) -> str:
        """Convert HTML file to Markdown using MarkItDown.

        Core conversion step using MarkItDown library.

        Args:
            temp_path: Path to HTML file (created by _write_temp_file)

        Returns:
            Markdown string (result.text_content from MarkItDown)

        Raises:
            Exception: If MarkItDown conversion fails
                (caught and handled in process() method)

        Note:
            MarkItDown returns a result object with .text_content attribute.
        """
        result = self.md_converter.convert(temp_path)
        markdown: str = str(result.text_content)

        return markdown

    def _cleanup_temp_file(self, temp_path: str) -> None:
        """Clean up temporary file if it exists.

        Silently removes the temporary file. Errors during cleanup do not
        propagate (to prevent masking actual conversion errors).

        Args:
            temp_path: Path to temporary file

        Note:
            Silently ignores errors during cleanup:
            - File already deleted
            - Permission denied
            - File system errors
            These are logged at debug level but don't raise exceptions.
        """
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception as e:
            logger.debug(f"Failed to clean up temp file {temp_path}: {e}")

    @property
    def name(self) -> str:
        """Component name for logging and registration.

        Returns the component identifier used for:
        - Logging and debugging output
        - spaCy factory registration
        - Pipeline component identification

        Returns:
            Component identifier string: 'html_markdown_converter'

        Example:
            >>> converter = HTMLMarkdownConverter()
            >>> converter.name
            'html_markdown_converter'
        """
        return "html_markdown_converter"
