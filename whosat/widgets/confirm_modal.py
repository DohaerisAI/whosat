from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from whosat.types import ProcessRecord


class ConfirmKillModal(ModalScreen[tuple[str, int | None] | None]):
    class Choice(Message):
        def __init__(self, sender: "ConfirmKillModal", action: str) -> None:
            self.action = action
            super().__init__()

    # Styling moved to whosat.tcss

    def __init__(self, row: ProcessRecord):
        super().__init__()
        self.row = row
        self.message_text = (
            f"Kill process '{row.name}' (pid={row.pid})?\n"
            f"Cmd: {(row.cmdline_text or row.exe or '-')[:120]}\n"
            f"Ports: {', '.join(str(p.port) for p in row.ports[:8]) or '-'}\n\n"
            "This will send SIGTERM first. If it stays alive you can force SIGKILL."
        )

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("[bold #ff4466]Confirm Kill[/]\n")
            yield Static(self.message_text)
            yield Button("Send SIGTERM", id="confirm-term", variant="error")
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-term":
            self.dismiss(("term", self.row.pid))
        else:
            self.dismiss(None)
