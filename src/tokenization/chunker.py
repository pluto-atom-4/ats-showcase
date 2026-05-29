"""Semantic chunking of text for optimal token efficiency."""

import logging
from typing import List

logger = logging.getLogger(__name__)


class SemanticChunker:
    """Chunk text by sentences to maintain semantic boundaries."""

    def __init__(self, target_chunk_size: int = 400, overlap: int = 50):
        """
        Initialize chunker.

        Args:
            target_chunk_size: Target tokens per chunk (~400 typical)
            overlap: Overlap tokens between chunks for context
        """
        self.target_chunk_size = target_chunk_size
        self.overlap = overlap
        self.nlp = self._load_spacy()

    def _load_spacy(self):
        """Load spaCy NLP model for sentence segmentation."""
        try:
            import spacy

            nlp = spacy.load("en_core_web_md")
            logger.debug("Loaded spaCy en_core_web_md")
            return nlp
        except Exception as e:
            logger.warning(f"Failed to load spaCy: {e}")
            return None

    def chunk(self, text: str, sentences: List[str] | None = None) -> List[str]:
        """
        Chunk text by sentences, respecting target size.

        Chunks at sentence boundaries (not random token breaks) to preserve meaning.

        Args:
            text: Original text to chunk
            sentences: Optional pre-segmented sentences (uses spaCy if None)

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
                chunks.append(chunk_text)
                current_chunk = [sentence]
                current_word_count = word_count
            else:
                current_chunk.append(sentence)
                current_word_count += word_count

        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append(chunk_text)

        logger.debug(f"Created {len(chunks)} chunks from {len(sentences)} sentences")
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
