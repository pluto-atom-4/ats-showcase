"""SectionClassifier pipeline component for spaCy.

Phase C of Issue #293: spaCy integration of markdown section classification.

This module provides SectionClassifierComponent, a spaCy pipeline component that
reads pre-parsed markdown sections from doc._.sections and produces classified
sections in doc._.classified_sections.

The component integrates with the spaCy pipeline using the @Language.factory()
decorator and can be added to pipelines via nlp.add_pipe("section_classifier").

Key Design Decisions:
- Does NOT inherit from PipelineComponent (incompatible Doc extension semantics)
- Implements standard spaCy pipe interface: __call__(doc: Doc) -> Doc
- Creates doc._.classified_sections extension on first use
- Handles missing/empty sections gracefully (no error on doc._.sections = None)
- Component insertion point: after markdown_polisher in pipeline
- Classification happens in-place (no side effects, idempotent)

Usage - Direct Instantiation:
    >>> from src.poc.tweak.spacy_pipeline import SectionClassifierComponent
    >>> import spacy
    >>>
    >>> nlp = spacy.load("en_core_web_md")
    >>> classifier = SectionClassifierComponent(nlp, "section_classifier")
    >>>
    >>> doc = nlp("## Technical Skills\\nPython, Java")
    >>> # Pre-populate doc._.sections (normally done by MarkdownSpanRuler)
    >>> from src.poc.tweak.multi_line_paragraph import MarkdownSection
    >>> doc._.sections = [
    ...     MarkdownSection(
    ...         title="Technical Skills",
    ...         content="Python, Java",
    ...         level=2,
    ...         start_line=0,
    ...         end_line=1,
    ...         word_count=2,
    ...         line_count=1,
    ...         has_list=False
    ...     )
    ... ]
    >>> doc = classifier(doc)
    >>> print(doc._.classified_sections)
    # [(MarkdownSection(...), SectionClassification(...))]

Usage - spaCy Factory Pattern:
    >>> import spacy
    >>> from src.poc.tweak.spacy_pipeline import registry  # noqa: F401
    >>>
    >>> nlp = spacy.load("en_core_web_md")
    >>> classifier = nlp.create_pipe("section_classifier")
    >>> nlp.add_pipe("section_classifier", last=True)
    >>>
    >>> doc = nlp("## Technical Skills\\nPython, Java")
    >>> print(doc._.classified_sections)
    # [(...classified sections...)]

Pipeline Integration:
    The component should be added after markdown_polisher in the standard pipeline:
    >>> nlp.add_pipe("html_preprocessor", last=True)
    >>> nlp.add_pipe("html_markdown_converter", last=True)
    >>> nlp.add_pipe("markdown_polisher", last=True)
    >>> nlp.add_pipe("section_classifier", last=True)  # Phase C component
    >>>
    >>> # Now the pipeline processes: raw HTML → markdown → sections → classifications

Related Modules:
    - multi_line_paragraph.py: MarkdownSpanRuler (populates doc._.sections)
    - markdown_section_classifier.py: SectionClassifier (performs classification)
    - markdown_polisher.py: Formats markdown before section extraction

See Also:
    docs/dev-note/issue-293.md: Phase C design and integration notes
    tests/poc/tweak/spacy_pipeline/test_section_classifier.py: Unit tests
"""

from typing import List, Tuple

from spacy.language import Language
from spacy.tokens import Doc

from src.poc.tweak.markdown_section_classifier import SectionClassification, SectionClassifier
from src.poc.tweak.multi_line_paragraph import MarkdownSection


class SectionClassifierComponent:
    """spaCy pipeline component for classifying markdown sections.

    Reads doc._.sections (populated by MarkdownSpanRuler or similar) and
    produces doc._.classified_sections with classification results.

    This component implements the standard spaCy pipe interface:
    - __call__(doc: Doc) -> Doc: Process a spaCy Doc
    - name property: Component identifier for logging

    Does NOT inherit from PipelineComponent because the pipe interface
    (text-in/text-out) is incompatible with Doc extension mutation semantics.

    Attributes:
        nlp: spaCy Language object (stored for potential future use)
        name: Component identifier string ('section_classifier')
        classifier: SectionClassifier instance for performing classifications

    Key Features:
        - Graceful handling of missing/empty doc._.sections (no error)
        - Automatic creation of doc._.classified_sections extension
        - Idempotent: multiple passes produce consistent results
        - No side effects beyond Doc extension mutation
        - Fast: classification is linear in number of sections

    Example:
        >>> from spacy.language import Language
        >>> import spacy
        >>> from src.poc.tweak.spacy_pipeline import registry  # noqa: F401
        >>>
        >>> nlp = spacy.load("en_core_web_md")
        >>> doc = nlp("## Technical Skills\\nPython, Java")
        >>>
        >>> # Before: doc._.sections populated by MarkdownSpanRuler
        >>> # Now: classify sections
        >>> classifier = nlp.create_pipe("section_classifier")
        >>> doc = classifier(doc)
        >>>
        >>> # After: doc._.classified_sections contains tuples
        >>> for section, classification in doc._.classified_sections:
        ...     print(f"{section.title}: {classification.section_type}")
    """

    def __init__(self, nlp: Language, name: str) -> None:
        """Initialize SectionClassifierComponent.

        Creates a SectionClassifier instance and registers the
        doc._.classified_sections extension if not already present.

        Args:
            nlp: spaCy Language object (required by factory pattern)
            name: Component name for logging (typically 'section_classifier')

        Raises:
            ValueError: If name is None or empty
        """
        if not name:
            raise ValueError("Component name cannot be None or empty")

        self.nlp = nlp
        self._name = name
        self.classifier = SectionClassifier()

        if not Doc.has_extension("classified_sections"):
            Doc.set_extension("classified_sections", default=[])

    def __call__(self, doc: Doc) -> Doc:
        """Process a spaCy Doc and classify its sections.

        Reads doc._.sections (list of MarkdownSection objects) and produces
        doc._.classified_sections (list of tuples).

        Each tuple is: (section: MarkdownSection, classification: SectionClassification)

        Handles edge cases gracefully:
        - If doc._.sections is None: treats as empty list
        - If doc._.sections is empty: doc._.classified_sections = []
        - If section.title is None: passes through to classifier (already handles)

        Args:
            doc: spaCy Doc to process

        Returns:
            Modified doc with doc._.classified_sections populated

        Raises:
            TypeError: If doc is not a spaCy Doc

        Example:
            >>> import spacy
            >>> from src.poc.tweak.multi_line_paragraph import MarkdownSection
            >>>
            >>> nlp = spacy.load("en_core_web_md")
            >>> classifier = SectionClassifierComponent(nlp, "section_classifier")
            >>>
            >>> doc = nlp("## Technical Skills\\nPython, Java")
            >>> doc._.sections = [
            ...     MarkdownSection(
            ...         title="Technical Skills",
            ...         content="Python, Java",
            ...         level=2,
            ...         start_line=0,
            ...         end_line=1,
            ...         word_count=2,
            ...         line_count=1,
            ...         has_list=False
            ...     )
            ... ]
            >>> doc = classifier(doc)
            >>> assert len(doc._.classified_sections) == 1
            >>> section, classification = doc._.classified_sections[0]
            >>> assert classification.section_type.value == "skills"
        """
        sections = doc._.sections if doc._.sections else []

        classified_sections: List[Tuple[MarkdownSection, SectionClassification]] = []

        for section in sections:
            classification = self.classifier.classify(section)
            classified_sections.append((section, classification))

        doc._.classified_sections = classified_sections

        return doc

    @property
    def name(self) -> str:
        """Component name for logging and identification.

        Returns the component's identifier used for:
        - Logging and debugging output
        - spaCy factory registration (@Language.factory("name"))
        - Pipeline component identification

        Returns:
            Component identifier string (typically 'section_classifier')

        Example:
            >>> from spacy.language import Language
            >>> import spacy
            >>>
            >>> nlp = spacy.load("en_core_web_md")
            >>> classifier = SectionClassifierComponent(nlp, "section_classifier")
            >>> classifier.name
            'section_classifier'
        """
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Allow spaCy to set component name.

        Args:
            value: New name value (set by spaCy during pipeline registration)
        """
        if not value:
            raise ValueError("Component name cannot be None or empty")
        self._name = value


@Language.factory("section_classifier")
def create_section_classifier(nlp: Language, name: str) -> SectionClassifierComponent:
    """Factory function to create SectionClassifierComponent.

    Registered with spaCy using @Language.factory() decorator. Allows
    instantiation via nlp.create_pipe("section_classifier").

    This factory creates SectionClassifierComponent instances with default
    configuration:
    - Uses default SectionClassifier (standard keyword-based matching)
    - No custom skip keywords (uses built-in SKIP_SECTIONS)

    Args:
        nlp: spaCy Language object (required by factory pattern)
        name: Component name (required by factory pattern)

    Returns:
        SectionClassifierComponent instance with default configuration

    Usage:
        >>> import spacy
        >>> from src.poc.tweak.spacy_pipeline import registry  # noqa: F401
        >>>
        >>> nlp = spacy.load("en_core_web_md")
        >>> classifier = nlp.create_pipe("section_classifier")
        >>> nlp.add_pipe("section_classifier", last=True)

    Note:
        For custom SectionClassifier configurations, create directly:
        >>> from src.poc.tweak.spacy_pipeline import SectionClassifierComponent
        >>> from src.poc.tweak.markdown_section_classifier import SectionClassifier
        >>>
        >>> custom_classifier = SectionClassifier(skip_keywords=custom_keywords)
        >>> component = SectionClassifierComponent(nlp, "section_classifier")
        >>> # Manually replace component.classifier if needed
    """
    return SectionClassifierComponent(nlp, name)
