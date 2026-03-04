from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from whosat.types import ProcessRecord


class ConfirmKillModal(ModalScreen[tuple[str, int | None, str | None] | None]):
    """Kill confirmation modal. Returns (action, pid, password) or None."""

    def __init__(self, row: ProcessRecord, require_sudo: bool = False):
        super().__init__()
        self.row = row
        self.require_sudo = require_sudo

        pid_str = str(row.pid) if row.pid is not None else "unknown"
        ports_str = ", ".join(str(p.port) for p in row.ports[:8]) or "-"
        self.message_text = (
            f"Kill process '{row.name}' (pid={pid_str})?\n"
            f"Cmd: {(row.cmdline_text or row.exe or '-')[:120]}\n"
            f"Ports: {ports_str}\n\n"
        )
        if require_sudo:
            self.message_text += "Requires elevated privileges. Enter your password below."
        else:
            self.message_text += "This will send SIGTERM first. If it stays alive you can force SIGKILL."

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("[bold #ff4466]Confirm Kill[/]\n")
            yield Static(self.message_text)
            if self.require_sudo:
                yield Static("\n[bold #ffd060]Password:[/]")
                yield Input(placeholder="sudo password", password=True, id="sudo-pass")
            yield Button("Send SIGTERM", id="confirm-term", variant="error")
            yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        if self.require_sudo:
            self.query_one("#sudo-pass", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-term":
            password = None
            if self.require_sudo:
                password = self.query_one("#sudo-pass", Input).value
                if not password:
                    return
            self.dismiss(("term", self.row.pid, password))
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "sudo-pass":
            password = event.input.value
            if password:
                self.dismiss(("term", self.row.pid, password))
