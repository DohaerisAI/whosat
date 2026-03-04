"""Rich-based CLI rendering — no Textual imports."""

from __future__ import annotations

import datetime
import json
import sys
import time

from rich.console import Console
from rich.table import Table
from rich.text import Text

from whosat.constants import icon_for_process
from whosat.formatting import fmt_bytes, fmt_percent, fmt_uptime
from whosat.services.conflicts import PortConflict
from whosat.types import AppSnapshot, ProcessRecord

# Auto-detect: no color/markup when piped
_console = Console(highlight=False, force_terminal=None)
_stderr = Console(stderr=True, highlight=False)


# ── JSON serialization ──────────────────────────────────────────


def process_to_dict(row: ProcessRecord, now: float | None = None) -> dict:
    """Convert a ProcessRecord to a JSON-serializable dict (stable API schema)."""
    if now is None:
        now = time.time()
    uptime = None
    if row.create_time is not None:
        uptime = max(0, now - row.create_time)
    docker = None
    if row.docker_container_id:
        docker = {
            "container_id": row.docker_container_id,
            "container_name": row.docker_container_name,
            "image": row.docker_image,
            "status": row.docker_status,
        }
    return {
        "pid": row.pid,
        "name": row.name,
        "username": row.username,
        "exe": row.exe,
        "cmdline": row.cmdline,
        "status": row.derived_status,
        "source": row.source,
        "ports": [
            {"port": p.port, "proto": p.proto, "family": p.family, "ip": p.ip}
            for p in row.ports
        ],
        "cpu_percent": row.cpu_percent,
        "memory_bytes": row.memory_bytes,
        "memory_percent": row.memory_percent,
        "threads": row.threads,
        "uptime_seconds": round(uptime, 1) if uptime is not None else None,
        "docker": docker,
    }


def snapshot_to_dict(snap: AppSnapshot) -> dict:
    """Full scan → dict (system + processes + conflicts + errors)."""
    from whosat import __version__
    from whosat.services.conflicts import detect_conflicts

    s = snap.system
    conflicts = detect_conflicts(snap.processes)
    now = snap.collected_at
    return {
        "version": __version__,
        "collected_at": datetime.datetime.fromtimestamp(now).isoformat(timespec="seconds"),
        "system": {
            "hostname": s.hostname,
            "os_version": s.os_version,
            "cpu_percent": s.cpu_percent,
            "memory_used_bytes": s.memory_used_bytes,
            "memory_total_bytes": s.memory_total_bytes,
            "uptime_seconds": s.uptime_seconds,
            "local_ips": s.local_ips,
            "total_processes": s.total_processes,
            "processes_with_ports": s.processes_with_ports,
            "tcp_count": s.tcp_count,
            "udp_count": s.udp_count,
            "ipv4_count": s.ipv4_count,
            "ipv6_count": s.ipv6_count,
            "docker_running": s.docker_running,
            "docker_stopped": s.docker_stopped,
        },
        "processes": [process_to_dict(r, now) for r in snap.processes],
        "conflicts": [
            {"port": c.port, "kind": c.kind, "message": c.message}
            for c in conflicts
        ],
        "errors": snap.errors,
    }


def print_json(data: dict) -> None:
    """Pretty JSON to stdout."""
    sys.stdout.write(json.dumps(data, indent=2, default=str) + "\n")


# ── Port lookup one-liner ────────────────────────────────────────


def print_port_oneliner(row: ProcessRecord, port: int) -> None:
    """Rich colored one-liner for `whosat <port>`."""
    icon = icon_for_process(row.name)
    pid_str = str(row.pid) if row.pid else "?"
    protos = "+".join(sorted({p.proto.upper() for p in row.ports if p.port == port})) or "TCP"
    ips = sorted({p.ip for p in row.ports if p.port == port})
    ip_str = ips[0] if ips else "0.0.0.0"

    status_color = {"ONLINE": "green", "WARN": "yellow", "OFFLINE": "red"}.get(row.derived_status, "white")
    mem = fmt_bytes(row.memory_bytes) if row.memory_bytes else "-"
    cpu = fmt_percent(row.cpu_percent) if row.cpu_percent is not None else "-"
    uptime = fmt_uptime(time.time() - row.create_time) if row.create_time else "-"
    user = row.username or "-"

    line = Text()
    line.append(f"{icon} ", style="bold")
    line.append(f":{port}", style="bold yellow")
    line.append(" → ", style="dim")
    line.append(f"{row.name}", style="bold")
    line.append(f" (pid {pid_str})", style="dim")
    line.append(f"  {protos}/{ip_str}", style="cyan")
    line.append(f"  [{row.derived_status}]", style=f"bold {status_color}")
    line.append(f"  cpu {cpu}", style="dim")
    line.append(f"  mem {mem}", style="dim")
    line.append(f"  up {uptime}", style="dim")
    line.append(f"  user {user}", style="dim")

    _console.print(line)


def print_port_not_found(port: int) -> None:
    """Red 'nothing listening' message."""
    _stderr.print(f"[red bold]Nothing listening on port {port}[/]")


# ── Process table (whosat ls) ────────────────────────────────────


def print_process_table(
    rows: list[ProcessRecord],
    sort_by: str,
    sort_order: str,
    conflicts: list[PortConflict] | None = None,
) -> None:
    """Rich Table for `whosat ls`."""
    if conflicts:
        print_conflicts(conflicts)

    table = Table(
        show_header=True,
        header_style="bold dim",
        border_style="dim",
        pad_edge=False,
        box=None,
        expand=True,
    )
    table.add_column("PORT", style="bold yellow", min_width=7, no_wrap=True)
    table.add_column("NAME", style="bold", min_width=16)
    table.add_column("PID", style="dim", min_width=7, no_wrap=True, justify="right")
    table.add_column("USER", style="dim", min_width=8)
    table.add_column("PROTO", style="dim", min_width=10, no_wrap=True)
    table.add_column("IP", style="cyan", min_width=14, no_wrap=True)
    table.add_column("STATUS", min_width=8, no_wrap=True)
    table.add_column("CPU", style="dim", min_width=6, no_wrap=True, justify="right")
    table.add_column("MEM", style="dim", min_width=8, no_wrap=True, justify="right")
    table.add_column("UPTIME", style="dim", min_width=7, no_wrap=True)

    for row in rows:
        ports_str = ",".join(str(p.port) for p in row.ports[:4])
        if len(row.ports) > 4:
            ports_str += f"+{len(row.ports) - 4}"

        protos = "+".join(sorted({p.proto.upper() for p in row.ports})) or "-"
        ips = sorted({p.ip for p in row.ports})
        ip_str = ips[0] if ips else "-"

        pid_str = str(row.pid) if row.pid else "-"
        user = row.username or "-"
        cpu = fmt_percent(row.cpu_percent) if row.cpu_percent is not None else "-"
        mem = fmt_bytes(row.memory_bytes) if row.memory_bytes else "-"
        uptime = fmt_uptime(time.time() - row.create_time) if row.create_time else "-"

        status_color = {"ONLINE": "green", "WARN": "yellow", "OFFLINE": "red"}.get(row.derived_status, "white")
        status = Text(f"● {row.derived_status}", style=f"{status_color}")

        icon = icon_for_process(row.name)
        name = f"{icon} {row.name}"

        table.add_row(ports_str, name, pid_str, user, protos, ip_str, status, cpu, mem, uptime)

    _console.print(table)
    _console.print(f"\n[dim]{len(rows)} process{'es' if len(rows) != 1 else ''} with open ports[/]")


# ── Kill output ──────────────────────────────────────────────────


def print_kill_target(row: ProcessRecord, port: int) -> None:
    """Show process about to be killed."""
    icon = icon_for_process(row.name)
    pid_str = str(row.pid) if row.pid else "?"
    _console.print(
        f"[bold]{icon} {row.name}[/] (pid [cyan]{pid_str}[/]) on port [yellow]{port}[/]"
    )


# ── Conflicts ────────────────────────────────────────────────────


def print_conflicts(conflicts: list[PortConflict]) -> None:
    """Yellow warnings for port conflicts."""
    for c in conflicts:
        _console.print(f"[yellow bold]⚠ {c.message}[/]")
    if conflicts:
        _console.print()
