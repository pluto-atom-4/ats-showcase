"""LLM model configuration and validation."""

from typing import Dict, Tuple

DEFAULT_MODEL = "claude-sonnet-5"

SUPPORTED_MODELS: Dict[str, Tuple[str, float, float]] = {
    "claude-haiku-4-5-20251001": (
        "claude-haiku-4-5-20251001",
        0.80,
        4.0,
    ),
    "claude-sonnet-5": (
        "claude-sonnet-5",
        3.0,
        15.0,
    ),
    "claude-opus-4-8": (
        "claude-opus-4-8",
        15.0,
        75.0,
    ),
}

# Aliases: short names map to full model IDs
MODEL_ALIASES: Dict[str, str] = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-5",
    "opus": "claude-opus-4-8",
}


def resolve_model_alias(model_input: str) -> str:
    """Resolve model alias to full model ID.

    Args:
        model_input: Model ID or alias (e.g., "sonnet" or "claude-sonnet-5")

    Returns:
        Full model ID
    """
    # Check if it's an alias (case-insensitive)
    lower_input = model_input.lower()
    if lower_input in MODEL_ALIASES:
        return MODEL_ALIASES[lower_input]
    # Return as-is if not an alias (assume full ID)
    return model_input


def validate_model(model_id: str) -> None:
    """Validate model ID is supported.

    Args:
        model_id: Claude model ID or alias

    Raises:
        ValueError: If model not in SUPPORTED_MODELS
    """
    # Resolve alias first
    resolved_id = resolve_model_alias(model_id)

    if resolved_id not in SUPPORTED_MODELS:
        aliases = ", ".join(MODEL_ALIASES.keys())
        supported = ", ".join(SUPPORTED_MODELS.keys())
        raise ValueError(
            f"Invalid model: {model_id}\n"
            f"  Aliases: {aliases}\n"
            f"  Full IDs: {supported}"
        )


def get_model_pricing(model_id: str) -> Tuple[float, float]:
    """Get pricing for model (input, output per 1M tokens).

    Args:
        model_id: Claude model ID or alias

    Returns:
        (input_price, output_price) per 1M tokens

    Raises:
        ValueError: If model not supported
    """
    validate_model(model_id)
    resolved_id = resolve_model_alias(model_id)
    _, input_price, output_price = SUPPORTED_MODELS[resolved_id]
    return input_price, output_price


def get_model_display_name(model_id: str) -> str:
    """Get short display name for model.

    Args:
        model_id: Full model ID (e.g. claude-haiku-4-5-20251001)

    Returns:
        Short name (e.g. Haiku, Sonnet, Opus)
    """
    if "haiku" in model_id.lower():
        return "Haiku"
    elif "sonnet" in model_id.lower():
        return "Sonnet"
    elif "opus" in model_id.lower():
        return "Opus"
    else:
        return model_id


def get_supported_models_list() -> str:
    """Get formatted list of supported models for help text.

    Returns:
        Comma-separated list of model IDs
    """
    return ", ".join(SUPPORTED_MODELS.keys())
