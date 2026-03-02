from __future__ import annotations

from textual import on
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button, Input, Static

from whosat.types import SortField, UIState

_SORT_OPTIONS: list[SortField] = ["port", "name", "created", "cpu", "mem"]
_MEM_SORT_OPTIONS = ["mem", "cpu", "name"]


class _GroupBtn(Static):
    """Clickable button inside a connected group."""

    class Pressed(Message):
        def __init__(self, btn_id: str) -> None:
            self.btn_id = btn_id
            super().__init__()

    def on_click(self) -> None:
        self.post_message(self.Pressed(self.id or ""))


class Toolbar(Horizontal):
    class StateChanged(Message):
        def __init__(self, sender: "Toolbar", key: str, value: str | int) -> None:
            self.key = key
            self.value = value
            super().__init__()

    class RefreshRequested(Message):
        pass

    def compose(self):
        # 1. Search box — prefix + input in one bordered container
        with Horizontal(id="search-wrap"):
            yield Static("$>", id="search-prefix")
            yield Input(placeholder="search process, port, ip...", id="search")

        # 2. Scope toggle — connected button group
        with Horizontal(id="scope-group"):
            yield _GroupBtn("ALL", id="scope-all")
            yield _GroupBtn("SYS", id="scope-sys", classes="grp-divider")
            yield _GroupBtn("DOCKER", id="scope-docker", classes="grp-divider")

        # 3. Sort label + cycle button
        yield Static("SORT", id="sort-label")
        yield Button("port \u25be", id="sort-cycle")

        # 4. ASC / DESC — connected button group
        with Horizontal(id="order-group"):
            yield _GroupBtn("ASC", id="order-asc")
            yield _GroupBtn("DESC", id="order-desc", classes="grp-divider")

        # 5. Spacer
        yield Static(id="tb-spacer")

        # 6. View toggle buttons
        yield Button("\u229e GROUP VIEW", id="view-group")
        yield Button("\u2261 FLAT VIEW", id="view-flat")

    def sync_from_state(self, state: UIState) -> None:
        view = state.main_view

        # Show/hide controls based on view
        scope_grp = self.query_one("#scope-group")
        view_grp_btn = self.query_one("#view-group", Button)
        view_flat_btn = self.query_one("#view-flat", Button)

        is_ports = (view == "ports")
        scope_grp.display = is_ports
        view_grp_btn.display = is_ports
        view_flat_btn.display = is_ports

        self.query_one("#sort-cycle", Button).label = f"{state.sort_by} \u25be"

        # Scope active state
        if is_ports:
            for scope in ("all", "sys", "docker"):
                btn = self.query_one(f"#scope-{scope}", _GroupBtn)
                btn.remove_class("scope-active-all", "scope-active-sys", "scope-active-docker")
                if state.scope == scope:
                    btn.add_class(f"scope-active-{scope}")

        # ASC / DESC active state
        asc_btn = self.query_one("#order-asc", _GroupBtn)
        desc_btn = self.query_one("#order-desc", _GroupBtn)
        asc_btn.remove_class("order-active")
        desc_btn.remove_class("order-active")
        if state.sort_order == "asc":
            asc_btn.add_class("order-active")
        else:
            desc_btn.add_class("order-active")

        # View buttons active state
        if is_ports:
            grp_btn = self.query_one("#view-group", Button)
            flat_btn = self.query_one("#view-flat", Button)
            grp_btn.remove_class("view-active")
            flat_btn.remove_class("view-active")
            if state.view_mode == "group":
                grp_btn.add_class("view-active")
            else:
                flat_btn.add_class("view-active")

    @on(Input.Changed, "#search")
    def _on_search_changed(self, event: Input.Changed) -> None:
        # The search key depends on the current view, but the app determines that
        self.post_message(self.StateChanged(self, "search_query", event.value))

    def set_main_view(self, view: str) -> None:
        """Update toolbar visibility for the given main view."""
        # This is called via sync_from_state which reads state.main_view
        pass

    def on__group_btn_pressed(self, event: _GroupBtn.Pressed) -> None:
        bid = event.btn_id
        if bid.startswith("scope-"):
            self.post_message(self.StateChanged(self, "scope", bid.split("-", 1)[1]))
            return
        if bid in ("order-asc", "order-desc"):
            nxt = "asc" if bid == "order-asc" else "desc"
            self.post_message(self.StateChanged(self, "sort_order", nxt))
            return

    @on(Button.Pressed)
    def _on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "sort-cycle":
            current = str(event.button.label).replace(" \u25be", "").strip()
            idx = _SORT_OPTIONS.index(current) if current in _SORT_OPTIONS else 0
            nxt = _SORT_OPTIONS[(idx + 1) % len(_SORT_OPTIONS)]
            self.post_message(self.StateChanged(self, "sort_by", nxt))
            return
        if bid == "view-group":
            self.post_message(self.StateChanged(self, "view_mode", "group"))
            return
        if bid == "view-flat":
            self.post_message(self.StateChanged(self, "view_mode", "flat"))
            return
