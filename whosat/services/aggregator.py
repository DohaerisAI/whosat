from __future__ import annotations

from collections import defaultdict

from whosat.constants import icon_for_process
from whosat.types import CategoryItem, ContainerRecord, GroupSummary, ProcessRecord

DB_NAMES = {
    "postgres",
    "postgresql",
    "mysql",
    "mariadb",
    "mongod",
    "redis",
    "redis-server",
    "sqlite",
}


def merge_processes_with_containers(
    processes: list[ProcessRecord],
    containers: list[ContainerRecord],
) -> list[ProcessRecord]:
    by_pid = {row.pid: row for row in processes if row.pid is not None}
    merged = list(processes)

    for c in containers:
        target = by_pid.get(c.pid) if c.pid is not None else None
        if target is not None:
            target.docker_container_id = c.id
            target.docker_container_name = c.name
            target.docker_image = c.image
            target.docker_status = c.status
            # Preserve local process source; Docker scope filtering can use docker metadata presence.
            if c.ports and not target.ports:
                target.ports = list(c.ports)
            continue
        merged.append(
            ProcessRecord(
                pid=None,
                name=c.name,
                exe=None,
                cmdline=[c.image] if c.image else [],
                ports=list(c.ports),
                source="docker",
                docker_container_id=c.id,
                docker_container_name=c.name,
                docker_image=c.image,
                docker_status=c.status,
            )
        )
    return merged


def normalized_group_name(row: ProcessRecord) -> str:
    name = (row.name or "unknown").strip().lower()
    if row.source == "docker":
        return "containers"
    if not name:
        return "unknown"
    if name.endswith(".exe"):
        name = name[:-4]
    return name


def icon_for_name(name: str) -> str:
    return icon_for_process(name)


def section_for_name(name: str, is_docker: bool = False) -> str:
    if is_docker or name == "containers":
        return "Docker"
    if name.lower() in DB_NAMES:
        return "Database"
    return "System"


def build_groups(rows: list[ProcessRecord]) -> list[GroupSummary]:
    buckets: dict[str, list[ProcessRecord]] = defaultdict(list)
    for row in rows:
        buckets[normalized_group_name(row)].append(row)

    groups: list[GroupSummary] = []
    for key in sorted(buckets):
        grows = buckets[key]
        up = sum(1 for r in grows if r.derived_status == "ONLINE")
        warn = sum(1 for r in grows if r.derived_status == "WARN")
        down = sum(1 for r in grows if r.derived_status == "OFFLINE")
        source = "docker" if key == "containers" or all(r.source == "docker" for r in grows) else "sys"
        groups.append(
            GroupSummary(
                key=key,
                label=key,
                icon=icon_for_name(key),
                source=source,
                rows=grows,
                up_count=up,
                warn_count=warn,
                down_count=down,
            )
        )
    return groups


def build_categories(rows: list[ProcessRecord]) -> list[CategoryItem]:
    groups = build_groups(rows)
    cats: list[CategoryItem] = []
    total_up = sum(1 for r in rows if r.derived_status == "ONLINE")
    total_warn = sum(1 for r in rows if r.derived_status == "WARN")
    total_down = sum(1 for r in rows if r.derived_status == "OFFLINE")
    cats.append(
        CategoryItem(
            key="all",
            label="All Processes",
            icon="\U0001f4cb",
            section="Categories",
            count=len(rows),
            up_count=total_up,
            warn_count=total_warn,
            down_count=total_down,
        )
    )
    for g in groups:
        cats.append(
            CategoryItem(
                key=g.key,
                label=g.label,
                icon=g.icon,
                section=section_for_name(g.key, g.source == "docker"),
                count=len(g.rows),
                up_count=g.up_count,
                warn_count=g.warn_count,
                down_count=g.down_count,
            )
        )
    return cats
