"""Formatting utilities for TUI display."""


def format_tokens(tokens: int) -> str:
    """Format token count with thousands separator.

    Args:
        tokens: Token count

    Returns:
        Formatted string like "12,450"
    """
    return f"{tokens:,}"


def format_cost(cost_usd: float) -> str:
    """Format cost in USD with 6 decimal places.

    Args:
        cost_usd: Cost in USD

    Returns:
        Formatted string like "$0.003750"
    """
    return f"${cost_usd:.6f}"


def format_speed(items_per_sec: float) -> str:
    """Format throughput speed.

    Args:
        items_per_sec: Items per second

    Returns:
        Formatted string like "12.5/s" or "--/s" if 0
    """
    if items_per_sec == 0:
        return "--/s"
    return f"{items_per_sec:.1f}/s"


def format_eta(seconds: float) -> str:
    """Format estimated time to completion.

    Args:
        seconds: ETA in seconds

    Returns:
        Formatted string like "2m 15s" or "--" if 0
    """
    if seconds == 0:
        return "--"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes == 0:
        return f"{secs}s"
    return f"{minutes}m {secs}s"


def format_elapsed(seconds: float) -> str:
    """Format elapsed time.

    Args:
        seconds: Elapsed time in seconds

    Returns:
        Formatted string like "2m 15s" or "45s"
    """
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes == 0:
        return f"{secs}s"
    return f"{minutes}m {secs}s"


def format_progress_bar(percent: float, width: int = 40) -> str:
    """Format progress bar.

    Args:
        percent: Percentage (0-100)
        width: Bar width in characters

    Returns:
        Progress bar like "████████░░░░░░░░░░░░░"
    """
    filled = int((percent / 100) * width)
    bar = "█" * filled + "░" * (width - filled)
    return bar


def truncate(text: str, max_len: int = 50) -> str:
    """Truncate text to max length with ellipsis.

    Args:
        text: Text to truncate
        max_len: Maximum length

    Returns:
        Truncated text like "Senior Python Developer..."
    """
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
