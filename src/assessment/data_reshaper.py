"""Reshape preprocessed job data for optimal Claude API consumption."""

import logging
from typing import Any, Dict, List, Optional, Tuple

from src.tokenization.counter import TokenCounter

logger = logging.getLogger(__name__)

_token_counter = TokenCounter()


class DataReshaper:
    """Convert preprocessed data into Claude-friendly formats."""

    @staticmethod
    def chunk_by_sentences(
        text: str, target_tokens: int = 400
    ) -> List[str]:
        """Group text into semantic chunks at sentence boundaries.

        Splits text at sentence breaks to preserve meaning; does not split
        mid-sentence. Chunks vary 100–600 tokens intentionally.

        Args:
            text: Clean job description text
            target_tokens: Target tokens per chunk (~400)

        Returns:
            List of semantic chunks
        """
        if not text or not text.strip():
            return []

        # Split on sentence boundaries (period, question mark, exclamation)
        sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".")
                     if s.strip()]

        chunks: List[str] = []
        current_chunk: List[str] = []
        current_tokens = 0

        for sent in sentences:
            sent_tokens = _token_counter.count_tokens(sent)

            # If adding this sentence exceeds target, finalize current chunk
            if current_tokens + sent_tokens > target_tokens and current_chunk:
                chunk_text = " ".join(current_chunk)
                chunks.append(chunk_text)
                logger.debug(f"Chunk: {len(chunk_text)} chars, {current_tokens} tokens")

                current_chunk = [sent]
                current_tokens = sent_tokens
            else:
                current_chunk.append(sent)
                current_tokens += sent_tokens

        # Add final chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append(chunk_text)
            logger.debug(f"Final chunk: {len(chunk_text)} chars, {current_tokens} tokens")

        logger.info(f"Chunked text into {len(chunks)} semantic chunks")
        return chunks

    @staticmethod
    def format_extracted_entities(
        skills: List[str],
        technologies: List[str],
        requirements: List[str],
        limit: int = 15,
    ) -> str:
        """Format extracted entities as readable text block.

        Args:
            skills: Extracted skills
            technologies: Extracted technologies
            requirements: Extracted requirements
            limit: Max entities per category to display

        Returns:
            Formatted entity block for inclusion in prompt
        """
        lines = []

        if skills:
            skills_text = ", ".join(skills[:limit])
            lines.append(f"**Skills:** {skills_text}")

        if technologies:
            tech_text = ", ".join(technologies[:limit])
            lines.append(f"**Tech Stack:** {tech_text}")

        if requirements:
            reqs_text = ", ".join(requirements[:limit])
            lines.append(f"**Requirements:** {reqs_text}")

        return "\n".join(lines) if lines else ""

    @staticmethod
    def prepare_assessment_context(
        cv_text: str,
        job_description: str,
        extracted_entities: Optional[Tuple[List[str], List[str], List[str]]] = None,
        chunks: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Prepare assessment context for LLM prompt.

        Combines CV, job description, extracted entities, and chunks
        into structured context. Counts tokens for cost estimation.

        Args:
            cv_text: Preprocessed CV text
            job_description: Preprocessed job description
            extracted_entities: Tuple of (skills, tech, requirements)
            chunks: Semantic chunks of job description

        Returns:
            Dict with 'cv', 'job', 'entities', 'chunks', 'token_count'
        """
        if extracted_entities is None:
            extracted_entities = ([], [], [])

        chunks_list: List[str] = chunks if chunks is not None else []

        # Format entities
        entities_text = DataReshaper.format_extracted_entities(*extracted_entities)

        # Build context
        context: Dict[str, Any] = {
            "cv": cv_text,
            "job_description": job_description,
            "entities": entities_text,
            "chunks": chunks_list,
        }

        # Count tokens for cost estimation
        full_text = f"{cv_text}\n{job_description}\n{entities_text}\n{chr(10).join(chunks_list)}"
        token_count = _token_counter.count_tokens(full_text)

        context["token_count"] = token_count

        logger.debug(f"Assessment context prepared: {token_count} tokens")
        return context
