from __future__ import annotations

from rich.text import Text
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Static

from whosat.formatting import fmt_clock_epoch
from whosat.theme import ThemePalette
from whosat.types import AppSnapshot, UIState
from whosat.widgets.pill import Pill

_REFRESH_OPTIONS = [15, 30, 60, 120, 0]
_REFRESH_LABELS = {15: "15s", 30: "30s", 60: "1m", 120: "2m", 0: "off"}


class _Clickable(Static):
    """Static that posts Clicked with its widget id."""

    class Clicked(Message):
        def __init__(self, widget_id: str) -> None:
            self.widget_id = widget_id
            super().__init__()

    def on_click(self) -> None:
        self.post_message(self.Clicked(self.id or ""))


class HeaderBar(Horizontal):
    """Top bar: logo | pills | live dot | spacer | stats | refresh | clock."""

    class ScopeChanged(Message):
        def __init__(self, scope: str) -> None:
            self.scope = scope
            super().__init__()

    class RefreshIntervalChanged(Message):
        def __init__(self, seconds: int) -> None:
            self.seconds = seconds
            super().__init__()

    class RefreshRequested(Message):
        pass

    class MainViewChanged(Message):
        def __init__(self, view: str) -> None:
            self.view = view
            super().__init__()

    class StatClicked(Message):
        def __init__(self, stat: str) -> None:
            self.stat = stat
            super().__init__()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._blink_on = True
        self._current_scope = "all"
        self._current_main_view = "ports"
        self._refresh_idx = 1  # default 30s

    def compose(self):
        yield Static(id="hdr-logo")
        yield Pill("PORTS", variant="ports", id="hdr-view-ports")
        yield Pill("MEMORY", variant="memory", id="hdr-view-memory")
        yield Pill("SYS", variant="sys", id="hdr-sys-pill")
        yield Pill("DOCKER", variant="docker", id="hdr-docker-pill")
        yield Static(id="hdr-live")
        yield Static(id="hdr-spacer")
        yield _Clickable(id="hdr-ports", classes="stat-box")
        yield _Clickable(id="hdr-down", classes="stat-box")
        yield _Clickable(id="hdr-docker-stat", classes="stat-box")
        yield _Clickable(id="hdr-refresh-sel", classes="hdr-ctrl")
        yield _Clickable(id="hdr-refresh-btn", classes="hdr-ctrl")
        yield Static(id="hdr-clock")

    def on_mount(self) -> None:
        self.set_interval(0.8, self._toggle_blink)

    def _toggle_blink(self) -> None:
        self._blink_on = not self._blink_on

    # ── Pill clicks (scope pills) ──

    def on_pill_clicked(self, event: Pill.Clicked) -> None:
        pill_id = event.pill.id
        if pill_id == "hdr-view-ports":
            self.post_message(self.MainViewChanged("ports"))
        elif pill_id == "hdr-view-memory":
            self.post_message(self.MainViewChanged("memory"))
        elif pill_id == "hdr-sys-pill":
            new = "all" if self._current_scope == "sys" else "sys"
            self.post_message(self.ScopeChanged(new))
        elif pill_id == "hdr-docker-pill":
            new = "all" if self._current_scope == "docker" else "docker"
            self.post_message(self.ScopeChanged(new))

    # ── Stat / refresh / button clicks ──

    def on__clickable_clicked(self, event: _Clickable.Clicked) -> None:
        wid = event.widget_id
        if wid == "hdr-ports":
            self.post_message(self.StatClicked("ports"))
        elif wid == "hdr-down":
            self.post_message(self.StatClicked("down"))
        elif wid == "hdr-docker-stat":
            self.post_message(self.StatClicked("docker"))
        elif wid == "hdr-refresh-sel":
            self._refresh_idx = (self._refresh_idx + 1) % len(_REFRESH_OPTIONS)
            self.post_message(
                self.RefreshIntervalChanged(_REFRESH_OPTIONS[self._refresh_idx])
            )
        elif wid == "hdr-refresh-btn":
            self.post_message(self.RefreshRequested())

    # ── Render ──

    def update_view(
        self,
        snapshot: AppSnapshot | None,
        state: UIState,
        now_ts: float | None = None,
        palette: ThemePalette | None = None,
    ) -> None:
        p = palette
        accent = p.accent if p else "#00ff88"
        cyan = p.secondary if p else "#00d4ff"
        purple = p.docker if p else "#b084ff"
        yellow = p.warn if p else "#ffd060"
        text2 = p.text_secondary if p else "#8aa0b0"
        text3 = p.text_dim if p else "#5a6a7a"

        self._current_scope = state.scope
        self._current_main_view = state.main_view
        if state.refresh_interval_seconds in _REFRESH_OPTIONS:
            self._refresh_idx = _REFRESH_OPTIONS.index(state.refresh_interval_seconds)

        # ── Logo ──
        logo = Text(no_wrap=True)
        logo.append("⬡ ", style=f"bold {accent}")
        logo.append("WHOSAT", style=f"bold {accent}")
        self.query_one("#hdr-logo", Static).update(logo)

        # ── View pills (PORTS / MEMORY) ──
        for view_name in ("ports", "memory"):
            vpill = self.query_one(f"#hdr-view-{view_name}", Pill)
            if state.main_view == view_name:
                vpill.add_class("pill-active")
            else:
                vpill.remove_class("pill-active")

        # ── SYS pill — toggle active, dim when not on ports view ──
        sys_pill = self.query_one("#hdr-sys-pill", Pill)
        if state.main_view != "ports":
            sys_pill.remove_class("pill-active")
            sys_pill.add_class("pill-dimmed")
        else:
            sys_pill.remove_class("pill-dimmed")
            if state.scope == "sys":
                sys_pill.add_class("pill-active")
            else:
                sys_pill.remove_class("pill-active")

        # ── DOCKER pill — toggle active, dim when not on ports view ──
        dock_pill = self.query_one("#hdr-docker-pill", Pill)
        if state.main_view != "ports":
            dock_pill.remove_class("pill-active")
            dock_pill.add_class("pill-dimmed")
        else:
            dock_pill.remove_class("pill-dimmed")
            if state.scope == "docker":
                dock_pill.add_class("pill-active")
            else:
                dock_pill.remove_class("pill-active")

        # ── LIVE dot ──
        live = Text(no_wrap=True)
        if self._blink_on:
            live.append("●", style=f"bold {accent}")
        else:
            live.append("●", style=f"bold {text3}")
        live.append(" LIVE", style=text3)
        self.query_one("#hdr-live", Static).update(live)

        # ── Stats ──
        rows = snapshot.processes if snapshot else []
        down_n = sum(1 for r in rows if r.derived_status == "OFFLINE") if snapshot else 0
        docker_n = len(snapshot.containers) if snapshot else 0
        ports_n = len(rows)

        # PORTS
        pt = Text(no_wrap=True)
        pt.append("● ", style=f"bold {accent}")
        pt.append("PORTS ", style=text3)
        pt.append(str(ports_n), style=f"bold {accent}")
        self.query_one("#hdr-ports").update(pt)

        # DOWN
        dt = Text(no_wrap=True)
        if down_n > 0 and self._blink_on:
            dt.append("● ", style=f"bold {yellow}")
        elif down_n > 0:
            dt.append("● ", style=text3)
        else:
            dt.append("● ", style=f"bold {yellow}")
        dt.append("DOWN ", style=text3)
        dt.append(str(down_n), style=f"bold {yellow}")
        self.query_one("#hdr-down").update(dt)

        # DOCKER stat
        dk = Text(no_wrap=True)
        dk.append("● ", style=f"bold {purple}")
        dk.append("DOCKER ", style=text3)
        dk.append(str(docker_n), style=f"bold {purple}")
        self.query_one("#hdr-docker-stat").update(dk)

        # ── Refresh selector ──
        ref = _REFRESH_LABELS.get(
            state.refresh_interval_seconds, f"{state.refresh_interval_seconds}s"
        )
        rs = Text(no_wrap=True)
        rs.append("REFRESH ", style=text3)
        rs.append(f"{ref} ▾", style=text2)
        self.query_one("#hdr-refresh-sel").update(rs)

        # ── Refresh button ──
        rb = Text(no_wrap=True)
        rb.append("↻ ", style=text2)
        rb.append("REFRESH", style=text2)
        self.query_one("#hdr-refresh-btn").update(rb)

        # ── Clock ──
        clock = Text(no_wrap=True)
        if now_ts is not None:
            clock.append(fmt_clock_epoch(now_ts), style=text3)
        self.query_one("#hdr-clock").update(clock)
