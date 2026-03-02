from __future__ import annotations

import time
from dataclasses import replace

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Static

from whosat import __version__
from whosat.config import WhosatConfig, load_config, save_config
from whosat.services.actions import can_kill, send_kill, terminate_then_check
from whosat.services.clipboard import copy_text
from whosat.services.aggregator import build_categories, build_groups, normalized_group_name
from whosat.services.filters import apply_filters
from whosat.services.path_display import get_display_path
from whosat.services.refresh import RefreshConfig, collect_snapshot, make_empty_system
from whosat.types import AppSnapshot, ProcessRecord, UIState
from whosat.theme import ThemePalette, get_theme, next_theme_name
from whosat.widgets.confirm_modal import ConfirmKillModal
from whosat.widgets.command_modal import CommandOutputModal
from whosat.widgets.detail_panel import DetailPanel
from whosat.widgets.footer_bar import FooterBar
from whosat.widgets.header_bar import HeaderBar
from whosat.widgets.memory_table import MemoryTable
from whosat.widgets.process_table import ProcessTable
from whosat.widgets.sidebar import Sidebar
from whosat.widgets.sys_info_bar import SysInfoBar
from whosat.widgets.toolbar import Toolbar


class WhosatApp(App):
    CSS_PATH = "styles/whosat.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("/", "focus_search", "Search"),
        ("r", "refresh_now", "Refresh"),
        ("g", "toggle_view", "View"),
        ("t", "cycle_theme", "Theme"),
        ("e", "toggle_path_expand", "Expand Path"),
        ("y", "copy_path", "Copy Path"),
        ("k", "kill_selected", "Kill"),
        ("d", "toggle_detail", "Detail"),
        ("up", "cursor_up", "Up"),
        ("down", "cursor_down", "Down"),
        ("enter", "activate_selected", "Select"),
        ("escape", "escape_action", "Escape"),
        ("1", "switch_view_ports", "Ports"),
        ("2", "switch_view_memory", "Memory"),
    ]

    tick = reactive(0)

    def __init__(self, docker_enabled: bool = True, debug: bool = False):
        super().__init__()
        self.debug_mode = debug
        self.config_data: WhosatConfig = load_config()
        self.theme_palette: ThemePalette = get_theme(self.config_data.theme)
        self.ui_state = UIState(docker_enabled=docker_enabled, selected_category="all", detail_open=True)
        self.snapshot: AppSnapshot | None = None
        self.filtered_rows: list[ProcessRecord] = []
        self.status_message = ""
        self.status_message_until: float | None = None
        self._sudo_hint_shown = False
        self._last_refresh_started = 0.0

    def compose(self) -> ComposeResult:
        yield HeaderBar(id="header-bar")
        yield SysInfoBar(id="sys-info")
        yield Toolbar(id="toolbar")
        with Horizontal(id="main-shell"):
            yield Sidebar(id="sidebar")
            yield ProcessTable(id="process-table")
            yield MemoryTable(id="memory-table")
            yield DetailPanel(id="detail-panel")
        yield FooterBar(id="footer-bar")

    def on_mount(self) -> None:
        self.title = "whosat"
        self.sub_title = "ports / processes / docker"
        self._apply_theme()
        self._sync_view_visibility()
        self.set_interval(1, self._on_second_tick)
        self.refresh_data()
        self._sync_controls()

    def _on_second_tick(self) -> None:
        self.tick += 1
        self._update_countdown()
        self._render_tick_only()
        if self._modal_pauses_refresh():
            return
        if self.ui_state.refresh_interval_seconds > 0 and self.ui_state.next_refresh_eta == 0:
            self.refresh_data()

    def _update_countdown(self) -> None:
        if self.ui_state.refresh_interval_seconds <= 0:
            self.ui_state.next_refresh_eta = None
            return
        if not self._last_refresh_started:
            self.ui_state.next_refresh_eta = self.ui_state.refresh_interval_seconds
            return
        elapsed = int(time.time() - self._last_refresh_started)
        remaining = max(0, self.ui_state.refresh_interval_seconds - elapsed)
        self.ui_state.next_refresh_eta = remaining

    def refresh_data(self) -> None:
        if self.ui_state.refresh_in_progress:
            self.set_status_message("refresh skipped (already running)")
            return
        self.ui_state.refresh_in_progress = True
        self._last_refresh_started = time.time()
        try:
            self.snapshot = collect_snapshot(RefreshConfig(
                docker_enabled=self.ui_state.docker_enabled,
                collect_memory=(self.ui_state.main_view == "memory"),
            ))
            if self.snapshot.errors:
                errors = list(self.snapshot.errors)
                sudo_hint = "Run with sudo for full process details: sudo whosat"
                if sudo_hint in errors and self._sudo_hint_shown:
                    errors = [e for e in errors if e != sudo_hint]
                elif sudo_hint in errors:
                    self._sudo_hint_shown = True
                if errors:
                    self.set_status_message("; ".join(errors[:2]), ttl_seconds=4.0)
                else:
                    self.status_message = ""
                    self.status_message_until = None
            else:
                self.status_message = ""
                self.status_message_until = None
            self._ensure_selection_valid()
            self._recompute_visible_rows()
        except Exception as exc:  # pragma: no cover
            self.set_status_message(f"refresh failed: {exc}", ttl_seconds=4.0)
            if self.snapshot is None:
                self.snapshot = AppSnapshot(system=make_empty_system(), processes=[], containers=[], collected_at=time.time())
        finally:
            self.ui_state.refresh_in_progress = False
            self._update_countdown()
            self._render_all()
            self._sync_controls()

    def _ensure_selection_valid(self) -> None:
        if self.snapshot is None:
            self.ui_state.selected_row_key = None
            return
        rows = self.snapshot.processes
        if not rows:
            self.ui_state.selected_row_key = None
            return
        if self.ui_state.selected_row_key and any(r.row_key == self.ui_state.selected_row_key for r in rows):
            return
        self.ui_state.selected_row_key = rows[0].row_key

    def _recompute_visible_rows(self) -> None:
        if self.snapshot is None:
            self.filtered_rows = []
            return
        self.filtered_rows = apply_filters(
            self.snapshot.processes,
            search_query=self.ui_state.search_query,
            scope=self.ui_state.scope,
            category_key=self.ui_state.selected_category,
            sort_by=self.ui_state.sort_by,
            sort_order=self.ui_state.sort_order,
        )
        if self.filtered_rows:
            keys = {r.row_key for r in self.filtered_rows}
            if self.ui_state.selected_row_key not in keys:
                self.ui_state.selected_row_key = self.filtered_rows[0].row_key
        else:
            self.ui_state.selected_row_key = None

    def _selected_row(self) -> ProcessRecord | None:
        if not self.ui_state.selected_row_key:
            return None
        for r in self.filtered_rows:
            if r.row_key == self.ui_state.selected_row_key:
                return r
        return None

    def _render_all(self) -> None:
        self.query_one(HeaderBar).update_view(self.snapshot, self.ui_state, time.time(), self.theme_palette)
        self.query_one(SysInfoBar).update_view(self.snapshot, self.theme_palette)

        view = self.ui_state.main_view

        if view == "ports":
            if self.snapshot:
                cats = build_categories(self.snapshot.processes)
            else:
                cats = []
            self.query_one(Sidebar).update_categories(cats, self.ui_state.selected_category, self.snapshot, self.theme_palette)
            self.query_one(ProcessTable).update_rows(self.filtered_rows, self.ui_state, self.theme_palette)
            detail = self.query_one(DetailPanel)
            detail.display = self.ui_state.detail_open
            detail.update_view(self._selected_row() if self.ui_state.detail_open else None, self.theme_palette)
        elif view == "memory":
            mem_snap = self.snapshot.memory if self.snapshot else None
            self.query_one(MemoryTable).update_view(mem_snap, self.ui_state, self.theme_palette)
            detail = self.query_one(DetailPanel)
            detail.display = False
        self.query_one(FooterBar).update_view(self.ui_state, __version__, self._active_status_message(), self.theme_palette)

    def _render_tick_only(self) -> None:
        self.query_one(HeaderBar).update_view(self.snapshot, self.ui_state, time.time(), self.theme_palette)
        self.query_one(FooterBar).update_view(self.ui_state, __version__, self._active_status_message(), self.theme_palette)

    def _sync_controls(self) -> None:
        self.query_one(Toolbar).sync_from_state(self.ui_state)

    def _sync_view_visibility(self) -> None:
        view = self.ui_state.main_view
        self.query_one(ProcessTable).display = (view == "ports")
        self.query_one(MemoryTable).display = (view == "memory")
        self.query_one(Sidebar).display = (view == "ports")

    def _switch_main_view(self, view: str) -> None:
        if view == self.ui_state.main_view:
            return
        self.ui_state.main_view = view
        self._sync_view_visibility()
        # Trigger data collection for the new view
        self.refresh_data()

    def _mutate_state(self, **kwargs) -> None:
        self.ui_state = replace(self.ui_state, **kwargs)
        self._recompute_visible_rows()
        self._render_all()
        self._sync_controls()

    def on_toolbar_state_changed(self, event: Toolbar.StateChanged) -> None:
        key = event.key
        value = event.value
        if key == "refresh_interval_seconds":
            self._mutate_state(refresh_interval_seconds=int(value))
            self._last_refresh_started = time.time()
            self._update_countdown()
            return
        if key == "search_query":
            view = self.ui_state.main_view
            if view == "memory":
                self._mutate_state(memory_search_query=str(value))
            else:
                self._mutate_state(search_query=str(value))
            return
        if key in {"scope", "sort_by", "sort_order", "view_mode"}:
            self._mutate_state(**{key: value})

    def on_toolbar_refresh_requested(self, _: Toolbar.RefreshRequested) -> None:
        self.refresh_data()

    def on_sidebar_category_selected(self, event: Sidebar.CategorySelected) -> None:
        self._mutate_state(selected_category=event.category_key)

    def on_process_table_row_selected(self, event: ProcessTable.RowSelected) -> None:
        self._mutate_state(selected_row_key=event.row_key, detail_open=True, expanded_paths=set())

    def on_process_table_group_toggled(self, event: ProcessTable.GroupToggled) -> None:
        expanded = set(self.ui_state.expanded_groups)
        if event.group_key in expanded:
            expanded.remove(event.group_key)
        else:
            expanded.add(event.group_key)
        self._mutate_state(expanded_groups=expanded)

    # ── HeaderBar events ──

    def on_header_bar_main_view_changed(self, event: HeaderBar.MainViewChanged) -> None:
        self._switch_main_view(event.view)

    def on_header_bar_scope_changed(self, event: HeaderBar.ScopeChanged) -> None:
        self._mutate_state(scope=event.scope)

    def on_header_bar_refresh_interval_changed(self, event: HeaderBar.RefreshIntervalChanged) -> None:
        self._mutate_state(refresh_interval_seconds=event.seconds)
        self._last_refresh_started = time.time()
        self._update_countdown()

    def on_header_bar_refresh_requested(self, _: HeaderBar.RefreshRequested) -> None:
        self.refresh_data()

    def on_header_bar_stat_clicked(self, event: HeaderBar.StatClicked) -> None:
        if event.stat == "ports":
            self._mutate_state(scope="all", search_query="")
        elif event.stat == "down":
            self._mutate_state(search_query="OFFLINE")
        elif event.stat == "docker":
            self._mutate_state(scope="docker")

    def on_detail_panel_kill_requested(self, _: DetailPanel.KillRequested) -> None:
        self.action_kill_selected()

    def on_detail_panel_close_requested(self, _: DetailPanel.CloseRequested) -> None:
        self._mutate_state(detail_open=False)

    # ── MemoryTable events ──

    def on_memory_table_process_selected(self, event: MemoryTable.ProcessSelected) -> None:
        self.ui_state.memory_selected_pid = event.pid
        self._render_all()

    def on_detail_panel_action_requested(self, event: DetailPanel.ActionRequested) -> None:
        if event.action == "ping":
            self.action_ping_selected()
        elif event.action == "curl":
            self.action_curl_selected()
        elif event.action == "copy_ip_port":
            self.action_copy_ip_port_selected()

    def action_focus_search(self) -> None:
        self.query_one("#search").focus()

    def action_refresh_now(self) -> None:
        self.refresh_data()

    def action_toggle_view(self) -> None:
        nxt = "flat" if self.ui_state.view_mode == "group" else "group"
        self._mutate_state(view_mode=nxt)

    def action_cycle_theme(self) -> None:
        nxt = next_theme_name(self.theme_palette.name)
        self.theme_palette = get_theme(nxt)
        self.config_data.theme = nxt
        try:
            save_config(self.config_data)
            self.set_status_message(f"Theme: {nxt} (saved)")
        except Exception:
            self.set_status_message(f"Theme: {nxt}")
        self._apply_theme()
        self._render_all()

    def action_toggle_detail(self) -> None:
        self._mutate_state(detail_open=not self.ui_state.detail_open)

    def action_toggle_path_expand(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        full_path = get_display_path(row)
        if not full_path:
            self.set_status_message("No path available")
            self._render_tick_only()
            return
        expanded = set(self.ui_state.expanded_paths)
        if row.row_key in expanded:
            expanded.remove(row.row_key)
        else:
            expanded = {row.row_key}
        self._mutate_state(expanded_paths=expanded)

    def action_copy_path(self) -> None:
        row = self._selected_row()
        if row is None:
            self.set_status_message("No row selected")
            self._render_tick_only()
            return
        _ok, msg = copy_text(get_display_path(row) or "")
        self.set_status_message(msg)
        self._render_tick_only()

    def action_ping_selected(self) -> None:
        row = self._selected_row()
        target = self._row_host_port(row)
        if row is None or target is None:
            self.set_status_message("No host/port selected")
            self._render_tick_only()
            return
        host, _port = target
        self.push_screen(CommandOutputModal(f"PING {host}", ["ping", "-c", "4", host], timeout=12))

    def action_curl_selected(self) -> None:
        row = self._selected_row()
        target = self._row_host_port(row)
        if row is None or target is None:
            self.set_status_message("No host/port selected")
            self._render_tick_only()
            return
        host, port = target
        url = f"http://{host}:{port}"
        self.push_screen(CommandOutputModal(f"CURL {url}", ["curl", "-v", "--max-time", "5", url], timeout=10))

    def action_copy_ip_port_selected(self) -> None:
        row = self._selected_row()
        target = self._row_host_port(row)
        if row is None or target is None:
            self.set_status_message("No host/port selected")
            self._render_tick_only()
            return
        host, port = target
        _ok, msg = copy_text(f"{host}:{port}")
        if msg.startswith("Copied via"):
            self.set_status_message(f"Copied {host}:{port}")
        else:
            self.set_status_message(msg)
        self._render_tick_only()

    def action_cursor_up(self) -> None:
        if not self.filtered_rows:
            return
        keys = [r.row_key for r in self.filtered_rows]
        cur = self.ui_state.selected_row_key or keys[0]
        idx = keys.index(cur) if cur in keys else 0
        self._mutate_state(selected_row_key=keys[max(0, idx - 1)], expanded_paths=set())

    def action_cursor_down(self) -> None:
        if not self.filtered_rows:
            return
        keys = [r.row_key for r in self.filtered_rows]
        cur = self.ui_state.selected_row_key or keys[0]
        idx = keys.index(cur) if cur in keys else 0
        self._mutate_state(selected_row_key=keys[min(len(keys) - 1, idx + 1)], expanded_paths=set())

    def action_activate_selected(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        group_key = normalized_group_name(row)
        if self.ui_state.view_mode == "group":
            expanded = set(self.ui_state.expanded_groups)
            if group_key not in expanded:
                expanded.add(group_key)
                self._mutate_state(expanded_groups=expanded)
        self._mutate_state(detail_open=True)

    def action_escape_action(self) -> None:
        try:
            if isinstance(self.screen, (ConfirmKillModal, CommandOutputModal)):
                self.pop_screen()
                return
        except Exception:
            pass
        if self.ui_state.detail_open:
            self._mutate_state(detail_open=False)
            return
        try:
            self.query_one("#search").blur()
        except Exception:
            pass

    def action_switch_view_ports(self) -> None:
        self._switch_main_view("ports")

    def action_switch_view_memory(self) -> None:
        self._switch_main_view("memory")

    def action_kill_selected(self) -> None:
        row = self._selected_row()
        if row is None or not can_kill(row):
            self.set_status_message("No killable process selected")
            self._render_all()
            return

        def _after(choice: tuple[str, int | None] | None) -> None:
            if not choice:
                self.set_status_message("Kill canceled")
                self._render_all()
                return
            action, pid = choice
            if pid is None:
                self.set_status_message("No PID to kill")
                self._render_all()
                return
            if action == "term":
                result = terminate_then_check(pid)
                self.set_status_message(result.message, ttl_seconds=4.0)
                if result.still_running:
                    force = send_kill(pid)
                    if force.ok:
                        self.set_status_message("SIGKILL sent after SIGTERM grace", ttl_seconds=4.0)
                    else:
                        self.set_status_message(force.message, ttl_seconds=4.0)
                self.refresh_data()

        self.push_screen(ConfirmKillModal(row), _after)

    def get_current_group_key(self) -> str | None:
        row = self._selected_row()
        if row is None:
            return None
        for group in build_groups(self.filtered_rows):
            if any(r.row_key == row.row_key for r in group.rows):
                return group.key
        return None

    def _apply_theme(self) -> None:
        p = self.theme_palette
        self.screen.styles.background = p.bg
        # Widgets that get panel bg + border
        for selector in (SysInfoBar, FooterBar, Sidebar, ProcessTable, DetailPanel, MemoryTable):
            try:
                widget = self.query_one(selector)
                widget.styles.background = p.panel
            except Exception:
                continue
        # HeaderBar: just bg, no border override (handled by TCSS)
        try:
            self.query_one(HeaderBar).styles.background = p.panel
        except Exception:
            pass

    def set_status_message(self, msg: str, ttl_seconds: float = 3.0) -> None:
        self.status_message = msg
        self.status_message_until = time.time() + ttl_seconds if msg else None

    def _active_status_message(self) -> str:
        if not self.status_message:
            return ""
        if self.status_message_until is None:
            return self.status_message
        if time.time() <= self.status_message_until:
            return self.status_message
        return ""

    def _modal_pauses_refresh(self) -> bool:
        try:
            return isinstance(self.screen, (ConfirmKillModal, CommandOutputModal))
        except Exception:
            return False

    def _row_host_port(self, row: ProcessRecord | None) -> tuple[str, int] | None:
        if row is None or not row.ports:
            return None
        # Prefer a specific bind over wildcard; fallback to localhost for wildcards.
        port = row.ports[0].port
        preferred = None
        for p in row.ports:
            if p.ip not in {"0.0.0.0", "::", ""}:
                preferred = p
                break
        bind = preferred or row.ports[0]
        host = bind.ip
        if host in {"0.0.0.0", ""}:
            host = "127.0.0.1"
        elif host == "::":
            host = "::1"
        return host, int(port)

