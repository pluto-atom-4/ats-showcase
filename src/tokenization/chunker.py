"""Semantic chunking of text for optimal token efficiency."""

import logging
import re
from typing import Any, List

logger = logging.getLogger(__name__)


class SemanticChunker:
    """Chunk text by sentences to maintain semantic boundaries."""

    def __init__(
        self,
        target_chunk_size: int = 400,
        overlap: int = 50,
        preserve_requirement_spans: bool = True,
    ):
        """
        Initialize chunker.

        Args:
            target_chunk_size: Target tokens per chunk (~400 typical)
            overlap: Overlap tokens between chunks for context
            preserve_requirement_spans: Never split requirement spans across chunks
        """
        self.target_chunk_size = target_chunk_size
        self.overlap = overlap
        self.preserve_requirement_spans = preserve_requirement_spans
        self.nlp: Any = self._load_spacy()

    def _load_spacy(self) -> Any | None:
        """Load spaCy NLP model for sentence segmentation."""
        try:
            import spacy

            nlp = spacy.load("en_core_web_md")
            logger.debug("Loaded spaCy en_core_web_md")
            return nlp
        except Exception as e:
            logger.warning(f"Failed to load spaCy: {e}")
            return None

    def chunk(self, text: str, sentences: List[str] | None = None, doc: Any | None = None) -> List[str]:
        """
        Chunk text by sentences, respecting target size and requirement spans.

        Chunks at sentence boundaries (not random token breaks) to preserve meaning.
        If preserve_requirement_spans is True, never splits a requirement span across chunks.

        Args:
            text: Original text to chunk
            sentences: Optional pre-segmented sentences (uses spaCy if None)
            doc: Optional spaCy Doc with requirement_spans attribute (for span preservation)

        Returns:
            List of semantic chunks
        """
        if not text or not text.strip():
            return []

        logger.debug(f"Chunking text into ~{self.target_chunk_size} token chunks")

        if sentences is None:
            sentences = self._segment_sentences(text)

        if not sentences:
            return [text] if text.strip() else []

        requirement_spans: list[dict[str, Any]] = []
        if self.preserve_requirement_spans and doc is not None:
            requirement_spans = getattr(doc._, "requirement_spans", [])

        chunks = self._accumulate_chunks(sentences, requirement_spans)

        logger.debug(f"Created {len(chunks)} chunks from {len(sentences)} sentences")
        return chunks

    def _accumulate_chunks(
        self,
        sentences: List[str],
        requirement_spans: list[dict[str, Any]],
    ) -> List[str]:
        """
        Accumulate sentences into chunks respecting size and span boundaries.

        Args:
            sentences: List of segmented sentences
            requirement_spans: List of requirement span dicts (may be empty)

        Returns:
            List of chunks
        """
        chunks = []
        current_chunk: list[str] = []
        current_word_count = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            word_count = len(sentence.split())

            if current_word_count + word_count > (self.target_chunk_size / 4) and current_chunk:
                chunk_text = " ".join(current_chunk)

                if self.preserve_requirement_spans and requirement_spans:
                    if self._would_split_requirement_span(chunk_text, requirement_spans):
                        # Finalizing would split a requirement span: keep adding unless the chunk is already huge.
                        if current_word_count < self.target_chunk_size:
                            current_chunk.append(sentence)
                            current_word_count += word_count
                            continue

                chunks.append(chunk_text)
                current_chunk = [sentence]
                current_word_count = word_count
            else:
                current_chunk.append(sentence)
                current_word_count += word_count

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def _segment_sentences(self, text: str) -> List[str]:
        """
        Segment text into sentences using spaCy NLP.

        Args:
            text: Text to segment

        Returns:
            List of sentences
        """
        if not self.nlp:
            return [text]

        try:
            doc = self.nlp(text)
            sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
            return sentences
        except Exception as e:
            logger.warning(f"spaCy segmentation failed: {e}, returning whole text")
            return [text]

    def _would_split_requirement_span(
        self,
        chunk_text: str,
        requirement_spans: List[dict[str, Any]],
    ) -> bool:
        """
        Check if chunk boundary would split a requirement span.

        Args:
            chunk_text: Text of the current chunk
            requirement_spans: List of requirement span dicts from Phase 8b

        Returns:
            True if splitting here would break a requirement span
        """
        if not requirement_spans or not chunk_text:
            return False

        for span in requirement_spans:
            span_text = span.get("span_text", "")
            if not span_text:
                continue

            # Normalize whitespace for matching (Bug #5 fix)
            normalized_span_text = re.sub(r"\s+", " ", span_text).strip()
            normalized_chunk_text = re.sub(r"\s+", " ", chunk_text).strip()

            if normalized_span_text in normalized_chunk_text:
                continue

            # Bug #1 fix: a plain substring find misses spans split across chunks ("Python and Docker").
            # Check for a partial match on word boundaries instead.
            words = normalized_span_text.split()
            if len(words) > 1:
                first_word = words[0]
                # Use word boundary regex to avoid false positives (e.g., "Python" in "Cython")
                first_word_pattern = r"\b" + re.escape(first_word) + r"\b"
                if (
                    re.search(first_word_pattern, normalized_chunk_text)
                    and normalized_span_text not in normalized_chunk_text
                ):
                    logger.debug(f"Would split requirement span: {normalized_span_text[:30]}...")
                    return True

            # Check span prefix (for cases like "Python and Docker" → chunk ends at "Python and")
            if len(normalized_span_text) > 3:
                span_prefix = normalized_span_text[: len(normalized_span_text) // 2]
                if span_prefix in normalized_chunk_text and normalized_span_text not in normalized_chunk_text:
                    logger.debug(f"Would split requirement span: {normalized_span_text[:30]}...")
                    return True

        return False

    def estimate_chunk_tokens(self, chunk: str) -> int:
        """
        Estimate tokens in a chunk (before tiktoken count).

        Uses rough heuristic: 1 token ≈ 4 characters (average for English).

        Args:
            chunk: Text chunk

        Returns:
            Estimated token count
        """
        words = len(chunk.split())
        estimated_tokens = max(1, int(words * 1.3))
        return estimated_tokens
