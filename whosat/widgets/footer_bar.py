from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from whosat.theme import ThemePalette
from whosat.types import UIState


class FooterBar(Static):
    """Single-row footer with keyboard shortcuts and countdown."""

    def update_view(
        self,
        state: UIState,
        version: str,
        status_message: str = "",
        palette: ThemePalette | None = None,
    ) -> None:
        p = palette
        width = self._current_width()

        right = Text(no_wrap=True)
        if state.next_refresh_eta is not None and state.refresh_interval_seconds:
            right.append("next ", style=p.text_dim if p else "#5a6a7a")
            right.append(f"{state.next_refresh_eta}s", style=f"bold {p.secondary if p else '#00d4ff'}")
            right.append(" \u00b7 ", style=p.text_dim if p else "#5a6a7a")
        right.append(f"v{version}", style=p.text_dim if p else "#5a6a7a")

        if status_message:
            left = Text(no_wrap=True)
            left.append(status_message, style=self._status_color(status_message, p))
        else:
            left = self._shortcut_text(p, state)

        rendered = self._fit_line(left, right, width)
        self.update(rendered)

    def _shortcut_text(self, p: ThemePalette | None, state: UIState | None = None) -> Text:
        text3 = p.text_dim if p else "#5a6a7a"
        text2 = p.text_secondary if p else "#8aa0b0"
        bg2 = p.panel_alt if p else "#13181f"
        border2 = "#243040"

        t = Text(no_wrap=True)

        # View switching shortcuts first
        view_items = [
            ("1", "ports"),
            ("2", "memory"),
        ]
        for idx, (key, label) in enumerate(view_items):
            if idx:
                t.append("  ")
            t.append("[", style=border2)
            t.append(key, style=f"bold {text2} on {bg2}")
            t.append("]", style=border2)
            t.append(f" {label}", style=text3)

        t.append("  │  ", style=text3)

        items = [
            ("\u2191\u2193", "navigate"),
            ("Enter", "expand"),
            ("K", "kill"),
            ("/", "search"),
            ("R", "refresh"),
            ("G", "group"),
            ("T", "theme"),
            ("Q", "quit"),
        ]
        for idx, (key, label) in enumerate(items):
            if idx:
                t.append("  ")
            t.append("[", style=border2)
            t.append(key, style=f"bold {text2} on {bg2}")
            t.append("]", style=border2)
            t.append(f" {label}", style=text3)
        return t

    def _fit_line(self, left: Text, right: Text, width: int) -> Text:
        if width <= 0:
            out = Text(no_wrap=True)
            out.append_text(left)
            out.append("  ")
            out.append_text(right)
            return out
        left_len = left.cell_len
        right_len = right.cell_len
        min_gap = 2
        available_left = max(0, width - right_len - min_gap)
        if left_len > available_left:
            left = left.copy()
            left.truncate(max(0, available_left), overflow="ellipsis")
            left_len = left.cell_len
        gap = max(1, width - left_len - right_len)
        out = Text(no_wrap=True)
        out.append_text(left)
        out.append(" " * gap)
        out.append_text(right)
        return out

    def _current_width(self) -> int:
        try:
            return max(0, self.size.width)
        except Exception:
            return 0

    def _status_color(self, msg: str, p: ThemePalette | None) -> str:
        low = msg.lower()
        if "docker daemon reachable" in low or "pip install whosat[docker]" in low:
            return p.secondary if p else "#00d4ff"
        if "not running" in low or "permission denied" in low:
            return p.danger if p else "#ff4466"
        if "theme:" in low or "copied" in low or "terminated" in low:
            return p.accent if p else "#00ff88"
        return p.warn if p else "#ffd060"
