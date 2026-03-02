from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from whosat.types import ContainerRecord, PortBinding


@dataclass(slots=True)
class DockerCollectionResult:
    containers: list[ContainerRecord]
    errors: list[str]
    running_count: int
    stopped_count: int


def collect_docker_snapshot(enabled: bool = True) -> DockerCollectionResult:
    if not enabled:
        return DockerCollectionResult([], [], 0, 0)
    try:
        import docker  # type: ignore
    except ModuleNotFoundError:
        return _docker_cli_fallback_or_hint()

    try:
        client = docker.from_env()
        raw_containers = client.containers.list(all=True)
    except Exception as exc:  # pragma: no cover - runtime dependent
        return DockerCollectionResult([], [f"docker unavailable: {exc}"], 0, 0)

    containers: list[ContainerRecord] = []
    running = 0
    stopped = 0
    for c in raw_containers:
        attrs: dict[str, Any] = getattr(c, "attrs", {}) or {}
        state = str((attrs.get("State") or {}).get("Status") or getattr(c, "status", "unknown"))
        if state == "running":
            running += 1
        else:
            stopped += 1
        ports = _parse_ports(attrs)
        pid = None
        state_pid = (attrs.get("State") or {}).get("Pid")
        if isinstance(state_pid, int) and state_pid > 0:
            pid = state_pid
        containers.append(
            ContainerRecord(
                id=str(getattr(c, "id", ""))[:12],
                name=str(getattr(c, "name", "container")),
                image=str(getattr(getattr(c, "image", None), "tags", [""])[:1][0] if getattr(c, "image", None) else ""),
                state=state,
                status=str(getattr(c, "status", state)),
                ports=ports,
                pid=pid,
            )
        )
    return DockerCollectionResult(containers, [], running, stopped)


def _docker_cli_fallback_or_hint() -> DockerCollectionResult:
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return DockerCollectionResult([], ["Docker support unavailable: install Docker CLI or pip install whosat[docker]"], 0, 0)

    probe = subprocess.run(
        [docker_bin, "ps", "-q"],
        capture_output=True,
        text=True,
        timeout=3,
    )
    if probe.returncode != 0:
        stderr = (probe.stderr or "").strip().lower()
        if "cannot connect to the docker daemon" in stderr or "is the docker daemon running" in stderr:
            return DockerCollectionResult([], ["Docker daemon not running"], 0, 0)
        if "permission denied" in stderr:
            return DockerCollectionResult([], ["Docker daemon permission denied"], 0, 0)
        return DockerCollectionResult([], [f"Docker CLI unavailable: {(probe.stderr or probe.stdout).strip() or 'unknown error'}"], 0, 0)

    running = len([line for line in probe.stdout.splitlines() if line.strip()])
    total = _docker_cli_total_count(docker_bin)
    stopped = max(0, total - running) if total is not None else 0
    return DockerCollectionResult(
        [],
        ["Docker daemon reachable. Install Python SDK for full integration: pip install whosat[docker]"],
        running,
        stopped,
    )


def _docker_cli_total_count(docker_bin: str) -> int | None:
    try:
        res = subprocess.run(
            [docker_bin, "ps", "-aq"],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except Exception:
        return None
    if res.returncode != 0:
        return None
    return len([line for line in res.stdout.splitlines() if line.strip()])


def _parse_ports(attrs: dict[str, Any]) -> list[PortBinding]:
    result: list[PortBinding] = []
    ports_map = ((attrs.get("NetworkSettings") or {}).get("Ports") or {})
    for key, mappings in ports_map.items():
        try:
            port_str, proto = key.split("/", 1)
            internal_port = int(port_str)
        except Exception:
            continue
        proto = proto.lower()
        if not mappings:
            result.append(PortBinding(port=internal_port, proto="tcp" if proto != "udp" else "udp", family="ipv4", ip="0.0.0.0"))
            continue
        for m in mappings:
            host_ip = str(m.get("HostIp") or "0.0.0.0")
            try:
                host_port = int(m.get("HostPort") or internal_port)
            except Exception:
                host_port = internal_port
            family = "ipv6" if ":" in host_ip else "ipv4"
            result.append(
                PortBinding(
                    port=host_port,
                    proto="udp" if proto == "udp" else "tcp",
                    family=family,
                    ip=host_ip,
                    is_listening=True,
                )
            )
    return result
