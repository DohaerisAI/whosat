from __future__ import annotations

import datetime as _dt

from rich.text import Text
from textual.containers import Horizontal
from textual.widgets import Static

from whosat.formatting import fmt_bytes, fmt_percent, fmt_uptime
from whosat.theme import ThemePalette
from whosat.types import AppSnapshot

# Block chars from lowest to tallest (8 levels)
_VBLOCKS = " ▁▂▃▄▅▆▇█"

_MAX_SUB_LEN = 22  # truncate sub-info strings


class SysInfoItem(Static):
    """Vertical 3-line block: label, value, sub-info."""

    def __init__(self, item_id: str, **kwargs):
        super().__init__(id=f"si-{item_id}", **kwargs)

    def set_content(
        self,
        label: str,
        value: str | Text,
        sub: str | Text,
        val_color: str = "#c8d8e8",
        text3: str = "#5a6a7a",
    ) -> None:
        t = Text(no_wrap=True)
        t.append(label.upper(), style=text3)
        t.append("\n")
        if isinstance(value, Text):
            t.append_text(value)
        else:
            t.append(value, style=f"bold {val_color}")
        t.append("\n")
        if isinstance(sub, Text):
            t.append_text(sub)
        else:
            s = sub if len(sub) <= _MAX_SUB_LEN else sub[: _MAX_SUB_LEN - 1] + "\u2026"
            t.append(s, style=text3)
        self.update(t)


class SysInfoBar(Horizontal):
    """System info bar with 7 items separated by CSS border-right dividers."""

    def compose(self):
        yield SysInfoItem("hostname")
        yield SysInfoItem("cpu")
        yield SysInfoItem("memory")
        yield SysInfoItem("uptime")
        yield SysInfoItem("containers")
        yield SysInfoItem("processes")
        yield SysInfoItem("localip", classes="si-last")

    def update_view(
        self, snapshot: AppSnapshot | None, palette: ThemePalette | None = None
    ) -> None:
        p = palette
        if snapshot is None:
            return
        s = snapshot.system
        accent = p.accent if p else "#00ff88"
        cyan = p.secondary if p else "#00d4ff"
        purple = p.docker if p else "#b084ff"
        yellow = p.warn if p else "#ffd060"
        text = p.text if p else "#c8d8e8"
        text3 = p.text_dim if p else "#5a6a7a"

        # 1. HOSTNAME
        os_short = _shorten_os(s.os_version)
        self.query_one("#si-hostname", SysInfoItem).set_content(
            "HOSTNAME", s.hostname, os_short, val_color=accent, text3=text3,
        )

        # 2. CPU (cores + load combined)
        core_count = max(1, len(s.per_core_percent))
        cpu_color = yellow if s.cpu_percent > 30 else accent
        # Value line: "20 cores · 34%"
        cpu_val = Text(no_wrap=True)
        cpu_val.append(f"{core_count} cores", style=f"bold {cyan}")
        cpu_val.append(" \u00b7 ", style=text3)
        cpu_val.append(fmt_percent(s.cpu_percent), style=f"bold {cpu_color}")
        # Sub line: per-core bars
        core_bars = _per_core_bars(s.per_core_percent, p)
        self.query_one("#si-cpu", SysInfoItem).set_content(
            "CPU", cpu_val, core_bars, text3=text3,
        )

        # 3. MEMORY
        mem_bar = _gradient_mem_bar(s.memory_used_bytes, s.memory_total_bytes, p)
        mem_val = f"{fmt_bytes(s.memory_used_bytes)} / {fmt_bytes(s.memory_total_bytes)}"
        self.query_one("#si-memory", SysInfoItem).set_content(
            "MEMORY", mem_val, mem_bar, val_color=cyan, text3=text3,
        )

        # 4. UPTIME
        boot_dt = _dt.datetime.now() - _dt.timedelta(seconds=s.uptime_seconds)
        since = f"since {boot_dt.strftime('%b %d')}"
        self.query_one("#si-uptime", SysInfoItem).set_content(
            "UPTIME", fmt_uptime(s.uptime_seconds), since, val_color=accent, text3=text3,
        )

        # 5. CONTAINERS
        self.query_one("#si-containers", SysInfoItem).set_content(
            "CONTAINERS", f"{s.docker_running} running",
            f"{s.docker_stopped} stopped", val_color=purple, text3=text3,
        )

        # 6. PROCESSES
        self.query_one("#si-processes", SysInfoItem).set_content(
            "PROCESSES", str(s.total_processes),
            f"{s.processes_with_ports} w/ ports", val_color=text, text3=text3,
        )

        # 7. LOCAL IP
        primary_ip = s.local_ips[0] if s.local_ips else "-"
        ifaces = ", ".join(s.local_ips[1:3]) if len(s.local_ips) > 1 else "lo"
        self.query_one("#si-localip", SysInfoItem).set_content(
            "LOCAL IP", primary_ip, ifaces, val_color=cyan, text3=text3,
        )


# ── helpers ──────────────────────────────────────────────────────


def _shorten_os(os_version: str) -> str:
    """Abbreviate long OS strings to fit in the SysInfo bar."""
    v = os_version
    if "microsoft" in v.lower() and "WSL" in v:
        return "Linux WSL2"
    if "microsoft" in v.lower():
        return "Linux WSL"
    parts = v.split()
    if len(parts) >= 2 and parts[0] == "Linux":
        kern = parts[1].split("-")[0]
        segs = kern.split(".")
        short_kern = ".".join(segs[:2]) if len(segs) > 2 else kern
        return f"Linux {short_kern}"
    if len(v) > _MAX_SUB_LEN:
        return v[: _MAX_SUB_LEN - 1] + "\u2026"
    return v


def _per_core_bars(per_core: list[float], p: ThemePalette | None) -> Text:
    accent = p.accent if p else "#00ff88"
    yellow = p.warn if p else "#ffd060"
    red = p.danger if p else "#ff4466"
    vals = per_core if per_core else [0.0] * 4
    t = Text(no_wrap=True)
    for v in vals[:20]:
        idx = min(8, max(0, int(v / 100.0 * 8)))
        char = _VBLOCKS[idx] if idx > 0 else "\u2581"
        if v > 70:
            color = red
        elif v > 40:
            color = yellow
        else:
            color = accent
        t.append(char, style=color)
    return t


def _gradient_mem_bar(used: int, total: int, p: ThemePalette | None) -> Text:
    cyan = p.secondary if p else "#00d4ff"
    purple = p.docker if p else "#b084ff"
    bg3 = p.panel_alt if p else "#1a2030"
    total = max(1, total)
    ratio = min(1.0, max(0.0, used / total))
    bar_len = 12
    fill = int(bar_len * ratio)
    t = Text(no_wrap=True)
    for i in range(bar_len):
        if i < fill:
            if fill > 0 and i >= fill * 0.7:
                t.append("\u2588", style=purple)
            else:
                t.append("\u2588", style=cyan)
        else:
            t.append("\u2591", style=bg3)
    pct = f" {ratio * 100:.0f}%"
    t.append(pct, style=p.text_dim if p else "#5a6a7a")
    return t
