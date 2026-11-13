"""NLP preprocessing for job postings using spaCy."""

import json
import logging
import re
from typing import Any, List, Optional, Set, Tuple, Union

import spacy
from spacy.language import Language
from spacy.tokens import Doc

from src.preprocessing.section_detector import SectionDetector
from src.preprocessing.section_extractor import SectionedResult, extract_sectioned
from src.tokenization.company_names import get_company_keywords, is_company_keyword
from src.tokenization.keywords import get_all_keywords
from src.tokenization.soft_skills import get_all_soft_skills
from src.tokenization.technical_compounds import is_technical_compound

logger = logging.getLogger(__name__)


class Preprocessor:
    """Preprocess text using spaCy for NLP tasks."""

    # Section names (or substrings) skipped by _extract_entities_by_section. Single source of truth:
    # other tooling (e.g. .claude/scripts/analyze_sections.py) should reference Preprocessor.SKIP_SECTIONS, not copy it.
    SKIP_SECTIONS: Set[str] = {
        "benefits",
        "compensation",
        "salary",
        "pay range",
        "401",
        "retirement",
        "insurance",
        "health",
        "dental",
        "vision",
        "pto",
        "vacation",
        "about",
        "company",
        "culture",
        "commitment",
        "team",
        "our",
        "equal opportunity",
        "eoe",
        "affirmative action",
        "disability",
        "background check",
        "export control",
        "security clearance",
        "visa",
        "apply",
        "posting date",
        "posted",
        "application close",
        "codevue",
        "shift",
        "location",
        "work location",
        "travel",
        "working condition",
        "fte",
        "temporary",
        "education:",
        "hiring practice",
        "bargaining",
        "conflict of interest",
        "drug free",
        "e-verify",
        "right to work",
        "safety sensitive",
        "technical assessment",
        "total rewards",
        "union",
        "contingent upon award",
    }

    def __init__(
        self,
        model: str = "en_core_web_md",
        extract_requirements: bool = True,
        preserve_requirement_spans: bool = True,
        section_engine: Optional[SectionDetector] = None,
        categorizer_strategy: str = "nlp",
        span_patterns_path: str | None = None,
        enable_poc_sentence_splitter: bool = True,
    ):
        """Initialize preprocessor with spaCy model.

        Args:
            model: spaCy model name (e.g., en_core_web_md)
            extract_requirements: Whether to extract trigger-based requirements (default: True)
            preserve_requirement_spans: Whether to respect requirement spans during chunking
            section_engine: Optional SectionDetector instance for opt-in section-aware requirement
                          extraction (default: None = legacy behavior unchanged)
            categorizer_strategy: "nlp" (POS/DEP span categorizer, default) or "custom"
                          (regex patterns from span_patterns_path, written to doc._.custom_spans)
            span_patterns_path: Path to patterns JSON; required when categorizer_strategy is "custom"
            enable_poc_sentence_splitter: Add the regex-only POC sentence splitter pipe (#638).
                          Default True adds "poc_sentence_splitter" to nlp.pipe_names. The
                          existing segment_sentences() output is unaffected.

        Raises:
            ValueError: Unknown strategy, "custom" without span_patterns_path, or invalid patterns.
            OSError: If span_patterns_path cannot be read.
        """
        if categorizer_strategy not in ("nlp", "custom"):
            raise ValueError(f"Unknown categorizer strategy: {categorizer_strategy}")
        if categorizer_strategy == "custom" and not span_patterns_path:
            raise ValueError("categorizer strategy 'custom' requires span_patterns_path")

        self.model_name = model
        self.extract_requirements = extract_requirements
        self.preserve_requirement_spans = preserve_requirement_spans
        self.section_engine = section_engine
        self.categorizer_strategy = categorizer_strategy
        self.enable_poc_sentence_splitter = enable_poc_sentence_splitter
        self.nlp: Optional[Language] = None
        self._custom_span_component: Any = None
        if categorizer_strategy == "custom":
            self._custom_span_component = self._build_custom_span_component(span_patterns_path or "")
        self._load_model()

    @staticmethod
    def _build_custom_span_component(span_patterns_path: str) -> Any:
        """Build a regex SpanCategorizerComponent from a patterns JSON file.

        Args:
            span_patterns_path: Path to patterns JSON (see load_patterns)

        Returns:
            SpanCategorizerComponent that writes doc._.custom_spans when called directly
        """
        from src.preprocessing.custom_span_categorizer import (
            CustomSpanCategorizer,
            SpanCategorizerComponent,
            load_patterns,
        )

        return SpanCategorizerComponent(CustomSpanCategorizer(load_patterns(span_patterns_path)))

    def apply_custom_spans(self, doc: Doc) -> Doc:
        """Run the custom span categorizer directly on a Doc (custom strategy only).

        Not registered as a pipeline component. No-op for the "nlp" strategy.

        Args:
            doc: spaCy Doc produced by self.nlp

        Returns:
            Same Doc, with doc._.custom_spans set when strategy is "custom"
        """
        if self._custom_span_component is None:
            return doc
        result: Doc = self._custom_span_component(doc)
        return result

    def _load_model(self) -> None:
        """Load spaCy model with error handling.

        Raises:
            OSError: If model cannot be loaded or is not installed.
        """
        try:
            logger.info(f"Loading spaCy model: {self.model_name}")
            self.nlp = spacy.load(self.model_name)
            logger.info(f"Successfully loaded spaCy model: {self.model_name}")
        except OSError as e:
            logger.error(
                f"Failed to load spaCy model '{self.model_name}': {e}. "
                "Ensure it's installed: python -m spacy download en_core_web_md"
            )
            raise

        if self.extract_requirements:
            try:
                # Importing registers the component via its decorator.
                import src.preprocessing.requirement_filter  # noqa: F401

                if "requirement_filter" not in self.nlp.pipe_names:
                    # Placed before 'ner' when present, otherwise appended.
                    anchor = "ner" if "ner" in self.nlp.pipe_names else None
                    if anchor:
                        self.nlp.add_pipe("requirement_filter", before=anchor)
                    else:
                        self.nlp.add_pipe("requirement_filter")
                    logger.info("Added requirement_filter component to pipeline")

                import src.preprocessing.span_categorizer  # noqa: F401

                if "span_categorizer" not in self.nlp.pipe_names:
                    # Must run after requirement_filter, which populates doc._.requirements.
                    self.nlp.add_pipe("span_categorizer", after="requirement_filter")
                    logger.info("Added span_categorizer component to pipeline")
            except ValueError as e:
                logger.warning(
                    f"Failed to register requirement extraction components: {e}. "
                    "Requirement extraction disabled. Processing will continue without extracted requirements."
                )
                self.extract_requirements = False

        # POC regex-only sentence splitter (Issue #638). Additive: writes only doc._.poc_sentences.
        if self.enable_poc_sentence_splitter:
            # Importing registers the factory via its decorator.
            import src.poc.sentence_splitter  # noqa: F401

            if "poc_sentence_splitter" not in self.nlp.pipe_names:
                self.nlp.add_pipe("poc_sentence_splitter")
                logger.info("Added poc_sentence_splitter component to pipeline")

    def segment_sentences(self, text: str) -> List[str]:
        """Split text into sentences using spaCy sentence segmentation.

        Handles edge cases: abbreviations (Dr., Inc.), multiple punctuation.

        Args:
            text: Input text to segment

        Returns:
            List of sentence strings
        """
        if not self.nlp:
            logger.warning("spaCy model not loaded, returning empty list")
            return []

        if not text or not text.strip():
            return []

        try:
            doc = self.nlp(text)
            sentences = [sent.text.strip() for sent in doc.sents]
            logger.debug(f"Segmented text into {len(sentences)} sentences")
            return sentences
        except Exception as e:
            logger.error(f"Error segmenting sentences: {e}")
            return []

    def segment_sentences_poc(self, doc: Doc) -> List[str]:
        """Return sentences produced by the POC regex splitter (Issue #638).

        Args:
            doc: spaCy Doc already processed by self.nlp

        Returns:
            doc._.poc_sentences, or [] if the flag is off or the component did not run.
        """
        if not self.enable_poc_sentence_splitter:
            return []
        return list(doc._.poc_sentences or [])

    def extract_entities(self, text: str) -> Tuple[List[str], List[str], List[str]]:
        """Extract named entities (skills, technologies, requirements).

        Phase 1: Smart filtering (section extraction → boilerplate removal → entity filtering)
        Uses spaCy NER for named entities and POS/DEP tagging for skills/tech.

        Args:
            text: Input text to extract entities from

        Returns:
            Tuple of (skills, technologies, requirements) as unique strings
        """
        if not self.nlp:
            logger.warning("spaCy model not loaded, returning empty lists")
            return [], [], []

        if not text or not text.strip():
            return [], [], []

        skills: set[str] = set()
        technologies: set[str] = set()
        requirements: set[str] = set()

        try:
            is_md = self._is_markdown(text)

            if is_md:
                logger.debug("Text is markdown format, using entity-aware section extraction")
                md_skills, md_technologies, md_requirements = self._extract_entities_by_section(text)
                skills.update(md_skills)
                technologies.update(md_technologies)
                requirements.update(md_requirements)

                # For markdown, drop benefits/compensation/about/culture sections from full-text extraction.
                skip_pattern_str = (
                    r"^#{1,3}\s+.*?"
                    r"(benefits|compensation|salary|pay|about|culture|company|how to apply)"
                    r".*?$.*?(?=^#{1,3}\s|\Z)"
                )
                text_to_extract = re.sub(skip_pattern_str, "", text, flags=re.MULTILINE | re.IGNORECASE | re.DOTALL)
                text_to_clean = text_to_extract if text_to_extract.strip() else text
            else:
                # Plain text: restrict to the job section, falling back to the full text when none is found.
                job_section = self._extract_job_section(text)
                text_to_clean = job_section if job_section.strip() else text

            # Remove boilerplate (salary, legal, location metadata)
            cleaned_text = self._remove_boilerplate(text_to_clean)

            # Extract entities from the cleaned text
            doc = self.nlp(cleaned_text)
            tech_keywords = self._get_tech_keywords()

            # Extract from NER (named entities) - always do this for comprehensive extraction
            self._extract_from_ner(doc, tech_keywords, technologies, requirements)

            entity_pos_tags: dict[str, str] = {}
            self._extract_from_tokens(doc, tech_keywords, skills, technologies, entity_pos_tags)

            # Markdown gets soft skills per skills section (_extract_entities_by_section); plain text uses full text.
            soft_skills_set: set[str] = set()
            if not is_md:
                self._extract_soft_skills(doc, soft_skills_set)

            # Reclassify technical compounds: move compound phrases from skills to technologies.
            skills_list = list(skills) + list(soft_skills_set)
            reclassified_skills: list[str] = []
            for skill in skills_list:
                if is_technical_compound(skill):
                    technologies.add(skill)
                else:
                    reclassified_skills.append(skill)

            # Filter noise, duplicates and short fragments; pass pre-computed POS tags to avoid a second NLP pass.
            skills = set(
                self._filter_entities(reclassified_skills, entity_type="skills", entity_pos_tags=entity_pos_tags)
            )
            technologies = set(
                self._filter_entities(list(technologies), entity_type="technologies", entity_pos_tags=entity_pos_tags)
            )
            requirements = set(
                self._filter_entities(list(requirements), entity_type="requirements", entity_pos_tags=entity_pos_tags)
            )

            logger.debug(
                f"Extracted {len(skills)} skills, "
                f"{len(technologies)} technologies, "
                f"{len(requirements)} requirements (Phase 1 filtering applied)"
            )

            return (
                sorted(skills),
                sorted(technologies),
                sorted(requirements),
            )

        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return [], [], []

    def extract_trigger_requirements(self, text: str) -> Optional[str]:
        """Extract trigger-based requirements using requirement_filter component.

        Uses spaCy pipeline with requirement_filter component for pattern-based
        requirement extraction with confidence scoring.

        Args:
            text: Input text to extract requirements from

        Returns:
            JSON string of requirements with trigger words and confidence, or None if disabled
        """
        if not self.extract_requirements or not self.nlp:
            return None

        if not text or not text.strip():
            return None

        try:
            doc = self.nlp(text)

            requirements_data = getattr(doc._, "requirements", None)

            if not requirements_data:
                return None

            return json.dumps(requirements_data, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Error extracting trigger requirements: {e}")
            return None

    def extract_sectioned_requirements(self, text: str) -> Optional[SectionedResult]:
        """Extract sectioned requirements from text using section_engine.

        Returns None when section_engine is None (legacy behavior unchanged).
        Otherwise returns SectionedResult with requirements extracted from detected sections.
        Skills/technologies still come from legacy extract_entities(); this method
        extracts only requirement-specific entities. Output is transient, not persisted.

        Args:
            text: Input text to extract from

        Returns:
            SectionedResult if section_engine is set, None otherwise
        """
        if self.section_engine is None:
            return None

        return extract_sectioned(text, detector=self.section_engine)

    @staticmethod
    def _get_tech_keywords() -> set[str]:
        """Get technology keywords from centralized keywords module.

        Returns:
            Set of 86+ technology keywords across all categories
        """
        return get_all_keywords()

    @staticmethod
    def _extract_from_ner(doc: Any, tech_keywords: Set[str], technologies: Set[str], requirements: Set[str]) -> None:
        """Extract entities from named entity recognition."""
        for ent in doc.ents:
            entity_text = ent.text.strip()
            if not entity_text or ent.label_ not in ("PRODUCT", "ORG"):
                continue

            if any(keyword in entity_text.lower() for keyword in tech_keywords):
                technologies.add(entity_text)
            else:
                requirements.add(entity_text)

    @staticmethod
    def _extract_from_tokens(
        doc: Any,
        tech_keywords: Set[str],
        skills: Set[str],
        technologies: Set[str],
        entity_pos_tags: Optional[dict[str, str]] = None,
    ) -> None:
        """Extract skills and tech from tokens (Phase 3: POS tag optimization).

        Args:
            doc: spaCy Doc object with processed tokens
            tech_keywords: Set of technology keywords to match
            skills: Set to add extracted skills to
            technologies: Set to add extracted technologies to
            entity_pos_tags: Optional dict to store entity -> POS tag mapping for later filtering
        """
        if entity_pos_tags is None:
            entity_pos_tags = {}

        exclude_skills = {"senior", "junior", "required", "optional", "available"}

        for token in doc:
            token_text = token.text.strip()
            if not token_text:
                continue

            if token_text.lower() in tech_keywords:
                technologies.add(token_text)
                entity_pos_tags[token_text] = token.pos_
            elif token.lemma_.lower() in tech_keywords:
                technologies.add(token.text)
                entity_pos_tags[token.text] = token.pos_

            if token.pos_ in ("NOUN", "PROPN") and token.dep_ in ("compound", "nmod", "attr") and len(token_text) > 3:
                parent = token.head
                if parent.pos_ in ("NOUN", "PROPN"):
                    phrase_tokens = [
                        child.text
                        for child in doc
                        if (child.head == parent or child == parent)
                        and not child.is_punct
                        and child.text.lower() not in ("and", "or", ",")
                    ]
                    if phrase_tokens:
                        phrase = " ".join(phrase_tokens)
                        if len(phrase) > 3 and "job" not in phrase.lower():
                            skills.add(phrase)
                            entity_pos_tags[phrase] = "NOUN"

            if token.pos_ == "ADJ" and len(token_text) > 4:
                if token_text.lower() not in exclude_skills:
                    skills.add(token_text)
                    entity_pos_tags[token_text] = "ADJ"

    def remove_stopwords(self, text: str) -> str:
        """Remove common English stopwords while preserving important terms.

        Uses spaCy's built-in stopwords list. Preserves technical terms
        and important entities.

        Args:
            text: Input text

        Returns:
            Text with stopwords removed
        """
        if not self.nlp:
            logger.warning("spaCy model not loaded, returning original text")
            return text

        if not text or not text.strip():
            return ""

        try:
            doc = self.nlp(text)

            preserve_terms = {
                "require",
                "required",
                "must",
                "should",
                "will",
                "ability",
                "experience",
                "skill",
                "knowledge",
                "understanding",
            }

            filtered_tokens = []
            for token in doc:
                # Keep tokens that are non-stopwords, preserved terms, named entities or punctuation.
                if not token.is_stop or token.lemma_.lower() in preserve_terms or token.ent_type_ or token.is_punct:
                    filtered_tokens.append(token.text)

            result = " ".join(filtered_tokens).strip()
            logger.debug(f"Removed stopwords: {len(doc)} tokens → {len(filtered_tokens)} tokens")
            return result

        except Exception as e:
            logger.error(f"Error removing stopwords: {e}")
            return text

    def _extract_job_section(self, text: str) -> str:
        """Extract job requirement sections, ignore boilerplate.

        Returns text from recognized job sections, stops at legal disclaimers.
        Returns empty string if no job section found (fallback to original text).
        """
        if not text:
            return ""

        import re

        # Job section headers in priority order; must be followed by a colon or newline to avoid mid-sentence matches.
        job_section_headers = [
            (
                r"(?i)(qualifications|requirements|what we're looking for|what we need|"
                r"what you'll need|must-have|essential|desired qualifications)(?:\s*[:|\n])"
            ),
            (
                r"(?i)(responsibilities|what you'll do|your role|what you will|"
                r"primary responsibilities)(?:\s*[:|\n])"
            ),
            r"(?i)(skills|technical skills|core skills|desired skills)(?:\s*[:|\n])",
        ]

        # Cutoff markers: extraction stops at these.
        cutoff_markers = [
            "equal opportunity",
            "affirmative action",
            "background check",
            "export control",
            "compliance",
            "how to apply",
            "apply now",
            "benefits",
            "compensation",
        ]

        first_match = None
        for pattern in job_section_headers:
            match = re.search(pattern, text)
            if match and (first_match is None or match.start() < first_match.start()):
                first_match = match

        # If no formal job section found, return empty (fallback to original text)
        if not first_match:
            logger.debug("No formal job section found, will use full text")
            return ""

        start_idx = first_match.end()

        cutoff_idx = len(text)
        for marker in cutoff_markers:
            idx = text.lower().find(marker)
            if idx != -1 and idx > start_idx:
                cutoff_idx = min(cutoff_idx, idx)

        section = text[start_idx:cutoff_idx]
        logger.debug(f"Extracted job section: {len(section)} chars from {len(text)}")
        return section

    def _remove_boilerplate(self, text: str) -> str:
        """Remove salary, location, and legal boilerplate from text."""
        if not text:
            return ""

        import re

        # Salary, location metadata, legal, compliance and benefits lines.
        boilerplate_patterns = [
            r"salary.*?(\n|$)",
            r"\$[\d,]+.*?(?:year|hour|annually)",
            r"(?:remote|on-site|location).*?(?:\n|$)",
            r"(?:equal opportunity|affirmative action|fcra|dbids).*?(?:\n|$)",
            r"(?:background check|export control).*?(?:\n|$)",
            r"(?:benefits|compensation|401\(k\)|health insurance).*?(?:\n|$)",
        ]

        cleaned = text
        for pattern in boilerplate_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.DOTALL)

        logger.debug(f"Removed boilerplate: {len(text)} → {len(cleaned)} chars")
        return cleaned

    def _should_skip_entity_common(
        self, entity_clean: str, entity_lower: str, entity_type: str, boilerplate_keywords: Set[str]
    ) -> bool:
        """Check if entity should be skipped due to common validation rules.

        Args:
            entity_clean: Cleaned entity text
            entity_lower: Lowercase entity text
            entity_type: Type of entity (skills, technologies, requirements)
            boilerplate_keywords: Set of boilerplate keywords to filter

        Returns:
            True if entity should be skipped, False otherwise
        """
        # Requirement phrases run longer than skill and technology names, hence 100 vs 70 chars.
        max_length = 100 if entity_type == "requirements" else 70
        if len(entity_clean) < 2 or len(entity_clean) > max_length:
            return True

        if entity_clean.startswith("#"):
            return True

        if any(kw in entity_lower for kw in boilerplate_keywords):
            return True

        # Skip if contains excessive formatting artifacts (but allow parentheses in some contexts)
        if entity_clean.count("\xa0") > 1 or entity_clean.count("(") > 2:
            return True

        return False

    def _is_numeric_or_cost(self, entity_clean: str, entity_lower: str) -> bool:
        """Check if entity is purely numeric or a cost/salary range.

        Args:
            entity_clean: Cleaned entity text
            entity_lower: Lowercase entity text

        Returns:
            True if entity is numeric or cost-related, False otherwise
        """
        if re.match(r"^\d+(\.\d+)?$", entity_clean):
            return True

        if "$" in entity_clean or ("range" in entity_lower and ":" in entity_clean):
            return True

        return False

    def _is_possessive_or_article(self, entity_clean: str, words: list[str]) -> bool:
        """Check if entity is a possessive form, article, or artifact colon.

        Args:
            entity_clean: Cleaned entity text
            words: List of lowercased words in entity

        Returns:
            True if entity should be skipped, False otherwise
        """
        if entity_clean.rstrip().endswith(":"):
            return True

        # Skip possessive forms (Blue Origin's, Carbon Robotics', Blue's)
        if entity_clean.endswith("'s") or entity_clean.endswith("'"):
            return True

        if words and words[0] in ("the", "a", "an"):
            return True

        return False

    def _is_generic_or_incomplete_phrase(self, entity_clean: str, entity_lower: str, words: list[str]) -> bool:
        """Check if entity is a fragment, incomplete phrase, or generic phrase.

        Args:
            entity_clean: Cleaned entity text
            entity_lower: Lowercase entity text
            words: List of lowercased words in entity

        Returns:
            True if entity should be skipped, False otherwise
        """
        # Skip single-word fragments
        if len(words) == 1:
            if entity_lower in ("one", "review", "oversees"):
                return True

        if entity_clean in ("s of Service", "Oversees"):
            return True

        if entity_clean in ("each year", "U.S. National"):
            return True

        return False

    def _is_job_title_or_category(self, entity_lower: str) -> bool:
        """Check if entity is a job title or generic category.

        Args:
            entity_lower: Lowercase entity text

        Returns:
            True if entity is a job title or category, False otherwise
        """
        job_titles = {
            "design and verification engineer",
            "software lead",
            "technical leadership",
            "technical oversight and authority of a range of software solutions",
        }
        if entity_lower in job_titles:
            return True

        generic_categories = {
            "software engineering",
            "software architecture and design",
            "software configuration management",
            "software life cycle management",
            "college of arts",
            "college of arts and sciences",
            "computer science",
        }
        if entity_lower in generic_categories:
            return True

        return False

    def _is_policy_or_responsibility(self, entity_lower: str, words: list[str]) -> bool:
        """Check if entity is a policy keyword or responsibility phrase.

        Args:
            entity_lower: Lowercase entity text
            words: List of lowercased words in entity

        Returns:
            True if entity should be skipped, False otherwise
        """
        policy_patterns = {
            "alcohol",
            "commercial motor",
            "federal motor carrier",
            "pre-ipo",
            "pre-IPO",
            "stock option",
            "regulation",
        }
        if any(pattern in entity_lower for pattern in policy_patterns):
            return True

        if len(words) >= 2:
            action_verbs = {"optimize", "prepare", "manage", "oversee"}
            if words[0] in action_verbs:
                return True

        return False

    def _is_location_or_abbreviation(self, entity_lower: str) -> bool:
        """Check if entity is a location noun or unclear abbreviation.

        Args:
            entity_lower: Lowercase entity text

        Returns:
            True if entity should be skipped, False otherwise
        """
        location_nouns = {"seattle", "rocky", "road test"}
        if entity_lower in location_nouns:
            return True

        if entity_lower in ("hdhp", "blue's"):
            return True

        return False

    def _is_company_name(self, entity_lower: str) -> bool:
        """Check if entity is a company name using word-boundary matching (Issue #194 Phase 7).

        Uses centralized company names taxonomy for consistent filtering.
        Checks both exact matches and partial matches within compound entities.

        Args:
            entity_lower: Lowercase entity text

        Returns:
            True if entity is a company name, False otherwise
        """
        if is_company_keyword(entity_lower, word_boundary=True):
            return True

        # Substring match for compound entities, e.g. "% Carbon Robotics" contains "carbon robotics".
        company_keywords = get_company_keywords()
        if any(company in entity_lower for company in company_keywords):
            return True

        return False

    def _should_skip_requirement(self, entity_clean: str, entity_lower: str, words: list[str]) -> bool:
        """Check if requirement entity should be skipped.

        Args:
            entity_clean: Cleaned entity text
            entity_lower: Lowercase entity text
            words: List of lowercased words in entity

        Returns:
            True if entity should be skipped, False otherwise
        """
        return (
            self._is_numeric_or_cost(entity_clean, entity_lower)
            or self._is_possessive_or_article(entity_clean, words)
            or self._is_generic_or_incomplete_phrase(entity_clean, entity_lower, words)
            or self._is_job_title_or_category(entity_lower)
            or self._is_policy_or_responsibility(entity_lower, words)
            or self._is_location_or_abbreviation(entity_lower)
        )

    def _should_skip_skill(
        self,
        entity_clean: str,
        entity_lower: str,
        words: list[str],
        generic_skills: Set[str],
        company_names: Set[str],
        pos_tag: Optional[str] = None,
        tech_keywords: Optional[Set[str]] = None,
    ) -> bool:
        """Check if skill entity should be skipped (Phase 3: POS-aware filtering).

        Args:
            entity_clean: Cleaned entity text
            entity_lower: Lowercase entity text
            words: List of lowercased words in entity
            generic_skills: Set of generic skill words to filter
            company_names: Set of company names to filter (deprecated: use _is_company_name)
            pos_tag: POS tag of entity (from pre-computed extraction, avoids re-parsing)
            tech_keywords: Set of technology keywords exempted from the single-adjective
                filter below (Issue #211: spaCy tags standalone/attributive tech terms
                like "Agile"/"Lean" as ADJ, which would otherwise drop them)

        Returns:
            True if entity should be skipped, False otherwise
        """
        if re.match(r"^\d+[\d\.,\-]*%?$|^\$[\d,]+", entity_clean):
            return True

        # Skip items containing percentages or large numbers (e.g., "5–50 %", "% Carbon Robotics", "90,000")
        if "%" in entity_clean or re.search(r"\d+[\–-]\d+\s*%?|\d{3,}", entity_clean):
            return True

        if len(words) == 1 and entity_lower in generic_skills:
            return True

        # Single adjectives are filtered only when a POS tag is available, to avoid false positives.
        soft_skills = get_all_soft_skills()
        if pos_tag == "ADJ" and len(words) == 1:
            # Keep a single adjective only if it is a soft skill or tech keyword; spaCy tags "Agile" and "Lean" as ADJ.
            if entity_lower not in soft_skills and entity_lower not in (tech_keywords or set()):
                return True

        # Issue #194 Phase 7: Skip company names using centralized taxonomy with word-boundary matching
        if self._is_company_name(entity_lower):
            return True

        if entity_lower.startswith(("an ", "a ", "the ")):
            if len(words) <= 3 and any(word in generic_skills for word in words[1:]):
                return True

        return False

    @staticmethod
    def _has_excessive_case_transitions(entity: str) -> bool:
        """Detect multi-word fragments with excessive case transitions (MixedCase).

        Examples:
        - "may differCulture StatementDon't" -> 3+ transitions (true)
        - "machine Learning" -> 1 transition (false)

        Args:
            entity: Text to check

        Returns:
            True if entity has 3+ case transitions indicating fragment, False otherwise
        """
        case_transitions = 0
        for i in range(1, len(entity)):
            if entity[i].isupper() != entity[i - 1].isupper():
                case_transitions += 1

        # 3+ transitions typically indicates MixedCase fragment
        return case_transitions >= 3

    @staticmethod
    def _has_unclosed_punctuation(entity: str) -> bool:
        """Check if entity has mismatched or unclosed punctuation.

        Examples:
        - "(incomplete" -> True
        - "test(content)" -> False

        Args:
            entity: Text to check

        Returns:
            True if entity has unclosed punctuation, False otherwise
        """
        unclosed = False
        if entity.count("(") != entity.count(")"):
            unclosed = True
        if entity.count("[") != entity.count("]"):
            unclosed = True
        if entity.count("{") != entity.count("}"):
            unclosed = True

        return unclosed

    @staticmethod
    def _has_html_entity_artifacts(entity: str) -> bool:
        """Check if entity contains HTML entity artifacts.

        Examples:
        - "Requirements&nbsp;Details" -> True
        - "Java developer" -> False

        Args:
            entity: Text to check

        Returns:
            True if entity contains HTML artifacts, False otherwise
        """
        # Named and numeric entities, and tags.
        html_entity_patterns = [
            r"&\w+;",
            r"&#\d+;",
            r"<.*?>",
        ]

        for pattern in html_entity_patterns:
            if re.search(pattern, entity):
                return True

        return False

    @staticmethod
    def _is_suspicious_multi_word_fragment(entity: str) -> bool:
        """Detect suspicious multi-word fragments from HTML parsing issues.

        Multi-word entities with odd spacing, mismatched case, or artifacts.

        Examples:
        - "Required QualificationsTo" -> True (section header artifact)
        - "computer science and years" -> True (oddly split)
        - "the Hiring Manager" -> True (article + proper noun)
        - "RequiredQualificationsTo" -> True (camelCase section header)

        Args:
            entity: Text to check

        Returns:
            True if entity is a suspicious fragment, False otherwise
        """
        words = entity.split()

        if Preprocessor._has_excessive_case_transitions(entity):
            return True

        if Preprocessor._has_unclosed_punctuation(entity):
            return True

        if Preprocessor._has_html_entity_artifacts(entity):
            return True

        if len(words) <= 1:
            return False

        if len(words) >= 2 and words[0].lower() in ("the", "a", "an"):
            if words[1][0].isupper() and len(words) <= 3:
                return True

        # Flag 4+ words with a conjunction or comma in the middle.
        # 3-word extraction artifacts like "software development , Python" pass.
        if len(words) >= 4:
            for w in words[1:-1]:
                if w.lower() in ("and", "or", ","):
                    return True

        return False

    def _filter_entities(
        self, entities: list[str], entity_type: str = "skills", entity_pos_tags: Optional[dict[str, str]] = None
    ) -> list[str]:
        """Filter extracted entities to remove noise and short fragments (Phase 3: POS optimization).

        Validation rules (Phase 12 with requirement-specific filtering):
        - Reject if: len < 2 or len > 70
        - Reject if: Matches boilerplate keywords
        - Reject if: Duplicate
        - For requirements: Skip numbers, possessives, job titles, policies, etc.
        - For skills: Skip generic words, numbers, company names, publications
        - For skills with POS tags: Filter single adjectives not in soft_skills

        Args:
            entities: List of entity strings to filter
            entity_type: Type of entity (skills, technologies, requirements)
            entity_pos_tags: Optional dict mapping entity text to POS tag (avoids re-parsing)
        """
        if entity_pos_tags is None:
            entity_pos_tags = {}
        boilerplate_keywords: Set[str] = {
            "affirmative",
            "action",
            "equal",
            "opportunity",
            "applications",
            "candidates",
            "recruitment",
            "fcra",
            "dbids",
            "compliance",
            "background",
            "check",
            "export",
            "control",
            "base pay",
            "salary",
            "wage",
            "location",
            "remote",
            "drug test",
            "alcohol test",
            "testing",
            "experienced",
            "autonomy",
            "years of",
            "bachelor",
            "master",
            "degree",
        }

        generic_skills: Set[str] = {
            "company",
            "data",
            "time",
            "level",
            "market",
            "process",
            "industry",
            "role",
            "work",
            "job",
            "experience",
            "position",
            "area",
            "field",
            "range",
            "option",
            "form",
            "base",
            "suite",
            "tech",
            "able",
            "available",
            "dollar",
            "pay",
            "year",
            "cost",
            "product",
            "service",
            "employee",
            "employees",
            "culture",
            "team",
            "person",
            "people",
            "value",
            "values",
            "benefit",
            "benefits",
            "compensation",
            "salary",
            "state",
            "location",
            "place",
            "site",
            "office",
            "center",
        }

        # Company names, publications, brands (Issue #194 Phase 7: use expanded taxonomy)
        company_names: Set[str] = get_company_keywords()

        filtered: set[str] = set()
        for entity in entities:
            entity_clean = entity.strip()
            entity_lower = entity_clean.lower()
            words = entity_lower.split()

            # Phase 6: Enhanced fragment detection (Issue #193 Phase 3)
            if self._is_suspicious_multi_word_fragment(entity_clean):
                logger.debug(f"Filtered suspicious fragment: {entity_clean}")
                continue

            if self._should_skip_entity_common(entity_clean, entity_lower, entity_type, boilerplate_keywords):
                continue

            if entity_type == "requirements":
                if self._should_skip_requirement(entity_clean, entity_lower, words):
                    continue
            elif entity_type == "skills":
                pos_tag = entity_pos_tags.get(entity_clean, None)
                if self._should_skip_skill(
                    entity_clean,
                    entity_lower,
                    words,
                    generic_skills,
                    company_names,
                    pos_tag=pos_tag,
                    tech_keywords=self._get_tech_keywords(),
                ):
                    continue

            filtered.add(entity_clean)

        logger.debug(f"Filtered entities: {len(entities)} → {len(filtered)} after validation")
        return sorted(filtered)

    def _is_markdown(self, text: str) -> bool:
        """Detect if text is markdown format (Phase 9, Phase 11 enhanced).

        Checks for markdown indicators: headers, lists, bold, code blocks.
        Prioritizes markdown headers (## Section) as strongest indicator.

        Coupled to the header/divider format synthesized by
        ``src.parsers.html_to_markdown.add_markdown_section_headers``
        ("## "/"### " headers, "---" dividers, Issue #228) — a change to
        that synthesis format must stay in sync with the patterns below.

        Phase 11: Enhance bold detection to recognize bold-formatted headers
        at line start (Issue #241).
        """
        if not text:
            return False

        # Strong indicator: Markdown section headers
        if re.search(r"^##\s+", text, re.MULTILINE):
            return True

        # Headers, lists, bold, inline code and code blocks.
        markdown_indicators = [
            r"^#+\s+",
            r"^[\*\-\+]\s+",
            r"^\d+\.\s+",
            r"^\*\*[^\*]+\*\*",  # Bold-formatted headers at line start (Issue #241)
            r"\*\*.*?\*\*",
            r"__.*?__",
            r"`.*?`",
            r"```.*?```",
        ]

        for pattern in markdown_indicators:
            if re.search(pattern, text, re.MULTILINE):
                return True

        return False

    @staticmethod
    def _classify_section_from_header(header_text: str) -> str:
        """Classify section type from markdown header text.

        Args:
            header_text: Normalized (lowercase) header text

        Returns:
            Section name (qualifications, skills, knowledge, responsibilities, or default)
        """
        if any(kw in header_text for kw in ("qualif", "requirement", "essential")):
            return "qualifications"
        if any(kw in header_text for kw in ("skill", "technical", "core")):
            return "skills"
        if any(kw in header_text for kw in ("knowledge", "experience")):
            return "knowledge"
        if any(kw in header_text for kw in ("respons", "duty", "what you")):
            return "responsibilities"
        return header_text.replace(" ", "_")

    @staticmethod
    def _repair_malformed_dividers(text: str) -> str:
        """Phase 3: Repair malformed dividers (embedded in text).

        Detects lines with embedded dividers (e.g., `:R69380---`) and splits
        them onto separate lines. Removes orphaned Workday refs and colons.

        Skips processing table rows (lines starting with |) to avoid interfering
        with markdown table separator rows.

        Args:
            text: Text with potential embedded dividers

        Returns:
            Text with dividers isolated on separate lines
        """
        if not text:
            return text

        lines = text.split("\n")
        repaired_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                repaired_lines.append("")
                continue

            # Skip processing table rows (lines starting with | are table markup)
            if stripped.startswith("|"):
                repaired_lines.append(line)
                continue

            if "---" in stripped:
                parts = stripped.split("---")
                for i, part in enumerate(parts):
                    part = part.strip()
                    # Remove leading colons from parts (Workday artifact cleanup)
                    part = re.sub(r"^:+\s*", "", part).strip()
                    # Skip pure Workday refs or IDs
                    if part and not re.match(r"^(?:R\d+|\w+\d+)\s*$", part):
                        repaired_lines.append(part)
                    if i < len(parts) - 1:
                        repaired_lines.append("---")
                # Add a final divider only if the line ended with "---" and the loop did not already add one.
                if len(parts) > 1 and not parts[-1].strip():
                    if not repaired_lines or repaired_lines[-1].strip() != "---":
                        repaired_lines.append("---")
            else:
                repaired_lines.append(line)

        result = "\n".join(repaired_lines)

        if result != text:
            logger.debug("Repaired malformed dividers in markdown sections")

        return result

    def _extract_markdown_sections(self, text: str) -> dict[str, str]:
        """Extract sections from structured markdown with divider awareness (Phase 10, Phase 3 enhanced).

        Phase 3: Repair malformed dividers before extraction.
        Phase 11: Recognize bold-formatted headers (Issue #241).
        """
        if not text:
            return {}

        # Phase 3: Repair embedded dividers before processing
        text = self._repair_malformed_dividers(text)

        sections: dict[str, str] = {}
        current_section = "description"
        current_content: list[str] = []

        lines = text.split("\n")
        for line in lines:
            if line.strip() == "---":
                if current_content:
                    sections[current_section] = "\n".join(current_content).strip()
                    current_content = []
                continue

            header_match = re.match(r"^#+\s+(.+)$", line)
            # Check for bold-formatted headers at line start: **Header** (Issue #241)
            bold_header_match = re.match(r"^\*\*([^\*]+)\*\*", line)

            if header_match:
                if current_content:
                    sections[current_section] = "\n".join(current_content).strip()
                    current_content = []

                header_text = header_match.group(1).strip().lower()
                current_section = self._classify_section_from_header(header_text)
            elif bold_header_match:
                if current_content:
                    sections[current_section] = "\n".join(current_content).strip()
                    current_content = []

                header_text = bold_header_match.group(1).strip().lower()
                current_section = self._classify_section_from_header(header_text)

                # If the bold header is not the whole line, the remainder (e.g. "— description") becomes content.
                remaining = line[bold_header_match.end() :].strip()
                if remaining:
                    current_content.append(remaining)
            else:
                if line.strip():
                    current_content.append(line)

        if current_content:
            sections[current_section] = "\n".join(current_content).strip()

        return sections

    @staticmethod
    def _filter_boilerplate_content(section_content: str) -> str:
        """Remove boilerplate phrases from section content.

        Filters out compensation/benefits paragraphs mixed into other sections.

        Args:
            section_content: Raw section text

        Returns:
            Cleaned section text with boilerplate lines removed
        """
        boilerplate_phrases = {
            "carbon robotics follows equitable",
            "offers additional compensation",
            "base pay",
            "pay ranges",
            "pay equity",
            "individual base",
            "pre-ipo stock",
            "target earning",
            "commissions",
            "offers compensation",
            "benefits premiums",
            "on target earning",
        }
        content_lines = []
        for line in section_content.split("\n"):
            line_lower = line.lower()
            if not any(phrase in line_lower for phrase in boilerplate_phrases):
                content_lines.append(line)
        return "\n".join(content_lines)

    @staticmethod
    def _determine_section_type(
        section_name: str,
        skills_section_keywords: Tuple[str, ...],
        req_section_keywords: Tuple[str, ...],
    ) -> Tuple[bool, bool, bool]:
        """Determine section type based on name keywords.

        Args:
            section_name: Name of the section
            skills_section_keywords: Keywords that indicate skills sections
            req_section_keywords: Keywords that indicate requirements sections

        Returns:
            Tuple of (is_skills_section, is_req_section, is_description_section)
        """
        section_lower = section_name.lower()
        is_skills_section = any(kw in section_lower for kw in skills_section_keywords)
        is_req_section = any(kw in section_lower for kw in req_section_keywords)
        is_description_section = any(kw in section_lower for kw in ("description", "overview", "summary", "about"))
        return is_skills_section, is_req_section, is_description_section

    @staticmethod
    def _route_entity_by_section(
        entity_text: str,
        ent_label: str,
        is_skills_section: bool,
        is_req_section: bool,
        is_description_section: bool,
        tech_keywords: Set[str],
        skills: Set[str],
        technologies: Set[str],
        requirements: Set[str],
        skip_ent_types: Set[str],
    ) -> None:
        """Route a single entity to appropriate set based on section type.

        Args:
            entity_text: The entity text to route
            ent_label: spaCy entity label
            is_skills_section: Whether section is skills-focused
            is_req_section: Whether section is requirements-focused
            is_description_section: Whether section is description-focused
            tech_keywords: Set of technology keywords
            skills: Set to add skill entities to
            technologies: Set to add technology entities to
            requirements: Set to add requirement entities to
            skip_ent_types: Entity types to skip
        """
        if not entity_text or len(entity_text) < 2 or ent_label in skip_ent_types:
            return

        if is_skills_section:
            if any(kw in entity_text.lower() for kw in tech_keywords):
                technologies.add(entity_text)
            else:
                skills.add(entity_text)
        elif is_req_section:
            requirements.add(entity_text)
        elif is_description_section:
            if any(kw in entity_text.lower() for kw in tech_keywords):
                technologies.add(entity_text)

    @staticmethod
    def _extract_noun_compounds(
        doc: Any,
        is_skills_section: bool,
        is_description_section: bool,
        section_name: str,
        tech_keywords: Set[str],
        skills: Set[str],
        technologies: Set[str],
    ) -> None:
        """Extract noun compounds and tokens from parsed doc.

        Args:
            doc: spaCy Doc object
            is_skills_section: Whether section is skills-focused
            is_description_section: Whether section is description-focused
            section_name: Name of the section
            tech_keywords: Set of technology keywords
            skills: Set to add skill tokens to
            technologies: Set to add technology tokens to
        """
        if is_skills_section:
            for token in doc:
                if token.pos_ in ("NOUN", "PROPN") and len(token.text) > 2:
                    if token.text.lower() in tech_keywords:
                        technologies.add(token.text)
                    elif token.text not in skills:
                        skills.add(token.text)
        elif is_description_section or section_name == "responsibilities":
            for token in doc:
                if token.text.lower() in tech_keywords and len(token.text) > 2:
                    technologies.add(token.text)

    @staticmethod
    def _normalize_list_item(item: Union[str, Tuple[str, str]]) -> str:
        """Extract text from tuple or string, return normalized item text.

        Args:
            item: String or tuple (from re.findall) to normalize

        Returns:
            Normalized (stripped) item text
        """
        if isinstance(item, tuple):
            item_text = item[0] if item[0] else (item[1] if len(item) > 1 else "")
        else:
            item_text = str(item)
        return item_text.strip()

    @staticmethod
    def _should_skip_list_item(item_text: str) -> bool:
        """Check if item should be skipped based on validation rules.

        Args:
            item_text: Normalized item text

        Returns:
            True if item should be skipped, False otherwise
        """
        if not item_text or len(item_text) < 3:
            return True
        if re.search(r"^\d{4}\s*[-–]\s*\d{4}$", item_text):
            return True
        item_lower = item_text.lower()
        if re.search(r"\d+\s*[-–]\s*\d+\s*years?", item_lower):
            return True
        if re.search(r"^\d+\+\s*years?", item_lower):
            return True
        if re.search(r"\d+\s*years?.*experience", item_lower):
            return True
        if re.search(r"\d+\s*(?:lbs?|kg|meters?|feet?|hours?|days?)", item_lower):
            return True
        return False

    @staticmethod
    def _route_list_item_by_section(
        item_text: str,
        section_name: str,
        is_skills_section: bool,
        is_req_section: bool,
        is_description_section: bool,
        tech_keywords: Set[str],
        skills: Set[str],
        technologies: Set[str],
        requirements: Set[str],
    ) -> None:
        """Route item to appropriate set based on section type.

        Args:
            item_text: Normalized item text
            section_name: Name of the section
            is_skills_section: Whether section is skills-focused
            is_req_section: Whether section is requirements-focused
            is_description_section: Whether section is description-focused
            tech_keywords: Set of technology keywords
            skills: Set to add skill items to
            technologies: Set to add technology items to
            requirements: Set to add requirement items to
        """
        if is_skills_section:
            if len(item_text) > 3 and item_text.count(",") < 2:
                skills.add(item_text)
        elif is_req_section:
            if len(item_text) > 3 and item_text.count(",") < 2:
                requirements.add(item_text)
        elif section_name == "responsibilities" or is_description_section:
            exclude_words = ("design", "architecture", "strategy")
            item_lower = item_text.lower()
            has_excluded = any(word in item_lower for word in exclude_words)
            if len(item_text) > 5 and not has_excluded:
                for keyword in tech_keywords:
                    if keyword in item_lower:
                        technologies.add(keyword)

    @staticmethod
    def _extract_list_items(
        list_items: List[Tuple[str, str]],
        section_name: str,
        is_skills_section: bool,
        is_req_section: bool,
        is_description_section: bool,
        tech_keywords: Set[str],
        skills: Set[str],
        technologies: Set[str],
        requirements: Set[str],
    ) -> None:
        """Extract and route list items based on section type.

        Args:
            list_items: List of regex-matched items (tuples from re.findall)
            section_name: Name of the section
            is_skills_section: Whether section is skills-focused
            is_req_section: Whether section is requirements-focused
            is_description_section: Whether section is description-focused
            tech_keywords: Set of technology keywords
            skills: Set to add skill items to
            technologies: Set to add technology items to
            requirements: Set to add requirement items to
        """
        for item in list_items:
            item_text = Preprocessor._normalize_list_item(item)
            if Preprocessor._should_skip_list_item(item_text):
                continue
            Preprocessor._route_list_item_by_section(
                item_text,
                section_name,
                is_skills_section,
                is_req_section,
                is_description_section,
                tech_keywords,
                skills,
                technologies,
                requirements,
            )

    def _extract_entities_by_section(self, text: str) -> Tuple[Set[str], Set[str], Set[str]]:
        """Extract entities intelligently from markdown sections using NER (Phase 11).

        Routes entities to skills, technologies, or requirements based on section type.
        Skips: Benefits, How to Apply, About, Company Culture, Legal content.
        """
        if not self.nlp or not text:
            return set(), set(), set()

        skills: Set[str] = set()
        technologies: Set[str] = set()
        requirements: Set[str] = set()

        sections = self._extract_markdown_sections(text)
        tech_keywords = self._get_tech_keywords()

        skip_sections = self.SKIP_SECTIONS

        skills_section_keywords = ("skill", "technical", "core", "competency", "ability", "expertise", "proficiency")
        req_section_keywords = (
            "requirement",
            "qualif",
            "needed",
            "essential",
            "must",
            "knowledge",
            "experience",
            "responsibility",
            "duty",
        )

        skip_ent_types = {"ORG", "PRODUCT", "QUANTITY", "CARDINAL", "DATE", "TIME", "MONEY"}

        for section_name, section_content in sections.items():
            section_lower = section_name.lower().replace("_", " ")
            if any(skip_kw in section_lower for skip_kw in skip_sections):
                continue
            if not section_content.strip():
                continue

            section_content = self._filter_boilerplate_content(section_content)
            if not section_content.strip():
                continue

            try:
                doc = self.nlp(section_content)
            except Exception:
                continue

            list_items = re.findall(r"^[\*\-\+]\s+(.+)$|^\d+\.\s+(.+)$", section_content, re.MULTILINE)

            is_skills_section, is_req_section, is_description_section = self._determine_section_type(
                section_name, skills_section_keywords, req_section_keywords
            )
            # Keep in sync with the "responsibilities" cases in _extract_noun_compounds and _route_list_item_by_section.
            # "responsibilities" does not substring-match "responsibility", so fold it in explicitly.
            if section_name == "responsibilities":
                is_req_section = True

            for ent in doc.ents:
                self._route_entity_by_section(
                    ent.text.strip(),
                    ent.label_,
                    is_skills_section,
                    is_req_section,
                    is_description_section,
                    tech_keywords,
                    skills,
                    technologies,
                    requirements,
                    skip_ent_types,
                )

            self._extract_noun_compounds(
                doc,
                is_skills_section,
                is_description_section,
                section_name,
                tech_keywords,
                skills,
                technologies,
            )

            self._extract_list_items(
                list_items,
                section_name,
                is_skills_section,
                is_req_section,
                is_description_section,
                tech_keywords,
                skills,
                technologies,
                requirements,
            )

        logger.debug(
            f"Entity extraction by section: {len(skills)} skills, "
            f"{len(technologies)} technologies, {len(requirements)} requirements"
        )
        return skills, technologies, requirements

    @staticmethod
    def _extract_soft_skills(doc: Any, soft_skills: Set[str]) -> None:
        """Extract soft skills from tokens."""
        soft_skills_list = get_all_soft_skills()
        tokens_list = list(doc)

        for token in tokens_list:
            token_text = token.text.strip()
            if not token_text or len(token_text) < 3:
                continue

            if token_text.lower() in soft_skills_list:
                soft_skills.add(token_text)
            elif token.lemma_.lower() in soft_skills_list:
                soft_skills.add(token.text)

            if token.pos_ in ("ADJ", "NOUN"):
                parent = token.head
                if parent.pos_ in ("NOUN", "ADJ") and parent != token:
                    phrase = " ".join(child.text for child in tokens_list if child.head == parent or child == parent)
                    if 3 < len(phrase) < 50 and phrase.lower() in soft_skills_list:
                        soft_skills.add(phrase)
