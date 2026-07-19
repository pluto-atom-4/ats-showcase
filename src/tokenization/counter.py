"""Token counting and cost estimation using tiktoken."""

import logging
from typing import Dict, List, Optional

from src.config.models import DEFAULT_MODEL, get_model_pricing

try:
    import tiktoken
except ImportError:
    tiktoken = None  # type: ignore

logger = logging.getLogger(__name__)


class TokenCounter:
    """Count tokens using tiktoken for Claude models."""

    def __init__(self, model: str = DEFAULT_MODEL):
        """
        Initialize token counter for Claude model.

        Args:
            model: Claude model identifier (default: claude-sonnet-5)
        """
        self.model = model
        self.encoding: Optional["tiktoken.Encoding"] = None
        self._load_encoding()

    def _load_encoding(self) -> None:
        """Load tiktoken encoding for the model."""
        try:
            import tiktoken

            self.encoding = tiktoken.get_encoding("cl100k_base")
            logger.info(f"Loaded tiktoken cl100k_base for {self.model}")
        except ImportError:
            logger.warning("tiktoken not available, will use fallback token counting")
            self.encoding = None
        except Exception as e:
            logger.error(f"Failed to load tiktoken: {e}")
            self.encoding = None

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken.

        Falls back to word-based estimation if tiktoken unavailable.

        Args:
            text: Input text

        Returns:
            Token count
        """
        if not text:
            return 0

        if self.encoding:
            try:
                tokens = self.encoding.encode(text)
                return len(tokens)
            except Exception as e:
                logger.warning(f"tiktoken encoding failed: {e}, using fallback")

        return self._estimate_tokens(text)

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate tokens using heuristic (fallback).

        Heuristic: 1 token ≈ 1.3 words on average.

        Args:
            text: Input text

        Returns:
            Estimated token count
        """
        words = len(text.split())
        estimated = max(1, int(words * 1.3))
        return estimated

    def count_chunks(self, chunks: List[str]) -> Dict[int, int]:
        """
        Count tokens for each chunk.

        Args:
            chunks: List of text chunks

        Returns:
            Dict of chunk_index -> token_count
        """
        return {i: self.count_tokens(chunk) for i, chunk in enumerate(chunks)}

    def estimate_cost(
        self, input_tokens: int, output_tokens: int = 300
    ) -> float:
        """Estimate cost for API call.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Expected output tokens (default: 300 for assessment)
                Assumption: Job assessment responses typically 200-400 tokens
                This 300-token estimate is more realistic than prior 100-token default

        Returns:
            Estimated cost in USD (based on model's input/output rates per 1M tokens)
        """
        input_price, output_price = get_model_pricing(self.model)
        input_cost = (input_tokens / 1_000_000) * input_price
        output_cost = (output_tokens / 1_000_000) * output_price
        return input_cost + output_cost

    def format_cost(self, cost: float) -> str:
        """
        Format cost as readable string.

        Args:
            cost: Cost in USD

        Returns:
            Formatted cost string (e.g., "$0.0024")
        """
        return f"${cost:.4f}"
