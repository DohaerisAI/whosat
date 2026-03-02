from __future__ import annotations

import time

from rich.text import Text
from textual.widgets import Static

from whosat.theme import ThemePalette


class RefreshProgressBar(Static):
    """Thin 1-row progress bar that fills smoothly left→right between refreshes."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._start_ts: float = 0.0
        self._interval: float = 30.0
        self._palette: ThemePalette | None = None
        self._timer = None

    def on_mount(self) -> None:
        self._timer = self.set_interval(1 / 30, self._tick)

    def _tick(self) -> None:
        self._render_bar()

    def set_refresh_timing(
        self,
        start_ts: float,
        interval_seconds: int,
        palette: ThemePalette | None = None,
    ) -> None:
        """Called by the app when a refresh completes or interval changes."""
        self._start_ts = start_ts
        self._interval = max(1, interval_seconds)
        if palette is not None:
            self._palette = palette

    def update_view(self, ratio: float, palette: ThemePalette | None = None) -> None:
        """Legacy compat — just store palette, bar self-renders."""
        if palette is not None:
            self._palette = palette

    def _render_bar(self) -> None:
        p = self._palette
        width = self.size.width if getattr(self, "size", None) else 0
        if width <= 0:
            return

        if self._start_ts <= 0 or self._interval <= 0:
            ratio = 0.0
        else:
            elapsed = time.time() - self._start_ts
            ratio = max(0.0, min(1.0, elapsed / self._interval))

        fill = int(width * ratio)
        t = Text()
        if fill > 0:
            green_len = max(0, fill - max(1, fill // 4))
            cyan_len = fill - green_len
            if green_len:
                t.append("━" * green_len, style=p.accent if p else "#00ff88")
            if cyan_len:
                t.append("━" * cyan_len, style=p.secondary if p else "#00d4ff")
        if width - fill > 0:
            bg = p.panel_alt if p else "#1a2030"
            t.append("━" * (width - fill), style=bg)
        self.update(t)
