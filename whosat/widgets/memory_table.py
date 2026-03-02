from __future__ import annotations

from rich.text import Text
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Button, Static

from whosat.formatting import fmt_bytes, fmt_percent
from whosat.theme import ThemePalette
from whosat.types import MemorySnapshot, UIState


# Column widths
_COL_NUM = 5     # row number
_COL_NAME = 22   # process name
_COL_USER = 12   # username
_COL_PID = 8     # pid
_COL_RSS = 10    # RSS
_COL_MPCT = 7    # %MEM
_COL_CPU = 7     # CPU%
_COL_THR = 8     # threads


def _bar_text(used: int, total: int, width: int, palette: ThemePalette | None,
              fill_color: str | None = None) -> Text:
    """Render a compact progress bar as Text."""
    t = Text(no_wrap=True)
    if total <= 0:
        t.append("░" * width, style="#3a4a5a")
        return t
    pct = min(used / total, 1.0)
    filled = int(pct * width)
    empty = width - filled
    fc = fill_color or (palette.accent if palette else "#00ff88")
    dim = palette.border if palette else "#3a4a5a"
    t.append("█" * filled, style=fc)
    t.append("░" * empty, style=dim)
    return t


class MemoryTable(Vertical):
    """All-process memory view with optional GPU section."""

    class ProcessSelected(Message):
        def __init__(self, pid: int) -> None:
            self.pid = pid
            super().__init__()

    def compose(self):
        yield Static(id="mem-summary")
        yield Static(id="mem-hdr-fixed")
        yield VerticalScroll(id="mem-scroll")

    def update_view(
        self,
        snapshot: MemorySnapshot | None,
        state: UIState,
        palette: ThemePalette | None = None,
    ) -> None:
        if snapshot is None:
            self.query_one("#mem-summary", Static).update("No memory data")
            self.query_one("#mem-hdr-fixed", Static).update("")
            scroll = self.query_one("#mem-scroll", VerticalScroll)
            scroll.remove_children()
            return

        p = palette
        accent = p.accent if p else "#00ff88"
        cyan = p.secondary if p else "#00d4ff"
        purple = p.docker if p else "#b084ff"
        yellow = p.warn if p else "#ffd060"
        text2 = p.text_secondary if p else "#8aa0b0"
        text3 = p.text_dim if p else "#5a6a7a"

        # ── Summary bar ──
        summary = Text(no_wrap=True)

        # RAM
        summary.append("  RAM ", style=f"bold {text3}")
        summary.append(fmt_bytes(snapshot.used_ram_bytes), style=f"bold {cyan}")
        summary.append(f" / {fmt_bytes(snapshot.total_ram_bytes)} ", style=text3)
        summary.append_text(_bar_text(snapshot.used_ram_bytes, snapshot.total_ram_bytes, 20, p, cyan))
        summary.append(f" {fmt_percent(snapshot.used_ram_bytes / snapshot.total_ram_bytes * 100 if snapshot.total_ram_bytes else 0)}", style=cyan)

        # Swap
        if snapshot.swap_total_bytes > 0:
            summary.append("   SWAP ", style=f"bold {text3}")
            summary.append(fmt_bytes(snapshot.swap_used_bytes), style=f"bold {purple}")
            summary.append(f" / {fmt_bytes(snapshot.swap_total_bytes)} ", style=text3)
            summary.append_text(_bar_text(snapshot.swap_used_bytes, snapshot.swap_total_bytes, 12, p, purple))

        # GPU
        for gpu in snapshot.gpus:
            summary.append(f"   GPU{gpu.index} ", style=f"bold {text3}")
            summary.append(fmt_bytes(gpu.memory_used_bytes), style=f"bold {yellow}")
            summary.append(f" / {fmt_bytes(gpu.memory_total_bytes)} ", style=text3)
            summary.append_text(_bar_text(gpu.memory_used_bytes, gpu.memory_total_bytes, 12, p, yellow))

        self.query_one("#mem-summary", Static).update(summary)

        # ── Table header ──
        hdr = Text(no_wrap=True)
        hdr.append("#".ljust(_COL_NUM), style=f"bold {text3}")
        hdr.append("NAME".ljust(_COL_NAME), style=f"bold {text3}")
        hdr.append("USER".ljust(_COL_USER), style=f"bold {text3}")
        hdr.append("PID".rjust(_COL_PID), style=f"bold {text3}")
        hdr.append("  ")
        hdr.append("RSS".rjust(_COL_RSS), style=f"bold {text3}")
        hdr.append("  ")
        hdr.append("%MEM".rjust(_COL_MPCT), style=f"bold {text3}")
        hdr.append("  ")
        hdr.append("CPU%".rjust(_COL_CPU), style=f"bold {text3}")
        hdr.append("  ")
        hdr.append("THREADS".rjust(_COL_THR), style=f"bold {text3}")
        self.query_one("#mem-hdr-fixed", Static).update(hdr)

        # ── Rows ──
        scroll = self.query_one("#mem-scroll", VerticalScroll)
        scroll.remove_children()

        search = state.memory_search_query.lower().strip()
        procs = snapshot.processes
        if search:
            procs = [pr for pr in procs if search in pr.name.lower()
                     or search in (pr.username or "").lower()
                     or search in str(pr.pid)]

        for idx, proc in enumerate(procs[:500], 1):
            row_text = Text(no_wrap=True)
            row_text.append(str(idx).ljust(_COL_NUM), style=text3)
            row_text.append(proc.name[:_COL_NAME - 1].ljust(_COL_NAME), style="bold" if idx <= 10 else "")
            row_text.append((proc.username or "-")[:_COL_USER - 1].ljust(_COL_USER), style=text3)
            row_text.append(str(proc.pid).rjust(_COL_PID), style=text2)
            row_text.append("  ")

            rss_str = fmt_bytes(proc.rss_bytes)
            # Color by magnitude
            if proc.rss_bytes > 1024 * 1024 * 1024:  # >1GB
                rss_color = f"bold {yellow}"
            elif proc.rss_bytes > 256 * 1024 * 1024:  # >256MB
                rss_color = f"bold {cyan}"
            else:
                rss_color = text2
            row_text.append(rss_str.rjust(_COL_RSS), style=rss_color)
            row_text.append("  ")

            pct = fmt_percent(proc.memory_percent)
            pct_color = yellow if proc.memory_percent > 10 else (cyan if proc.memory_percent > 2 else text2)
            row_text.append(pct.rjust(_COL_MPCT), style=pct_color)
            row_text.append("  ")

            cpu_str = fmt_percent(proc.cpu_percent)
            cpu_color = yellow if proc.cpu_percent > 50 else text2
            row_text.append(cpu_str.rjust(_COL_CPU), style=cpu_color)
            row_text.append("  ")

            row_text.append(str(proc.num_threads).rjust(_COL_THR), style=text3)

            btn = Button(id=f"mem-row-{idx}")
            btn.label = row_text
            btn._mem_pid = proc.pid
            if state.memory_selected_pid == proc.pid:
                btn.add_class("-primary")
            scroll.mount(btn)

        # GPU processes section
        if snapshot.gpu_available and snapshot.gpu_processes:
            gpu_hdr = Text(no_wrap=True)
            gpu_hdr.append("\n  GPU PROCESSES", style=f"bold {yellow}")
            gpu_hdr.append(f"  ({len(snapshot.gpu_processes)} processes)", style=text3)
            gpu_label = Static(gpu_hdr, classes="mem-gpu-header")
            scroll.mount(gpu_label)

            for gi, gp in enumerate(sorted(snapshot.gpu_processes, key=lambda g: g.gpu_memory_bytes, reverse=True)):
                gtext = Text(no_wrap=True)
                gtext.append("  GPU  ".ljust(_COL_NUM), style=f"bold {yellow}")
                gtext.append(gp.name[:_COL_NAME - 1].ljust(_COL_NAME), style="bold")
                gtext.append(" " * _COL_USER)
                gtext.append(str(gp.pid).rjust(_COL_PID), style=text2)
                gtext.append("  ")
                gtext.append(fmt_bytes(gp.gpu_memory_bytes).rjust(_COL_RSS), style=f"bold {yellow}")
                gbtn = Button(id=f"mem-gpu-{gi}")
                gbtn.label = gtext
                gbtn._mem_pid = gp.pid
                scroll.mount(gbtn)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid.startswith("mem-row-") or bid.startswith("mem-gpu-"):
            pid = getattr(event.button, "_mem_pid", None)
            if pid is not None:
                self.post_message(self.ProcessSelected(pid))
