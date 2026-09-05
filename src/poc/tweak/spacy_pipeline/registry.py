"""spaCy component factory registration for HTML→Markdown pipeline.

Registers HTMLPreprocessor, HTMLMarkdownConverter, MarkdownPolisher, and
SectionClassifierComponent as spaCy components using the @Language.factory()
decorator. This allows components to be instantiated via nlp.create_pipe()
or added to a pipeline.

The registrations are automatically triggered on module import via the
__init__.py import statement:
    >>> from . import registry  # noqa: F401

This approach ensures factories are registered before any code tries to use
them with nlp.create_pipe().

Usage:
    >>> import spacy
    >>> from src.poc.tweak.spacy_pipeline import registry  # Trigger registration
    >>>
    >>> nlp = spacy.load("en_core_web_md")
    >>> preprocessor = nlp.create_pipe("html_preprocessor")
    >>> converter = nlp.create_pipe("html_markdown_converter")
    >>> polisher = nlp.create_pipe("markdown_polisher")
    >>> classifier = nlp.create_pipe("section_classifier")
    >>>
    >>> # Process through pipeline
    >>> result = polisher.process(converter.process(preprocessor.process(html)))

Factory Pattern Benefits:
- Decouples component creation from implementation details
- Enables configuration via spaCy config files
- Allows components to be added to spaCy pipelines
- Supports lazy loading and registration

Integration Notes:
- Each factory creates a new instance (no singleton pattern)
- Factories ignore nlp and name parameters (required by spaCy API)
- All components use default configurations
- Custom configurations can be created directly (not via factory)

Example - Using Components with spaCy:
    >>> import spacy
    >>> nlp = spacy.load("en_core_web_md")
    >>>
    >>> # Create components via factory
    >>> preprocessor = nlp.create_pipe("html_preprocessor")
    >>> converter = nlp.create_pipe("html_markdown_converter")
    >>> polisher = nlp.create_pipe("markdown_polisher")
    >>> classifier = nlp.create_pipe("section_classifier")
    >>>
    >>> # Process text
    >>> html = "<div><p>Hello</p></div>"
    >>> markdown = polisher.process(converter.process(preprocessor.process(html)))

Example - Custom Configuration (direct instantiation):
    >>> from src.poc.tweak.spacy_pipeline import (
    ...     HTMLPreprocessor,
    ...     HTMLMarkdownConverter,
    ...     MarkdownPolisher,
    ...     SectionClassifierComponent
    ... )
    >>>
    >>> # Use custom fallback mode for converter
    >>> converter = HTMLMarkdownConverter(fallback_mode="raise")
    >>>
    >>> # Use selective rules for polisher
    >>> polisher = MarkdownPolisher(rules=['line_norm', 'cleanup'])
    >>>
    >>> result = polisher.process(converter.process(preprocessor.process(html)))
"""

from spacy.language import Language

# Import section_classifier to trigger @Language.factory() decorator registration
# (the factory is defined in section_classifier.py)
from . import section_classifier  # noqa: F401
from .html_markdown_converter import HTMLMarkdownConverter
from .html_preprocessor import HTMLPreprocessor
from .markdown_polisher import MarkdownPolisher


@Language.factory("html_preprocessor")
def create_html_preprocessor(nlp: Language, name: str) -> HTMLPreprocessor:
    """Factory function to create HTMLPreprocessor component.

    Registered with spaCy using @Language.factory() decorator. Allows
    instantiation via nlp.create_pipe("html_preprocessor").

    This factory creates HTMLPreprocessor instances with default configuration:
    - No special configuration (all behavior is fixed)
    - Removes non-breaking spaces
    - Normalizes HTML structure via BeautifulSoup

    Args:
        nlp: spaCy Language object (unused, required by factory pattern)
        name: Component name (unused, required by factory pattern)

    Returns:
        HTMLPreprocessor instance with default configuration

    Usage:
        >>> import spacy
        >>> nlp = spacy.load("en_core_web_md")
        >>> preprocessor = nlp.create_pipe("html_preprocessor")
        >>> html = "<div>Text</div>"
        >>> result = preprocessor.process(html)

    Note:
        The nlp and name parameters are required by the spaCy factory pattern
        but are not used by HTMLPreprocessor (it has no configuration).
    """
    return HTMLPreprocessor()


@Language.factory("html_markdown_converter")
def create_html_markdown_converter(nlp: Language, name: str) -> HTMLMarkdownConverter:
    """Factory function to create HTMLMarkdownConverter component.

    Registered with spaCy using @Language.factory() decorator. Allows
    instantiation via nlp.create_pipe("html_markdown_converter").

    This factory creates HTMLMarkdownConverter instances with default configuration:
    - fallback_mode="html" (graceful degradation on errors)
    - Returns original HTML if conversion fails (no exceptions)

    Args:
        nlp: spaCy Language object (unused, required by factory pattern)
        name: Component name (unused, required by factory pattern)

    Returns:
        HTMLMarkdownConverter instance with fallback_mode="html"

    Usage:
        >>> import spacy
        >>> nlp = spacy.load("en_core_web_md")
        >>> converter = nlp.create_pipe("html_markdown_converter")
        >>> html = "<div><p>Hello</p></div>"
        >>> markdown = converter.process(html)

    Custom Configuration:
        For custom fallback modes, create directly:
        >>> from src.poc.tweak.spacy_pipeline import HTMLMarkdownConverter
        >>> converter = HTMLMarkdownConverter(fallback_mode="raise")

    Note:
        The nlp and name parameters are required by the spaCy factory pattern
        but are not used to configure the converter.
    """
    return HTMLMarkdownConverter(fallback_mode="html")


@Language.factory("markdown_polisher")
def create_markdown_polisher(nlp: Language, name: str) -> MarkdownPolisher:
    """Factory function to create MarkdownPolisher component.

    Registered with spaCy using @Language.factory() decorator. Allows
    instantiation via nlp.create_pipe("markdown_polisher").

    This factory creates MarkdownPolisher instances with default configuration:
    - All 5 formatting rules enabled
    - Rules applied in standard order:
      1. line_norm - Strip trailing/leading whitespace
      2. list_tight - Remove blank lines between bullets
      3. header_format - Ensure blank lines around bold headers
      4. list_block - Ensure blank lines before/after lists
      5. cleanup - Collapse 3+ newlines to 2

    Args:
        nlp: spaCy Language object (unused, required by factory pattern)
        name: Component name (unused, required by factory pattern)

    Returns:
        MarkdownPolisher instance with all rules enabled

    Usage:
        >>> import spacy
        >>> nlp = spacy.load("en_core_web_md")
        >>> polisher = nlp.create_pipe("markdown_polisher")
        >>> markdown = "* Item 1\\n\\n* Item 2\\n\\n\\n"
        >>> polished = polisher.process(markdown)

    Custom Configuration:
        For selective rules, create directly:
        >>> from src.poc.tweak.spacy_pipeline import MarkdownPolisher
        >>> # Only line norm and cleanup
        >>> polisher = MarkdownPolisher(rules=['line_norm', 'cleanup'])

    Note:
        The nlp and name parameters are required by the spaCy factory pattern
        but are not used to configure the polisher.
    """
    return MarkdownPolisher()


@Language.factory("requirement_processor")
def create_requirement_processor(nlp: Language, name: str):
    """Factory function to create RequirementProcessor component.

    Registered with spaCy using @Language.factory() decorator. Allows
    instantiation via nlp.create_pipe("requirement_processor").

    This factory creates RequirementProcessor instances with default configuration:
    - Filters to "requirements" section type only (B2 decision)
    - Returns requirements list: [{"text": str, "confidence": float, "source": str}, ...]

    Args:
        nlp: spaCy Language object (required by factory pattern)
        name: Component name (required by factory pattern)

    Returns:
        RequirementProcessor instance with default configuration

    Usage:
        >>> import spacy
        >>> from src.poc.tweak.spacy_pipeline import registry  # noqa: F401
        >>>
        >>> nlp = spacy.load("en_core_web_md")
        >>> processor = nlp.create_pipe("requirement_processor")
        >>> nlp.add_pipe("requirement_processor", last=True)

    Note:
        The nlp and name parameters are required by the spaCy factory pattern.
        For custom configurations, create directly:
        >>> from src.poc.tweak.spacy_pipeline import RequirementProcessor
        >>> processor = RequirementProcessor(nlp, "requirement_processor")
    """
    from .requirement_processor import RequirementProcessor

    return RequirementProcessor(nlp, name)


@Language.factory("skill_processor")
def create_skill_processor(nlp: Language, name: str):
    """Factory function to create SkillProcessor component.

    Registered with spaCy using @Language.factory() decorator. Allows
    instantiation via nlp.create_pipe("skill_processor").

    This factory creates SkillProcessor instances with default configuration:
    - Filters to "skills" section type only (B2 decision)
    - Uses spaCy Matcher with action verb lemmas (SKILL_VERBS from patterns)
    - Returns skills list: [{"skill": str, "confidence": 1.0}, ...]

    Args:
        nlp: spaCy Language object (required by factory pattern)
        name: Component name (required by factory pattern)

    Returns:
        SkillProcessor instance with default configuration

    Usage:
        >>> import spacy
        >>> from src.poc.tweak.spacy_pipeline import registry  # noqa: F401
        >>>
        >>> nlp = spacy.load("en_core_web_md")
        >>> processor = nlp.create_pipe("skill_processor")
        >>> nlp.add_pipe("skill_processor", last=True)

    Note:
        The nlp and name parameters are required by the spaCy factory pattern.
        For custom configurations, create directly:
        >>> from src.poc.tweak.spacy_pipeline import SkillProcessor
        >>> processor = SkillProcessor(nlp, "skill_processor")
    """
    from .skill_processor import SkillProcessor

    return SkillProcessor(nlp, name)


@Language.factory("technology_processor")
def create_technology_processor(nlp: Language, name: str):
    """Factory function to create TechnologyProcessor component.

    Registered with spaCy using @Language.factory() decorator. Allows
    instantiation via nlp.create_pipe("technology_processor").

    This factory creates TechnologyProcessor instances with default configuration:
    - Filters to "technologies" OR "tools" section types only (B2 decision)
    - Uses pre-registered entity_ruler (D5 decision)
    - Returns technologies list: [{"tech": str, "confidence": 1.0}, ...]

    Args:
        nlp: spaCy Language object (required by factory pattern)
        name: Component name (required by factory pattern)

    Returns:
        TechnologyProcessor instance with default configuration

    Usage:
        >>> import spacy
        >>> from src.poc.tweak.spacy_pipeline import registry  # noqa: F401
        >>>
        >>> nlp = spacy.load("en_core_web_md")
        >>> # Ensure entity_ruler is pre-registered (done in batch_processor.py)
        >>> processor = nlp.create_pipe("technology_processor")
        >>> nlp.add_pipe("technology_processor", last=True)

    Note:
        The nlp and name parameters are required by the spaCy factory pattern.
        For custom configurations, create directly:
        >>> from src.poc.tweak.spacy_pipeline import TechnologyProcessor
        >>> processor = TechnologyProcessor(nlp, "technology_processor")
    """
    from .technology_processor import TechnologyProcessor

    return TechnologyProcessor(nlp, name)
