from __future__ import annotations

import os
import signal
import time
from dataclasses import dataclass

from whosat.types import ProcessRecord


@dataclass(slots=True)
class KillResult:
    ok: bool
    message: str
    pid: int | None
    signal_sent: int | None = None
    still_running: bool | None = None


def can_kill(row: ProcessRecord) -> bool:
    return row.pid is not None


def send_term(pid: int) -> KillResult:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return KillResult(True, "Process already exited", pid, signal.SIGTERM, still_running=False)
    except PermissionError:
        return KillResult(False, "Permission denied", pid, signal.SIGTERM)
    except OSError as exc:
        return KillResult(False, f"SIGTERM failed: {exc}", pid, signal.SIGTERM)
    return KillResult(True, "SIGTERM sent", pid, signal.SIGTERM)


def send_kill(pid: int) -> KillResult:
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return KillResult(True, "Process already exited", pid, signal.SIGKILL, still_running=False)
    except PermissionError:
        return KillResult(False, "Permission denied", pid, signal.SIGKILL)
    except OSError as exc:
        return KillResult(False, f"SIGKILL failed: {exc}", pid, signal.SIGKILL)
    return KillResult(True, "SIGKILL sent", pid, signal.SIGKILL)


def pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def terminate_then_check(pid: int, grace_seconds: float = 2.0) -> KillResult:
    result = send_term(pid)
    if not result.ok:
        return result
    deadline = time.time() + grace_seconds
    while time.time() < deadline:
        if not pid_exists(pid):
            result.still_running = False
            result.message = "Process terminated"
            return result
        time.sleep(0.1)
    result.still_running = pid_exists(pid)
    if result.still_running:
        result.message = "Process still running after SIGTERM"
    else:
        result.message = "Process terminated"
    return result
