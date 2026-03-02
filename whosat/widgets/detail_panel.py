from __future__ import annotations

import time

from rich.console import Group
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Button, Static

from whosat.formatting import fmt_bytes, fmt_percent, fmt_uptime
from whosat.services.path_display import get_display_path
from whosat.theme import ThemePalette
from whosat.types import ProcessRecord


class DetailPanel(Vertical):
    class ActionRequested(Message):
        def __init__(self, sender: "DetailPanel", action: str) -> None:
            self.action = action
            super().__init__()

    class KillRequested(Message):
        def __init__(self, sender: "DetailPanel", row_key: str) -> None:
            self.row_key = row_key
            super().__init__()

    class CloseRequested(Message):
        pass

    def compose(self):
        with Horizontal(id="detail-header"):
            yield Static("", id="detail-title")
            yield Button("\u2715 close", id="close-btn")
        with VerticalScroll(id="detail-body"):
            yield Static("Select a process", id="detail-info")
        with Horizontal(id="action-row-1"):
            yield Button("PING", id="ping-btn")
            yield Button("CURL", id="curl-btn")
            yield Button("COPY IP:PORT", id="copy-ip-port-btn")
        yield Button("KILL", id="kill-btn", variant="error")

    def update_view(self, row: ProcessRecord | None, palette: ThemePalette | None = None) -> None:
        info = self.query_one("#detail-info", Static)
        title = self.query_one("#detail-title", Static)
        kill = self.query_one("#kill-btn", Button)
        ping = self.query_one("#ping-btn", Button)
        curl = self.query_one("#curl-btn", Button)
        copy_ip_port = self.query_one("#copy-ip-port-btn", Button)

        if row is None:
            title.update("")
            info.update("Select a process")
            kill.disabled = True
            ping.disabled = True
            curl.disabled = True
            copy_ip_port.disabled = True
            return

        kill.disabled = row.pid is None
        has_port = bool(row.ports)
        ping.disabled = not has_port
        curl.disabled = not has_port
        copy_ip_port.disabled = not has_port

        p = palette
        title.update(self._header_line(row, palette))
        info.update(self._render_detail(row, palette))

    def _render_detail(self, row: ProcessRecord, palette: ThemePalette | None):
        p = palette
        sections: list = []

        sections.append(Rule(style=p.border if p else "#1e2a38"))

        # STATUS section
        sections.append(self._section_title("STATUS", palette))
        status = row.derived_status
        dot_color = {
            "ONLINE": p.accent if p else "#00ff88",
            "WARN": p.warn if p else "#ffd060",
            "OFFLINE": p.danger if p else "#ff4466",
        }.get(status, p.text_secondary if p else "#8aa0b0")
        sections.append(self._kv_block([
            ("State", f"\u25cf {status}"),
            ("Uptime", fmt_uptime(time.time() - row.create_time) if row.create_time else "-"),
            ("Restarts", "0"),
            ("Last check", "2s ago"),
        ], palette, highlights={"State": dot_color, "Uptime": p.secondary if p else "#00d4ff"}))

        # NETWORK section
        sections.append(self._section_title("NETWORK", palette))
        bind = f"{row.ports[0].ip}:{row.ports[0].port}" if row.ports else "\u2014"
        proto = f"{row.ports[0].proto.upper()}/{row.ports[0].family.upper()}" if row.ports else "\u2014"
        sections.append(self._kv_block([
            ("Bind", bind),
            ("Local IP", row.ports[0].ip if row.ports else "-"),
            ("Protocol", proto),
            ("Connections", "\u2014"),
            ("RX / TX", "\u2014"),
        ], palette, highlights={"Bind": p.secondary if p else "#00d4ff", "Connections": p.secondary if p else "#00d4ff"}))

        # ALL OPEN PORTS section
        sections.append(self._section_title("ALL OPEN PORTS", palette))
        sections.append(self._ports_line(row, palette))

        # RESOURCES section
        sections.append(self._section_title("RESOURCES", palette))
        sections.append(self._kv_block([
            ("CPU", fmt_percent(row.cpu_percent)),
            ("Memory", f"{fmt_bytes(row.memory_bytes)} ({fmt_percent(row.memory_percent)})"),
            ("Threads", str(row.threads or "-")),
            ("FDs", str(row.fd_count or "-")),
        ], palette, highlights={"CPU": p.secondary if p else "#00d4ff", "Memory": p.secondary if p else "#00d4ff"}))

        # PATH section
        sections.append(self._section_title("PATH", palette))
        sections.append(self._wrapped_text(get_display_path(row) or "\u2014", palette))

        # CMD section
        sections.append(self._section_title("CMD", palette))
        sections.append(self._wrapped_text(row.cmdline_text or row.exe or "\u2014", palette, dim=True))

        return Group(*sections)

    def _header_line(self, row: ProcessRecord, palette: ThemePalette | None) -> Text:
        p = palette
        accent = p.accent if p else "#00ff88"
        yellow = p.warn if p else "#ffd060"
        red = p.danger if p else "#ff4466"
        text = p.text if p else "#c8d8e8"
        text2 = p.text_secondary if p else "#8aa0b0"

        source = "docker" if (row.source == "docker" or row.docker_container_id) else "sys"
        status = row.derived_status
        dot_color = {"ONLINE": accent, "WARN": yellow, "OFFLINE": red}.get(status, text2)

        t = Text(no_wrap=False)
        t.append(row.name or "process", style=f"bold {text}")
        t.append(f"  pid {row.pid if row.pid is not None else '-'}", style=text2)
        t.append("  \u25cf ", style=f"bold {dot_color}")
        t.append(status, style=f"bold {dot_color}")
        t.append(f"  {source}", style=text2)
        return t

    def _section_title(self, title: str, palette: ThemePalette | None) -> Text:
        p = palette
        text3 = p.text_dim if p else "#5a6a7a"
        border = p.border if p else "#1e2a38"
        t = Text(no_wrap=False)
        t.append(title, style=f"bold {text3}")
        t.append("\n")
        t.append("\u2500" * 30, style=border)
        return t

    def _kv_block(self, rows: list[tuple[str, str]], palette: ThemePalette | None, highlights: dict[str, str] | None = None):
        p = palette
        text3 = p.text_dim if p else "#5a6a7a"
        text2 = p.text_secondary if p else "#8aa0b0"
        highlights = highlights or {}

        tbl = Table.grid(expand=True, padding=(0, 1))
        tbl.add_column(width=12, style=text3)
        tbl.add_column(ratio=1, style=text2)
        for k, v in rows:
            val_style = highlights.get(k, text2)
            tbl.add_row(
                Text(k, style=text3),
                Text(v, style=val_style),
            )
        return tbl

    def _wrapped_text(self, text_value: str, palette: ThemePalette | None, dim: bool = False) -> Text:
        p = palette
        style = p.text_dim if p and dim else (p.text_secondary if p else "#8aa0b0")
        return Text(text_value, style=style, no_wrap=False, overflow="fold")

    def _ports_line(self, row: ProcessRecord, palette: ThemePalette | None) -> Text:
        p = palette
        cyan = p.secondary if p else "#00d4ff"
        yellow = p.warn if p else "#ffd060"
        text3 = p.text_dim if p else "#5a6a7a"
        t = Text(no_wrap=False)
        if not row.ports:
            t.append("\u2014", style=text3)
            return t
        for idx, port in enumerate(row.ports[:12]):
            if idx:
                t.append("  ")
            if port.proto == "udp":
                t.append(f" {port.port} UDP ", style=f"bold {cyan} on #0d1a22")
            else:
                t.append(f" {port.port} TCP ", style=f"bold {yellow} on #2a2413")
        return t

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "close-btn":
            self.post_message(self.CloseRequested())
        elif bid == "kill-btn":
            self.post_message(self.KillRequested(self, "selected"))
        elif bid == "ping-btn":
            self.post_message(self.ActionRequested(self, "ping"))
        elif bid == "curl-btn":
            self.post_message(self.ActionRequested(self, "curl"))
        elif bid == "copy-ip-port-btn":
            self.post_message(self.ActionRequested(self, "copy_ip_port"))
