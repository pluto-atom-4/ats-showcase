"""HTML to Markdown conversion with clean formatting.

This module provides a legacy interface to HTML→Markdown conversion, refactored
to use modular pipeline components (HTMLPreprocessor, HTMLMarkdownConverter,
MarkdownPolisher) for maintainability and testability.

The public API remains unchanged:
- clean_and_convert(html_input: str) -> str: Convert HTML to formatted Markdown
- main(): CLI entry point (unchanged)

New Architecture (Phase 5):
- HTMLPreprocessor: Remove non-breaking spaces, normalize HTML
- HTMLMarkdownConverter: Convert HTML to Markdown via MarkItDown
- MarkdownPolisher: Apply 5 formatting rules for clean rendering

The refactored implementation chains these components together internally,
maintaining 100% backward compatibility with the original implementation.
"""

import argparse
import json
import os

from src.poc.tweak.spacy_pipeline import (
    HTMLMarkdownConverter,
    HTMLPreprocessor,
    MarkdownPolisher,
)


def clean_and_convert(html_input):
    """Convert HTML to formatted Markdown using modular pipeline components.

    Legacy interface that maintains 100% backward compatibility with the original
    implementation. Internally chains three composable pipeline components:

    1. HTMLPreprocessor: Removes non-breaking spaces, normalizes HTML
    2. HTMLMarkdownConverter: Converts HTML to Markdown via MarkItDown
    3. MarkdownPolisher: Applies 5 formatting rules for clean rendering

    The output is identical to the original implementation, but the code is now
    more modular, testable, and maintainable.

    Args:
        html_input: Raw HTML string to convert

    Returns:
        Formatted Markdown string (stripped of leading/trailing whitespace)

    Example:
        >>> html = "<div><p>Hello <strong>World</strong></p></div>"
        >>> markdown = clean_and_convert(html)
        >>> "Hello **World**" in markdown
        True
    """
    preprocessor = HTMLPreprocessor()
    converter = HTMLMarkdownConverter(fallback_mode="html")
    polisher = MarkdownPolisher()

    html_clean = preprocessor.process(html_input)

    markdown = converter.process(html_clean)

    markdown_final = polisher.process(markdown)

    return markdown_final.strip()


def main():
    parser = argparse.ArgumentParser(description="HTML to Markdown with Clean Tight-List Rendering.")
    parser.add_argument("input", help="Path to JSON file")
    parser.add_argument("-o", "--output", help="Output file path")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: {args.input} not found.")
        return

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON: {e}")
        return

    html_content = data.get("description", "")
    markdown_result = clean_and_convert(html_content)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(markdown_result)
        print(f"Success! Saved to {args.output}")
    else:
        print(markdown_result)


if __name__ == "__main__":
    main()
