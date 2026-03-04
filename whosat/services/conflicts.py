"""Port conflict detection — reusable by CLI and TUI."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from whosat.types import ProcessRecord


@dataclass(slots=True)
class PortConflict:
    port: int
    kind: str  # "multi_pid" | "mixed_bind"
    pids: list[int] = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    ips: list[str] = field(default_factory=list)
    message: str = ""


def detect_conflicts(rows: list[ProcessRecord]) -> list[PortConflict]:
    """Scan rows for port conflicts: multiple PIDs or wildcard+specific bind."""
    # Map port → list of (pid, name, ips)
    port_map: dict[int, list[tuple[int | None, str, set[str]]]] = defaultdict(list)
    for row in rows:
        row_ips: set[str] = set()
        for pb in row.ports:
            row_ips.add(pb.ip)
            port_map[pb.port].append((row.pid, row.name, {pb.ip}))

    # Deduplicate entries per port by pid
    conflicts: list[PortConflict] = []
    seen_ports: set[int] = set()

    for port, entries in sorted(port_map.items()):
        # Collapse entries by pid
        by_pid: dict[int | None, tuple[str, set[str]]] = {}
        for pid, name, ips in entries:
            if pid in by_pid:
                by_pid[pid][1].update(ips)
            else:
                by_pid[pid] = (name, set(ips))

        if port in seen_ports:
            continue

        unique_pids = {p for p in by_pid if p is not None}
        all_ips: set[str] = set()
        all_names: list[str] = []
        for pid, (name, ips) in by_pid.items():
            all_ips.update(ips)
            if name not in all_names:
                all_names.append(name)

        # multi_pid: same port bound by different PIDs
        if len(unique_pids) > 1:
            seen_ports.add(port)
            conflicts.append(PortConflict(
                port=port,
                kind="multi_pid",
                pids=sorted(unique_pids),
                names=all_names,
                ips=sorted(all_ips),
                message=f"Port {port} bound by {len(unique_pids)} processes: {', '.join(all_names)}",
            ))

        # mixed_bind: wildcard (0.0.0.0 or ::) AND specific IP
        wildcards = {"0.0.0.0", "::", "*"}
        has_wildcard = bool(all_ips & wildcards)
        has_specific = bool(all_ips - wildcards)
        if has_wildcard and has_specific and port not in seen_ports:
            seen_ports.add(port)
            conflicts.append(PortConflict(
                port=port,
                kind="mixed_bind",
                pids=sorted(unique_pids),
                names=all_names,
                ips=sorted(all_ips),
                message=f"Port {port} has wildcard and specific bind: {', '.join(sorted(all_ips))}",
            ))

    return conflicts
