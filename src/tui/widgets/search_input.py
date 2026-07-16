"""Search input widget for job table filtering."""

from typing import Any

from textual.message import Message
from textual.widgets import Input


class SearchInput(Input):
    """Text input for searching jobs by title/company/location.

    Emits SearchChanged message when text changes.
    """

    class SearchChanged(Message):
        """Posted when search text changes."""

        def __init__(self, query: str) -> None:
            super().__init__()
            self.query = query

    DEFAULT_CSS = """
    SearchInput {
        width: 1fr;
        height: 1;
        border: solid $accent;
        padding: 0 1;
    }
    """

    def __init__(
        self, placeholder: str = "Search jobs...", **kwargs: Any
    ) -> None:
        super().__init__(placeholder=placeholder, **kwargs)

    def on_input_changed(self, message: Input.Changed) -> None:
        """Emit SearchChanged when input text changes."""
        self.post_message(self.SearchChanged(message.value))


class FilterBar(Input):
    """Filter bar for status/score filtering.

    Supports filters like:
    - status:confirmed
    - status:rejected
    - score:>80
    - score:<70
    """

    class FilterChanged(Message):
        """Posted when filter text changes."""

        def __init__(self, filters: str) -> None:
            super().__init__()
            self.filters = filters

    DEFAULT_CSS = """
    FilterBar {
        width: 1fr;
        height: 1;
        border: solid $accent;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        placeholder: str = "Filter by status:confirmed...",
        **kwargs: Any,
    ) -> None:
        super().__init__(placeholder=placeholder, **kwargs)

    def on_input_changed(self, message: Input.Changed) -> None:
        """Emit FilterChanged when filter text changes."""
        self.post_message(self.FilterChanged(message.value))
