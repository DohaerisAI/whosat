from __future__ import annotations

from collections import defaultdict

from rich.text import Text
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Static

from whosat.theme import ThemePalette
from whosat.types import AppSnapshot, CategoryItem


class _CatBtn(Static):
    """Clickable category row — single line with icon, name, and status counts."""

    class Pressed(Message):
        def __init__(self, cat_key: str) -> None:
            self.cat_key = cat_key
            super().__init__()

    def __init__(self, cat_key: str, **kwargs):
        super().__init__(**kwargs)
        self._cat_key = cat_key

    def on_click(self) -> None:
        self.post_message(self.Pressed(self._cat_key))


class Sidebar(VerticalScroll):
    class CategorySelected(Message):
        def __init__(self, sender: "Sidebar", category_key: str) -> None:
            self.category_key = category_key
            super().__init__()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._categories: list[CategoryItem] = []
        self._selected_key = "all"

    def update_categories(
        self,
        categories: list[CategoryItem],
        selected_key: str | None,
        snapshot: AppSnapshot | None = None,
        palette: ThemePalette | None = None,
    ) -> None:
        self._categories = categories
        self._selected_key = selected_key or "all"
        self._rebuild(snapshot, palette)

    def _rebuild(self, snapshot: AppSnapshot | None, palette: ThemePalette | None) -> None:
        self.remove_children()

        grouped: dict[str, list[CategoryItem]] = defaultdict(list)
        for c in self._categories:
            grouped[c.section].append(c)

        order = ["Categories", "System", "Database", "Docker"]
        for sec in order:
            items = grouped.get(sec, [])
            if not items:
                continue
            self.mount(Static(self._section_header(sec, palette), classes="section-hdr"))
            for c in items:
                active = c.key == self._selected_key
                cls = "cat-active" if active else ""
                btn = _CatBtn(c.key, classes=f"cat-item {cls}".strip())
                btn.update(self._cat_line(c, active, palette))
                self.mount(btn)

        # Quick stats at bottom
        if snapshot is not None:
            self.mount(Static(self._quick_stats(snapshot, palette), classes="quick"))

    def _section_header(self, title: str, palette: ThemePalette | None) -> Text:
        p = palette
        text3 = p.text_dim if p else "#5a6a7a"
        border = p.border if p else "#1e2a38"
        t = Text(no_wrap=True)
        label = title.upper()
        t.append(label, style=f"bold {text3}")
        remaining = max(0, 24 - len(label) - 1)
        if remaining > 0:
            t.append(" ")
            t.append("─" * remaining, style=border)
        return t

    def _cat_line(self, c: CategoryItem, active: bool, palette: ThemePalette | None) -> Text:
        p = palette
        accent = p.accent if p else "#00ff88"
        text2 = p.text_secondary if p else "#8aa0b0"
        text3 = p.text_dim if p else "#5a6a7a"
        green = p.accent if p else "#00ff88"
        yellow = p.warn if p else "#ffd060"
        red = p.danger if p else "#ff4466"
        bg3 = p.panel_alt if p else "#1a2030"

        name_color = accent if active else text2

        # Build right-side: count + up/down indicators
        right = Text(no_wrap=True)
        if c.up_count:
            right.append(f"{c.up_count}\u2191", style=f"bold {green}")
        if c.warn_count:
            if right.cell_len:
                right.append(" ")
            right.append(f"{c.warn_count}\u26a0", style=f"bold {yellow}")
        if c.down_count:
            if right.cell_len:
                right.append(" ")
            right.append(f"{c.down_count}\u2193", style=f"bold {red}")
        # Always show total count
        if right.cell_len:
            right.append(" ")
        count_style = f"bold {accent}" if active else f"bold {text3}"
        right.append(f"{c.count}", style=count_style)

        # Build left side: icon + name
        left = Text(no_wrap=True)
        left.append(f"{c.icon} ", style=text2)
        left.append(c.label, style=f"bold {name_color}")

        # Available width ~24 chars (sidebar 28 - 2 padding - 2 border)
        total_width = 24
        left_len = left.cell_len
        right_len = right.cell_len
        gap = max(1, total_width - left_len - right_len)

        t = Text(no_wrap=True)
        t.append_text(left)
        t.append(" " * gap)
        t.append_text(right)
        return t

    def _quick_stats(self, snapshot: AppSnapshot, palette: ThemePalette | None) -> Text:
        p = palette
        s = snapshot.system
        yellow = p.warn if p else "#ffd060"
        cyan = p.secondary if p else "#00d4ff"
        text = p.text if p else "#c8d8e8"
        text2 = p.text_secondary if p else "#8aa0b0"

        t = Text(no_wrap=False)
        t.append("TCP: ", style=text2)
        t.append(str(s.tcp_count), style=f"bold {yellow}")
        t.append("   UDP: ", style=text2)
        t.append(str(s.udp_count), style=f"bold {cyan}")
        t.append("\nIPv4: ", style=text2)
        t.append(str(s.ipv4_count), style=text)
        t.append("  IPv6: ", style=text2)
        t.append(str(s.ipv6_count), style=text)
        return t

    def on__cat_btn_pressed(self, event: _CatBtn.Pressed) -> None:
        self.post_message(self.CategorySelected(self, event.cat_key))
