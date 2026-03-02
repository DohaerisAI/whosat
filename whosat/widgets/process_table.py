from __future__ import annotations

import time

from rich.table import Table
from rich.text import Text
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Button, Static

from whosat.constants import icon_for_process
from whosat.formatting import fmt_bytes, fmt_percent, fmt_uptime
from whosat.services.aggregator import build_groups
from whosat.theme import ThemePalette
from whosat.types import ProcessRecord, UIState

# ── Fixed column widths (shared between header and rows) ──
_COL_CHV = 3       # chevron
_COL_PORT = 7      # port number
_COL_GAP = 2       # gap between port and name
_COL_NAME = 20     # icon + name + optional tag (truncate with …)
_COL_IP = 16       # IP address
_COL_PROTO = 10    # protocol
_COL_STATUS = 10   # status badge
_COL_CPU = 16      # cpu/mem
_COL_UPTIME = 8    # uptime

# Framework/server detection: cmdline substring → display tag
_FRAMEWORK_TAGS: dict[str, str] = {
    "fastapi": "FastAPI",
    "uvicorn": "Uvicorn",
    "gunicorn": "Gunicorn",
    "flask": "Flask",
    "django": "Django",
    "celery": "Celery",
    "express": "Express",
    "next": "Next.js",
    "nuxt": "Nuxt",
    "nest": "NestJS",
    "spring": "Spring",
    "tomcat": "Tomcat",
    "rails": "Rails",
    "puma": "Puma",
    "sinatra": "Sinatra",
    "gin": "Gin",
    "fiber": "Fiber",
    "actix": "Actix",
    "rocket": "Rocket",
}


def _derive_tag(row: ProcessRecord) -> str | None:
    """Derive a meaningful tag for a process row, or None if nothing useful."""
    # Docker rows: use image name as tag
    if row.source == "docker" or row.docker_container_id:
        if row.docker_image:
            img = row.docker_image.split("/")[-1]  # strip registry prefix
            if len(img) > 14:
                img = img[:14]
            return img
        return "docker"

    # System rows: detect framework from cmdline
    cmdline = row.cmdline_text.lower()
    proc_name = (row.name or "").lower()
    for pattern, tag_name in _FRAMEWORK_TAGS.items():
        if pattern in cmdline and pattern not in proc_name:
            return tag_name

    return None


class ProcessTable(Vertical):
    class RowSelected(Message):
        def __init__(self, sender: "ProcessTable", row_key: str) -> None:
            self.row_key = row_key
            super().__init__()

    class GroupToggled(Message):
        def __init__(self, sender: "ProcessTable", group_key: str) -> None:
            self.group_key = group_key
            super().__init__()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._row_map: dict[str, ProcessRecord] = {}
        self._palette: ThemePalette | None = None
        self._state: UIState | None = None

    def compose(self):
        yield Static(id="table-hdr-fixed", classes="table-hdr")
        yield VerticalScroll(id="table-scroll")

    @property
    def row_map(self) -> dict[str, ProcessRecord]:
        return self._row_map

    def update_rows(self, rows: list[ProcessRecord], state: UIState, palette: ThemePalette | None = None) -> None:
        self._row_map = {r.row_key: r for r in rows}
        self._palette = palette
        self._state = state

        hdr = self.query_one("#table-hdr-fixed", Static)
        scroll = self.query_one("#table-scroll", VerticalScroll)

        saved_y = scroll.scroll_y
        scroll.remove_children()

        # Table header is always visible — prevents layout shift on expand/collapse
        hdr.update(self._table_header_text())

        if state.view_mode == "flat":
            for r in rows:
                self._mount_row(scroll, r, state.selected_row_key)
            if not rows:
                scroll.mount(Static("No processes match current filters.", classes="group-meta"))
            self._restore_scroll(scroll, state.selected_row_key, saved_y)
            return

        groups = build_groups(rows)
        if not groups:
            scroll.mount(Static("No processes match current filters.", classes="group-meta"))
            return

        # Sort groups by the order of their earliest row in the already-sorted list
        row_order = {r.row_key: i for i, r in enumerate(rows)}
        groups.sort(key=lambda g: min(row_order.get(r.row_key, 999) for r in g.rows))

        # Content width for right-aligning pills in group headers
        w = self.size.width
        content_width = max(80, w - 8) if w > 20 else 100

        for g in groups:
            collapsed = g.key not in state.expanded_groups
            btn = Button(
                self._group_header_label(g, collapsed, content_width),
                name=f"group-{g.key}",
                classes="group-btn",
            )
            scroll.mount(btn)
            if collapsed:
                continue
            for r in g.rows:
                self._mount_row(scroll, r, state.selected_row_key)

        self._restore_scroll(scroll, state.selected_row_key, saved_y)

    def _restore_scroll(self, scroll: VerticalScroll, selected_key: str | None, fallback_y: float) -> None:
        """After rebuild, restore scroll position immediately (no deferred callbacks)."""
        scroll.scroll_to(y=fallback_y, animate=False)

    # ── Table header (fixed at top, outside scroll) ──

    def _table_header_text(self) -> Text:
        p = self._palette
        text3 = p.text_dim if p else "#5a6a7a"
        cyan = p.secondary if p else "#00d4ff"

        t = Text(no_wrap=True)
        t.append(" " * _COL_CHV, style=text3)
        t.append(f"{'PORT':>{_COL_PORT}}", style=f"bold {cyan}")
        t.append(" " * _COL_GAP)
        t.append(f"{'NAME / CMD':<{_COL_NAME}}", style=f"bold {text3}")
        t.append(f"{'IP ADDRESS':<{_COL_IP}}", style=f"bold {text3}")
        t.append(f"{'PROTO':<{_COL_PROTO}}", style=f"bold {text3}")
        t.append(f"{'STATUS':<{_COL_STATUS}}", style=f"bold {text3}")
        t.append(f"{'CPU / MEM':<{_COL_CPU}}", style=f"bold {text3}")
        t.append(f"{'UPTIME':<{_COL_UPTIME}}", style=f"bold {text3}")
        return t

    # ── Group header (full-width, own layout, pills right-aligned) ──

    def _group_header_label(self, group, collapsed: bool, content_width: int) -> Text:
        p = self._palette
        accent = p.accent if p else "#00ff88"
        cyan = p.secondary if p else "#00d4ff"
        purple = p.docker if p else "#b084ff"
        yellow = p.warn if p else "#ffd060"
        red = p.danger if p else "#ff4466"
        text = p.text if p else "#c8d8e8"
        text2 = p.text_secondary if p else "#8aa0b0"
        text3 = p.text_dim if p else "#5a6a7a"

        # Left: chevron + icon + title
        left = Text(no_wrap=True)
        chevron = "\u25b6" if collapsed else "\u25bc"
        left.append(f" {chevron} ", style=text3)
        left.append(f"{group.icon} ")
        left.append(group.label, style=f"bold {text}")

        # Right: meta text + pills
        right = Text(no_wrap=True)

        ports_preview = ", ".join(
            str(r.min_port) for r in group.rows[:4] if r.min_port is not None
        )
        if len(group.rows) > 4:
            ports_preview += ", \u2026"
        meta = f"{len(group.rows)} processes"
        if ports_preview:
            meta += f" \u00b7 port {ports_preview}"
        right.append(meta, style=text2)
        right.append("  ")

        # Source pill
        src = "DOCKER" if group.source == "docker" else "SYS"
        if src == "DOCKER":
            right.append(f" {src} ", style=f"bold {purple} on #1e1c2e")
        else:
            right.append(f" {src} ", style=f"bold {cyan} on #0d1a22")
        right.append(" ")

        # Count pill
        right.append(f" {len(group.rows)} procs ", style=f"{text3} on #1a2030")
        right.append(" ")

        # Online pill
        right.append(f" {group.up_count} online ", style=f"bold {accent} on #12261b")

        if group.warn_count:
            right.append(" ")
            right.append(f" {group.warn_count} warn ", style=f"bold {yellow} on #2a2413")

        if group.down_count:
            right.append(" ")
            right.append(f" {group.down_count} down ", style=f"bold {red} on #2a141a")

        # Combine left + spacer + right (pills pushed to far right)
        left_len = left.cell_len
        right_len = right.cell_len
        spacer = max(2, content_width - left_len - right_len)

        t = Text(no_wrap=True)
        t.append_text(left)
        t.append(" " * spacer)
        t.append_text(right)
        return t

    # ── Process rows (follow column grid) ──

    def _mount_row(self, container, row: ProcessRecord, selected_row_key: str | None) -> None:
        safe_key = row.row_key.replace(":", "-")
        btn = Button(self._process_row_label(row), name=f"row-{safe_key}")
        btn.variant = "primary" if row.row_key == selected_row_key else "default"
        container.mount(btn)
        if self._state and row.row_key == self._state.selected_row_key:
            container.mount(Static(self._expanded_row_label(row), classes="expanded"))

    def _process_row_label(self, row: ProcessRecord) -> Text:
        p = self._palette
        accent = p.accent if p else "#00ff88"
        yellow = p.warn if p else "#ffd060"
        red = p.danger if p else "#ff4466"
        purple = p.docker if p else "#b084ff"
        text = p.text if p else "#c8d8e8"
        text2 = p.text_secondary if p else "#8aa0b0"
        text3 = p.text_dim if p else "#5a6a7a"

        port = str(row.min_port or "\u2014")
        icon = icon_for_process(row.name or "unknown")
        raw_name = row.name or "unknown"
        tag = _derive_tag(row)
        ip = (row.ports[0].ip if row.ports else "\u2014")[:14]
        proto = f"{row.ports[0].proto.upper()}/{row.ports[0].family.upper()}" if row.ports else "\u2014"
        status = row.derived_status
        status_color = {
            "ONLINE": accent,
            "WARN": yellow,
            "OFFLINE": red,
        }.get(status, text2)

        cpu_str = fmt_percent(row.cpu_percent)
        mem_str = fmt_bytes(row.memory_bytes)
        if cpu_str == "-" and mem_str == "-":
            cpu_mem = "\u2014"
        else:
            cpu_mem = f"{cpu_str}/{mem_str}"
        uptime = fmt_uptime(time.time() - row.create_time) if row.create_time else "\u2014"

        t = Text(no_wrap=True)

        # Chevron (3 chars)
        t.append(" \u25b6 ", style=text3)

        # Port (7 chars, right-aligned)
        t.append(f"{port:>{_COL_PORT}}", style=f"bold {yellow}")

        # Gap (2 chars)
        t.append(" " * _COL_GAP)

        # Name column (20 visual cells): icon(2) + space(1) + name + optional tag + padding
        # Text budget after icon+space: 17 chars
        name_budget = _COL_NAME - 3
        if tag:
            tag_display = f" {tag}"
            max_name_len = name_budget - len(tag_display)
            if max_name_len < 4:
                # Tag too long for column, drop it
                name = raw_name[:name_budget] if len(raw_name) <= name_budget else raw_name[: name_budget - 1] + "\u2026"
                tag_display = ""
            else:
                name = raw_name[:max_name_len] if len(raw_name) <= max_name_len else raw_name[: max_name_len - 1] + "\u2026"
        else:
            name = raw_name[:name_budget] if len(raw_name) <= name_budget else raw_name[: name_budget - 1] + "\u2026"
            tag_display = ""

        t.append(f"{icon} ", style=text2)
        t.append(name, style=text)
        if tag_display:
            is_docker = row.source == "docker" or row.docker_container_id is not None
            tag_style = f"{purple} on #1e1c2e" if is_docker else f"{text3} on #1a2030"
            t.append(tag_display, style=tag_style)

        # Pad to _COL_NAME: 3 (icon+space) + len(name) + len(tag_display) + pad = 20
        used = 3 + len(name) + len(tag_display)
        pad = max(0, _COL_NAME - used)
        t.append(" " * pad)

        # IP (16 chars)
        t.append(f"{ip:<{_COL_IP}}", style=text3)

        # Proto (10 chars)
        t.append(f"{proto:<{_COL_PROTO}}", style=text3)

        # Status (10 chars): dot(1) + space(1) + text(8) = 10
        t.append("\u25cf ", style=f"bold {status_color}")
        t.append(f"{status:<{_COL_STATUS - 2}}", style=f"bold {status_color}")

        # CPU/MEM (16 chars)
        t.append(f"{cpu_mem:<{_COL_CPU}}", style=text2)

        # Uptime (8 chars)
        t.append(f"{uptime:<{_COL_UPTIME}}", style=text3)

        return t

    # ── Expanded detail (full-width, 3-column grid, not column-aligned) ──

    def _expanded_row_label(self, row: ProcessRecord) -> Text:
        p = self._palette
        cyan = p.secondary if p else "#00d4ff"
        yellow = p.warn if p else "#ffd060"
        text2 = p.text_secondary if p else "#8aa0b0"
        text3 = p.text_dim if p else "#5a6a7a"

        grid = Table.grid(expand=True, padding=(0, 2))
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)

        # Column 1: OPEN PORTS
        col1 = Text(no_wrap=False)
        col1.append("OPEN PORTS\n", style=f"bold {text3}")
        if row.ports:
            for pt in row.ports[:6]:
                if pt.proto == "udp":
                    col1.append(f" {pt.port} UDP ", style=f"bold {cyan} on #0d1a22")
                else:
                    col1.append(f" {pt.port} TCP ", style=f"bold {yellow} on #2a2413")
                col1.append("  ")
        else:
            col1.append("\u2014", style=text3)

        # Column 2: PROCESS INFO
        col2 = Text(no_wrap=False)
        col2.append("PROCESS INFO\n", style=f"bold {text3}")
        col2.append("PID    ", style=text3)
        col2.append(f"{row.pid or '\u2014'}\n", style=f"bold {cyan}")
        col2.append("User   ", style=text3)
        col2.append(f"{row.username or '\u2014'}\n", style=text2)
        col2.append("Cmd    ", style=text3)
        cmd_text = (row.cmdline_text or row.exe or "\u2014")[:40]
        col2.append(cmd_text, style=text2)

        # Column 3: NETWORK
        col3 = Text(no_wrap=False)
        col3.append("NETWORK\n", style=f"bold {text3}")
        col3.append("Conns  ", style=text3)
        col3.append("\u2014\n", style=text2)
        col3.append("RX/TX  ", style=text3)
        col3.append("\u2014\n", style=text2)
        col3.append("Bind   ", style=text3)
        bind = f"{row.ports[0].ip}:{row.ports[0].port}" if row.ports else "\u2014"
        col3.append(bind, style=f"bold {cyan}")

        grid.add_row(col1, col2, col3)
        return grid

    # ── Event handling ──

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.name or ""
        if bid.startswith("row-"):
            raw = bid.split("-", 1)[1]
            if raw.startswith("pid-"):
                row_key = raw.replace("pid-", "pid:", 1)
            elif raw.startswith("docker-"):
                row_key = raw.replace("docker-", "docker:", 1)
            else:
                row_key = raw
            self.post_message(self.RowSelected(self, row_key))
        elif bid.startswith("group-"):
            self.post_message(self.GroupToggled(self, bid.split("-", 1)[1]))
