from __future__ import annotations

from whosat.services.aggregator import normalized_group_name
from whosat.types import ProcessRecord, Scope, SortField, SortOrder


def row_matches_search(row: ProcessRecord, query: str) -> bool:
    q = query.strip().lower()
    if not q:
        return True
    hay = [
        row.name,
        row.exe or "",
        row.cmdline_text,
        row.docker_container_name or "",
        row.docker_image or "",
        row.derived_status,
    ]
    hay.extend(str(p.port) for p in row.ports)
    hay.extend(p.ip for p in row.ports)
    joined = "\n".join(hay).lower()
    return q in joined


def row_in_scope(row: ProcessRecord, scope: Scope) -> bool:
    if scope == "all":
        return True
    if scope == "docker":
        return row.source == "docker" or row.docker_container_id is not None
    return row.source == "sys"


def row_in_category(row: ProcessRecord, category_key: str | None) -> bool:
    if not category_key or category_key == "all":
        return True
    return normalized_group_name(row) == category_key


def _sort_value(row: ProcessRecord, field: SortField):
    if field == "port":
        return (row.min_port if row.min_port is not None else 10**9, row.name.lower())
    if field == "name":
        return row.name.lower()
    if field == "created":
        return row.create_time if row.create_time is not None else float("inf")
    if field == "cpu":
        return row.cpu_percent if row.cpu_percent is not None else float("-inf")
    if field == "mem":
        return row.memory_bytes if row.memory_bytes is not None else -1
    return row.name.lower()


def sort_rows(rows: list[ProcessRecord], field: SortField, order: SortOrder) -> list[ProcessRecord]:
    reverse = order == "desc"
    if field in {"cpu", "mem"}:
        # Partition: rows with data first (sorted), rows without data last
        attr = "cpu_percent" if field == "cpu" else "memory_bytes"
        present = [r for r in rows if getattr(r, attr) is not None]
        absent = [r for r in rows if getattr(r, attr) is None]
        return sorted(present, key=lambda r: _sort_value(r, field), reverse=reverse) + absent
    return sorted(rows, key=lambda r: _sort_value(r, field), reverse=reverse)


def apply_filters(
    rows: list[ProcessRecord],
    *,
    search_query: str,
    scope: Scope,
    category_key: str | None,
    sort_by: SortField,
    sort_order: SortOrder,
) -> list[ProcessRecord]:
    filtered = [
        r for r in rows if row_in_scope(r, scope) and row_in_category(r, category_key) and row_matches_search(r, search_query)
    ]
    return sort_rows(filtered, sort_by, sort_order)
