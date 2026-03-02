from __future__ import annotations

import time
from dataclasses import dataclass

from whosat.collector.docker import collect_docker_snapshot
from whosat.collector.system import collect_system_snapshot
from whosat.services.aggregator import merge_processes_with_containers
from whosat.services.status import apply_status
from whosat.types import AppSnapshot, SystemSnapshot


@dataclass(slots=True)
class RefreshConfig:
    docker_enabled: bool = True
    collect_memory: bool = False


def make_empty_system() -> SystemSnapshot:
    return SystemSnapshot(
        hostname="localhost",
        os_version="unknown",
        cpu_percent=0.0,
        per_core_percent=[],
        memory_used_bytes=0,
        memory_total_bytes=0,
        uptime_seconds=0,
        local_ips=[],
        total_processes=0,
        processes_with_ports=0,
        tcp_count=0,
        udp_count=0,
        ipv4_count=0,
        ipv6_count=0,
        docker_running=0,
        docker_stopped=0,
        disk_used_bytes=0,
        disk_total_bytes=0,
    )


def collect_snapshot(config: RefreshConfig) -> AppSnapshot:
    errors: list[str] = []
    try:
        sysres = collect_system_snapshot()
        system = sysres.system
        rows = sysres.processes
        errors.extend(sysres.errors)
    except Exception as exc:
        system = make_empty_system()
        rows = []
        errors.append(str(exc))

    dock = collect_docker_snapshot(enabled=config.docker_enabled)
    errors.extend(dock.errors)
    system.docker_running = dock.running_count
    system.docker_stopped = dock.stopped_count

    merged = merge_processes_with_containers(rows, dock.containers)
    apply_status(merged)

    # Optional memory collection
    memory_snap = None
    if config.collect_memory:
        try:
            from whosat.collector.memory import collect_memory_snapshot
            memory_snap = collect_memory_snapshot()
        except Exception as exc:
            errors.append(f"memory: {exc}")

    return AppSnapshot(
        system=system,
        processes=merged,
        containers=dock.containers,
        collected_at=time.time(),
        errors=errors,
        memory=memory_snap,
    )
