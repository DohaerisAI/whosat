from __future__ import annotations

from textual.message import Message
from textual.widgets import Static


class Pill(Static):
    """Reusable pill/badge widget with color variants.

    Usage:
        Pill("SYS", variant="sys", id="my-pill")

    Variants: sys, docker, online, warn, down, count
    CSS classes added: pill-{variant}
    Toggle pill-active class for active state.
    """

    class Clicked(Message):
        def __init__(self, pill: "Pill") -> None:
            self.pill = pill
            super().__init__()

    def __init__(self, label: str, variant: str = "default", **kwargs):
        super().__init__(label, **kwargs)
        self.variant = variant
        self.add_class(f"pill-{variant}")

    def on_click(self) -> None:
        self.post_message(self.Clicked(self))
