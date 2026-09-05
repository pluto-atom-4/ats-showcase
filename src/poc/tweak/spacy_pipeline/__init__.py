"""spaCy pipeline components for HTML→Markdown conversion and section classification.

Provides composable, chainable components for HTML processing and markdown analysis:
1. HTMLPreprocessor: Clean HTML, normalize structure, remove non-breaking spaces
2. HTMLMarkdownConverter: Convert HTML to Markdown using MarkItDown
3. MarkdownPolisher: Apply formatting rules for polished output
4. SectionClassifierComponent: Classify markdown sections into semantic types (Phase C)
5. RequirementProcessor: Extract requirements from classified sections (Issue #321)
6. SkillProcessor: Extract skills from classified sections (Issue #321)
7. TechnologyProcessor: Extract technologies from classified sections (Issue #321)

All components except SectionClassifierComponent, RequirementProcessor, SkillProcessor,
and TechnologyProcessor inherit from PipelineComponent abstract base and follow the
text-in/text-out interface. The latter four operate on spaCy Doc extensions and use the
standard spaCy pipe interface (__call__(doc) -> doc).

Components are composable and can be chained independently or via spaCy factory pattern.

Quick Start - Direct Instantiation (PipelineComponent-based):
    >>> from src.poc.tweak.spacy_pipeline import HTMLPreprocessor, HTMLMarkdownConverter, MarkdownPolisher
    >>>
    >>> preprocessor = HTMLPreprocessor()
    >>> converter = HTMLMarkdownConverter()
    >>> polisher = MarkdownPolisher()
    >>>
    >>> raw_html = "<div><p>Hello <strong>World</strong></p></div>"
    >>> markdown = polisher.process(converter.process(preprocessor.process(raw_html)))
    >>> print(markdown)
    # Output: "Hello **World**\n"

Chaining Example:
    >>> # Process through pipeline with chaining
    >>> result = (polisher(converter(preprocessor(raw_html))))

Quick Start - spaCy Factory Pattern:
    >>> import spacy
    >>> from src.poc.tweak.spacy_pipeline import registry  # Trigger factory registration
    >>>
    >>> nlp = spacy.load("en_core_web_md")
    >>>
    >>> # Create components via spaCy factory
    >>> preprocessor = nlp.create_pipe("html_preprocessor")
    >>> converter = nlp.create_pipe("html_markdown_converter")
    >>> polisher = nlp.create_pipe("markdown_polisher")
    >>> classifier = nlp.create_pipe("section_classifier")  # Phase C component
    >>> req_proc = nlp.create_pipe("requirement_processor")  # Issue #321
    >>> skill_proc = nlp.create_pipe("skill_processor")  # Issue #321
    >>> tech_proc = nlp.create_pipe("technology_processor")  # Issue #321
    >>>
    >>> # Process through full pipeline
    >>> markdown = polisher.process(converter.process(preprocessor.process(raw_html)))

Advanced - Custom Configuration:
    >>> # Use graceful error handling for converter
    >>> converter = HTMLMarkdownConverter(fallback_mode="html")
    >>>
    >>> # Use selective rules for polisher (only normalize lines + cleanup)
    >>> polisher = MarkdownPolisher(rules=['line_norm', 'cleanup'])
    >>>
    >>> markdown = polisher.process(converter.process(preprocessor.process(raw_html)))

Component Descriptions:

HTMLPreprocessor:
    Cleans raw HTML and normalizes structure for downstream conversion.
    - Removes non-breaking spaces (\\xa0 → space)
    - Normalizes HTML structure via BeautifulSoup
    - Prepares for MarkItDown conversion

    Example:
        >>> preprocessor = HTMLPreprocessor()
        >>> html = "<div>Text\\xa0with\\xa0nbsp</div>"
        >>> clean_html = preprocessor.process(html)
        >>> print(clean_html)  # Non-breaking spaces removed

HTMLMarkdownConverter:
    Converts HTML to Markdown using MarkItDown with robust error handling.
    - Converts HTML to Markdown via MarkItDown library
    - Manages temp files robustly (write → convert → cleanup)
    - Supports fallback modes: "html" (graceful) or "raise" (fail-fast)
    - Always cleans up temp files, even on exception

    Example:
        >>> converter = HTMLMarkdownConverter()
        >>> html = "<div><p>Hello <strong>World</strong></p></div>"
        >>> markdown = converter.process(html)
        >>> print(markdown)  # "Hello **World**\\n"

MarkdownPolisher:
    Applies formatting rules to Markdown for clean, consistent output.
    - Applies 5 rules in strict order:
      1. line_norm: Strip trailing/leading whitespace from each line
      2. list_tight: Remove blank lines between consecutive bullets
      3. header_format: Ensure blank lines before/after bold headers
      4. list_block: Ensure blank lines before/after list blocks
      5. cleanup: Collapse 3+ newlines to 2
    - Supports selective rule disabling
    - Pre-compiles regex patterns for performance

    Example:
        >>> polisher = MarkdownPolisher()
        >>> markdown = "Line 1  \\n\\n* Item 1\\n\\n* Item 2\\n\\n\\n"
        >>> polished = polisher.process(markdown)
        >>> print(polished)  # Formatted with proper spacing

SectionClassifierComponent (Phase C):
    Classifies markdown sections into semantic types (skills, qualifications, etc.).
    - Reads doc._.sections (populated by MarkdownSpanRuler)
    - Produces doc._.classified_sections with classification results
    - Uses SectionClassifier for keyword-based classification
    - Integrates with spaCy pipeline via factory pattern

    Example:
        >>> classifier = nlp.create_pipe("section_classifier")
        >>> doc = nlp("## Technical Skills\\nPython, Java")
        >>> doc = classifier(doc)
        >>> for section, classification in doc._.classified_sections:
        ...     print(f"{section.title}: {classification.section_type}")

RequirementProcessor (Issue #321):
    Extracts requirements from classified sections.
    - Filters to "requirements" section type only
    - Uses pattern-based detection with confidence scoring
    - Returns list: [{"text": str, "confidence": float, "source": str}, ...]

    Example:
        >>> req_proc = nlp.create_pipe("requirement_processor")
        >>> nlp.add_pipe("requirement_processor", last=True)
        >>> doc = nlp("Must have Python. Nice to have Java.")
        >>> doc._.requirements
        # [{"text": "Must have Python.", "confidence": 0.93, "source": "pattern"}]

SkillProcessor (Issue #321):
    Extracts skills from classified sections.
    - Filters to "skills" section type only
    - Uses spaCy Matcher with action verb lemmas
    - Returns list: [{"skill": str, "confidence": 1.0}, ...]

    Example:
        >>> skill_proc = nlp.create_pipe("skill_processor")
        >>> nlp.add_pipe("skill_processor", last=True)
        >>> doc = nlp("Building scalable architectures")
        >>> doc._.skills
        # [{"skill": "building scalable architectures", "confidence": 1.0}]

TechnologyProcessor (Issue #321):
    Extracts technologies from classified sections.
    - Filters to "technologies" OR "tools" section types only
    - Uses pre-registered entity_ruler for entity matching
    - Returns list: [{"tech": str, "confidence": 1.0}, ...]

    Example:
        >>> tech_proc = nlp.create_pipe("technology_processor")
        >>> nlp.add_pipe("technology_processor", last=True)
        >>> doc = nlp("Experience with Python, Docker, and AWS")
        >>> doc._.technologies
        # [{"tech": "python", "confidence": 1.0}, ...]

Usage Patterns:

1. Pipeline class (recommended for repeated use):
    >>> class HTMLToMarkdownPipeline:
    ...     def __init__(self, polisher_rules=None):
    ...         self.preprocessor = HTMLPreprocessor()
    ...         self.converter = HTMLMarkdownConverter()
    ...         self.polisher = MarkdownPolisher(rules=polisher_rules)
    ...
    ...     def process(self, html):
    ...         stage1 = self.preprocessor.process(html)
    ...         stage2 = self.converter.process(stage1)
    ...         return self.polisher.process(stage2)
    >>>
    >>> pipeline = HTMLToMarkdownPipeline()
    >>> result = pipeline.process(raw_html)

2. Functional chaining (for one-off use):
    >>> from functools import reduce
    >>> components = [HTMLPreprocessor(), HTMLMarkdownConverter(), MarkdownPolisher()]
    >>> result = reduce(lambda text, comp: comp.process(text), components, raw_html)

Performance Notes:
- HTMLPreprocessor: <1ms (string manipulation)
- HTMLMarkdownConverter: ~50ms (MarkItDown I/O)
- MarkdownPolisher: <1ms (pre-compiled regex)
- SectionClassifierComponent: <1ms per section (keyword matching)
- RequirementProcessor: <5ms per job (pattern matching)
- SkillProcessor: <10ms per job (spaCy matcher)
- TechnologyProcessor: <10ms per job (entity extraction)
- Total: ~50-100ms per document

See docs/spacy_pipeline.md for comprehensive documentation, configuration options,
troubleshooting, and advanced integration patterns.

Module Contents:
- PipelineComponent: Abstract base class for all components
- HTMLPreprocessor: Stage 1 - HTML cleanup
- HTMLMarkdownConverter: Stage 2 - HTML to Markdown conversion
- MarkdownPolisher: Stage 3 - Markdown formatting
- SectionClassifierComponent: Phase C - Section classification
- RequirementProcessor: Issue #321 - Requirement extraction
- SkillProcessor: Issue #321 - Skill extraction
- TechnologyProcessor: Issue #321 - Technology extraction
- registry: spaCy factory registrations
"""

# Import components for public API
# Import registry module to trigger @Language.factory() decorators
# This must happen on module import so factories are registered
# Set up Doc extensions for extracted data (Issue #321)
from spacy.tokens import Doc

from . import registry  # noqa: F401
from .base import PipelineComponent
from .html_markdown_converter import HTMLMarkdownConverter
from .html_preprocessor import HTMLPreprocessor
from .markdown_polisher import MarkdownPolisher
from .requirement_processor import RequirementProcessor
from .section_classifier import SectionClassifierComponent
from .skill_processor import SkillProcessor
from .technology_processor import TechnologyProcessor

if not Doc.has_extension("requirements"):
    Doc.set_extension("requirements", default=[])

if not Doc.has_extension("skills"):
    Doc.set_extension("skills", default=[])

if not Doc.has_extension("technologies"):
    Doc.set_extension("technologies", default=[])

__all__ = [
    "PipelineComponent",
    "HTMLPreprocessor",
    "HTMLMarkdownConverter",
    "MarkdownPolisher",
    "SectionClassifierComponent",
    "RequirementProcessor",
    "SkillProcessor",
    "TechnologyProcessor",
    "registry",
]
