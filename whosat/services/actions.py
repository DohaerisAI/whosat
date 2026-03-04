from __future__ import annotations

import os
import shutil
import signal
import subprocess
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
    """A row is killable if it has a PID or a port we can resolve."""
    return row.pid is not None or bool(row.ports)


def needs_sudo(row: ProcessRecord) -> bool:
    """Check if killing this process likely requires sudo."""
    if row.pid is None:
        return True
    try:
        os.kill(row.pid, 0)
        return False
    except PermissionError:
        return True
    except (ProcessLookupError, OSError):
        return False


def resolve_pid_via_sudo(port: int, proto: str, password: str) -> int | None:
    """Use sudo ss to resolve PID from port when we lack permissions."""
    sudo = shutil.which("sudo")
    ss = shutil.which("ss")
    if not sudo or not ss:
        return None

    flag = "-tlnpH" if proto.lower() == "tcp" else "-ulnpH"
    try:
        result = subprocess.run(
            [sudo, "-S", ss, flag],
            input=password + "\n",
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None

    if result.returncode != 0:
        return None

    import re
    pid_re = re.compile(r'users:\(\("([^"]+)",pid=(\d+)')
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        local_addr = parts[3]
        if ":" not in local_addr:
            continue
        try:
            line_port = int(local_addr.rsplit(":", 1)[1])
        except (ValueError, IndexError):
            continue
        if line_port == port:
            m = pid_re.search(line)
            if m:
                try:
                    return int(m.group(2))
                except ValueError:
                    pass
    return None


def sudo_kill(pid: int, password: str, sig: int = signal.SIGTERM) -> KillResult:
    """Kill a process using sudo."""
    sudo = shutil.which("sudo")
    if not sudo:
        return KillResult(False, "sudo not found", pid, sig)

    sig_flag = "-TERM" if sig == signal.SIGTERM else "-KILL"
    try:
        result = subprocess.run(
            [sudo, "-S", "kill", sig_flag, str(pid)],
            input=password + "\n",
            capture_output=True, text=True, timeout=10,
        )
    except subprocess.TimeoutExpired:
        return KillResult(False, "sudo kill timed out", pid, sig)
    except OSError as exc:
        return KillResult(False, f"sudo kill failed: {exc}", pid, sig)

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "incorrect password" in stderr.lower() or "sorry" in stderr.lower():
            return KillResult(False, "Incorrect password", pid, sig)
        return KillResult(False, f"sudo kill failed: {stderr}", pid, sig)

    return KillResult(True, f"{'SIGTERM' if sig == signal.SIGTERM else 'SIGKILL'} sent (sudo)", pid, sig)


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


def terminate_then_check(pid: int, password: str | None = None, grace_seconds: float = 2.0) -> KillResult:
    if password:
        result = sudo_kill(pid, password, signal.SIGTERM)
    else:
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
