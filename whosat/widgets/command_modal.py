from __future__ import annotations

import subprocess
import threading
from collections import deque
from pathlib import Path
from typing import Iterable

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class CommandOutputModal(ModalScreen[None]):
    BINDINGS = [("escape", "close", "Close"), ("q", "close", "Close")]
    # Styling moved to whosat.tcss

    def __init__(self, title: str, command: list[str], timeout: float = 10.0):
        super().__init__()
        self.title = title
        self.command = command
        self.timeout = timeout
        self._output = ""
        self._done = False
        self._exit_code: int | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"{self.title}\n$ {' '.join(self.command)}", id="cmd-title")
            with VerticalScroll(id="cmd-output-wrap"):
                yield Static("Running...", id="cmd-output")
            yield Static("", id="cmd-status")
            yield Button("Close", id="close-btn")

    def on_mount(self) -> None:
        self.set_interval(0.2, self._refresh_output)
        threading.Thread(target=self._run_command, daemon=True).start()

    def _run_command(self) -> None:
        try:
            res = subprocess.run(self.command, capture_output=True, text=True, timeout=self.timeout)
            self._output = (res.stdout or "") + (("\n" if res.stdout and res.stderr else "") + (res.stderr or ""))
            self._exit_code = res.returncode
        except FileNotFoundError:
            self._output = f"Command not found: {self.command[0]}"
            self._exit_code = 127
        except subprocess.TimeoutExpired as exc:
            stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
            self._output = (stdout + "\n" + stderr).strip() + "\n\nTimed out."
            self._exit_code = -1
        except Exception as exc:
            self._output = f"Command failed: {exc}"
            self._exit_code = 1
        self._done = True

    def _refresh_output(self) -> None:
        out = self.query_one("#cmd-output", Static)
        status = self.query_one("#cmd-status", Static)
        out.update(self._output or "Running...")
        if self._done:
            status.update(f"Exit code: {self._exit_code}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-btn":
            self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)


class LiveLogModal(ModalScreen[None]):
    BINDINGS = [("escape", "close", "Close"), ("q", "close", "Close")]
    # Styling moved to whosat.tcss

    def __init__(self, title: str, command: list[str]):
        super().__init__()
        self.title = title
        self.command = command
        self._proc: subprocess.Popen[str] | None = None
        self._lines: deque[str] = deque(maxlen=400)
        self._done = False
        self._lock = threading.Lock()

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"{self.title}\n$ {' '.join(self.command)}", id="log-title")
            with VerticalScroll(id="log-wrap"):
                yield Static("Starting...", id="log-output")
            yield Button("Close", id="close-btn")

    def on_mount(self) -> None:
        self.set_interval(0.2, self._refresh_output)
        threading.Thread(target=self._run_follow, daemon=True).start()

    def _run_follow(self) -> None:
        try:
            self._proc = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert self._proc.stdout is not None
            for line in self._proc.stdout:
                with self._lock:
                    self._lines.append(line.rstrip("\n"))
            self._proc.wait(timeout=1)
        except FileNotFoundError:
            with self._lock:
                self._lines.append(f"Command not found: {self.command[0]}")
        except Exception as exc:
            with self._lock:
                self._lines.append(f"Log tail failed: {exc}")
        finally:
            self._done = True

    def _refresh_output(self) -> None:
        with self._lock:
            text = "\n".join(self._lines) or ("Running..." if not self._done else "No output")
        self.query_one("#log-output", Static).update(text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-btn":
            self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)

    def on_unmount(self) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass
