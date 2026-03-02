from __future__ import annotations

from whosat.types import ProcessRecord, RowStatus


CPU_WARN = 70.0
MEM_WARN = 80.0


def derive_row_status(row: ProcessRecord) -> RowStatus:
    if row.collector_errors:
        return "WARN"
    if row.cpu_percent is not None and row.cpu_percent > CPU_WARN:
        return "WARN"
    if row.memory_percent is not None and row.memory_percent > MEM_WARN:
        return "WARN"
    has_listener = any(p.is_listening for p in row.ports)
    if row.source == "docker" and row.pid is None and not has_listener:
        return "OFFLINE"
    if has_listener or row.pid is not None:
        return "ONLINE"
    return "OFFLINE"


def apply_status(rows: list[ProcessRecord]) -> list[ProcessRecord]:
    for row in rows:
        row.derived_status = derive_row_status(row)
    return rows
