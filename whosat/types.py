from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Proto = Literal["tcp", "udp"]
Family = Literal["ipv4", "ipv6"]
Source = Literal["sys", "docker"]
RowStatus = Literal["ONLINE", "WARN", "OFFLINE"]
Scope = Literal["all", "sys", "docker"]
SortField = Literal["port", "name", "created", "cpu", "mem"]
SortOrder = Literal["asc", "desc"]
ViewMode = Literal["group", "flat"]
MainView = Literal["ports", "memory"]


@dataclass(slots=True)
class PortBinding:
    port: int
    proto: Proto
    family: Family
    ip: str
    is_listening: bool = True


@dataclass(slots=True)
class ProcessRecord:
    pid: int | None
    name: str
    exe: str | None = None
    cwd: str | None = None
    cmdline: list[str] = field(default_factory=list)
    username: str | None = None
    create_time: float | None = None
    cpu_percent: float | None = None
    memory_bytes: int | None = None
    memory_percent: float | None = None
    threads: int | None = None
    fd_count: int | None = None
    status_text: str | None = None
    ports: list[PortBinding] = field(default_factory=list)
    source: Source = "sys"
    docker_container_id: str | None = None
    docker_container_name: str | None = None
    docker_image: str | None = None
    docker_status: str | None = None
    restricted: bool = False
    collector_errors: list[str] = field(default_factory=list)
    derived_status: RowStatus = "ONLINE"

    @property
    def row_key(self) -> str:
        if self.pid is not None:
            return f"pid:{self.pid}"
        cid = self.docker_container_id or self.name
        return f"docker:{cid}"

    @property
    def min_port(self) -> int | None:
        if not self.ports:
            return None
        return min(p.port for p in self.ports)

    @property
    def cmdline_text(self) -> str:
        return " ".join(self.cmdline)


@dataclass(slots=True)
class ContainerRecord:
    id: str
    name: str
    image: str
    state: str
    status: str
    ports: list[PortBinding] = field(default_factory=list)
    pid: int | None = None


@dataclass(slots=True)
class SystemSnapshot:
    hostname: str
    os_version: str
    cpu_percent: float
    per_core_percent: list[float]
    memory_used_bytes: int
    memory_total_bytes: int
    uptime_seconds: int
    local_ips: list[str]
    total_processes: int
    processes_with_ports: int
    tcp_count: int
    udp_count: int
    ipv4_count: int
    ipv6_count: int
    docker_running: int = 0
    docker_stopped: int = 0
    disk_used_bytes: int = 0
    disk_total_bytes: int = 0


@dataclass(slots=True)
class AppSnapshot:
    system: SystemSnapshot
    processes: list[ProcessRecord]
    containers: list[ContainerRecord]
    collected_at: float
    errors: list[str] = field(default_factory=list)
    memory: MemorySnapshot | None = None


@dataclass(slots=True)
class GroupSummary:
    key: str
    label: str
    icon: str
    source: Source
    rows: list[ProcessRecord]
    up_count: int
    warn_count: int
    down_count: int


@dataclass(slots=True)
class CategoryItem:
    key: str
    label: str
    icon: str
    section: str
    count: int
    up_count: int
    warn_count: int
    down_count: int


@dataclass(slots=True)
class MemoryProcessRecord:
    pid: int
    name: str
    username: str | None = None
    exe: str | None = None
    cmdline: list[str] = field(default_factory=list)
    rss_bytes: int = 0
    vms_bytes: int = 0
    memory_percent: float = 0.0
    cpu_percent: float = 0.0
    num_threads: int = 0
    status: str = ""


@dataclass(slots=True)
class GpuProcessRecord:
    pid: int
    name: str
    gpu_memory_bytes: int = 0


@dataclass(slots=True)
class GpuInfo:
    index: int
    name: str
    memory_total_bytes: int = 0
    memory_used_bytes: int = 0
    utilization_percent: float = 0.0


@dataclass(slots=True)
class MemorySnapshot:
    processes: list[MemoryProcessRecord] = field(default_factory=list)
    total_ram_bytes: int = 0
    used_ram_bytes: int = 0
    available_ram_bytes: int = 0
    swap_total_bytes: int = 0
    swap_used_bytes: int = 0
    gpu_available: bool = False
    gpus: list[GpuInfo] = field(default_factory=list)
    gpu_processes: list[GpuProcessRecord] = field(default_factory=list)


@dataclass(slots=True)
class UIState:
    refresh_interval_seconds: int = 30
    scope: Scope = "all"
    sort_by: SortField = "port"
    sort_order: SortOrder = "asc"
    view_mode: ViewMode = "group"
    search_query: str = ""
    selected_category: str | None = None
    selected_row_key: str | None = None
    detail_open: bool = True
    expanded_groups: set[str] = field(default_factory=set)
    expanded_paths: set[str] = field(default_factory=set)
    docker_enabled: bool = True
    refresh_in_progress: bool = False
    next_refresh_eta: int | None = None
    focus_region: str = "table"
    main_view: MainView = "ports"
    memory_search_query: str = ""
    memory_selected_pid: int | None = None
