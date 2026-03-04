from __future__ import annotations

import platform
import re
import shutil
import socket
import subprocess
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from whosat.types import PortBinding, ProcessRecord, SystemSnapshot

_SS_USERS_RE = re.compile(r'users:\(\("([^"]+)",pid=(\d+)')

SYSTEMD_PORT_MAP = {
    5432: "postgresql",
    5433: "postgresql",
    3306: "mysql",
    27017: "mongod",
    6379: "redis",
}

WELL_KNOWN_PORTS: dict[int, tuple[str, str, str]] = {
    22: ("sshd", "🔐", "System"),
    53: ("dns", "🌐", "System"),
    80: ("http", "🌐", "Web"),
    443: ("https", "🔒", "Web"),
    631: ("cups", "🖨", "System"),
    3306: ("mysql", "🐬", "Database"),
    5432: ("postgres", "🐘", "Database"),
    5433: ("postgres", "🐘", "Database"),
    6379: ("redis", "⚡", "Database"),
    27017: ("mongodb", "🍃", "Database"),
    9200: ("elasticsearch", "🔍", "Database"),
    2375: ("docker", "🐳", "Docker"),
    2376: ("docker", "🐳", "Docker"),
}


@dataclass(slots=True)
class SystemCollectionResult:
    system: SystemSnapshot
    processes: list[ProcessRecord]
    errors: list[str]


def _import_psutil():
    try:
        import psutil  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - env dependent
        raise RuntimeError("psutil is required to collect system data") from exc
    return psutil


def _family_name(family: int) -> str:
    if family == socket.AF_INET6:
        return "ipv6"
    return "ipv4"


def _proto_name(kind: int) -> str:
    if kind == socket.SOCK_DGRAM:
        return "udp"
    return "tcp"


def parse_ss_output(output: str, proto: str = "TCP") -> list[dict]:
    ports: list[dict] = []
    for raw in output.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        local_addr = parts[3]
        try:
            ip, port, family = _parse_local_addr(local_addr)
            port_num = int(port)
        except Exception:
            continue

        pid = None
        proc_name = None
        m = _SS_USERS_RE.search(line)
        if m:
            proc_name = m.group(1)
            try:
                pid = int(m.group(2))
            except ValueError:
                pid = None

        state = parts[0].upper()
        ports.append(
            {
                "port": port_num,
                "ip": ip,
                "proto": proto.upper(),
                "family": family,
                "pid": pid,
                "proc_name": proc_name,
                "state": state,
            }
        )
    return ports


def _parse_local_addr(local_addr: str) -> tuple[str, str, str]:
    if local_addr.startswith("["):
        ip, port = local_addr.rsplit(":", 1)
        return ip.strip("[]"), port, "IPv6"
    ip, port = local_addr.rsplit(":", 1)
    family = "IPv6" if ":" in ip else "IPv4"
    return ip, port, family


def get_listening_ports_psutil(psutil_module=None) -> list[dict]:
    psutil = psutil_module or _import_psutil()
    try:
        conns = psutil.net_connections(kind="inet")
    except Exception:
        return []

    rows: list[dict] = []
    seen: set[tuple[int, str, str]] = set()
    for c in conns:
        laddr = getattr(c, "laddr", None)
        if not laddr:
            continue
        status = str(getattr(c, "status", "")).upper()
        if status not in {"LISTEN", "NONE"}:
            continue
        ip = getattr(laddr, "ip", None) or (laddr[0] if isinstance(laddr, tuple) and laddr else "")
        port = getattr(laddr, "port", None) or (laddr[1] if isinstance(laddr, tuple) and len(laddr) > 1 else None)
        if port is None:
            continue
        proto = "UDP" if getattr(c, "type", socket.SOCK_STREAM) == socket.SOCK_DGRAM else "TCP"
        family = "IPv6" if getattr(c, "family", socket.AF_INET) == socket.AF_INET6 else "IPv4"
        key = (int(port), str(ip), proto)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "port": int(port),
                "ip": str(ip),
                "proto": proto,
                "family": family,
                "pid": getattr(c, "pid", None),
                "proc_name": None,
                "state": status,
            }
        )
    return rows


def get_listening_ports_ss() -> list[dict]:
    ports, _errors = _get_listening_ports_ss_with_errors()
    return ports


def _get_listening_ports_ss_with_errors() -> tuple[list[dict], list[str]]:
    errors: list[str] = []
    ss_bin = shutil.which("ss")
    if ss_bin is None:
        errors.append("ss not available; using psutil fallback")
        return get_listening_ports_psutil(), errors

    rows: list[dict] = []
    for args, proto in (([ss_bin, "-tlnpH"], "TCP"), ([ss_bin, "-ulnpH"], "UDP")):
        try:
            res = subprocess.run(args, capture_output=True, text=True, timeout=5)
        except FileNotFoundError:
            errors.append("ss not available; using psutil fallback")
            return get_listening_ports_psutil(), errors
        except subprocess.TimeoutExpired:
            errors.append("ss timed out; using psutil fallback")
            return get_listening_ports_psutil(), errors
        if res.returncode != 0:
            stderr = (res.stderr or "").strip()
            errors.append(f"{' '.join(args[1:])} failed: {stderr or 'unknown error'}")
            continue
        rows.extend(parse_ss_output(res.stdout, proto=proto))

    if not rows:
        # fallback only if both scans failed or returned nothing unexpectedly
        fallback = get_listening_ports_psutil()
        if fallback:
            errors.append("ss returned no listeners; using psutil fallback")
            return fallback, errors

    deduped: list[dict] = []
    seen: set[tuple[int, str, str]] = set()
    for entry in rows:
        key = (int(entry["port"]), str(entry["ip"]), str(entry["proto"]).upper())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped, errors


def enrich_with_psutil(port_entry: dict, psutil_module=None) -> dict:
    psutil = psutil_module or _import_psutil()
    enriched = dict(port_entry)
    pid = enriched.get("pid")
    if not pid:
        return enriched
    try:
        proc = psutil.Process(int(pid))
        name = None
        try:
            name = proc.name()
        except Exception:
            pass
        exe = None
        try:
            exe = proc.exe()
        except Exception:
            pass
        cmdline = []
        try:
            cmdline = proc.cmdline()
        except Exception:
            pass
        username = None
        try:
            username = proc.username()
        except Exception:
            pass
        cpu_percent = None
        try:
            cpu_percent = float(proc.cpu_percent(interval=None))
        except Exception:
            pass
        memory_bytes = None
        memory_percent = None
        try:
            mem_info = proc.memory_info()
            memory_bytes = int(mem_info.rss)
        except Exception:
            pass
        try:
            memory_percent = float(proc.memory_percent())
        except Exception:
            pass
        create_time = None
        try:
            create_time = float(proc.create_time())
        except Exception:
            pass
        num_threads = None
        try:
            num_threads = int(proc.num_threads())
        except Exception:
            pass
        status = None
        try:
            status = str(proc.status())
        except Exception:
            pass
        cwd = None
        try:
            cwd = str(proc.cwd())
        except Exception:
            pass
        fd_count = None
        try:
            if hasattr(proc, "num_fds"):
                fd_count = int(proc.num_fds())
        except Exception:
            pass

        enriched.update(
            {
                "proc_name": name or enriched.get("proc_name"),
                "exe": exe,
                "cmdline": cmdline,
                "username": username,
                "cpu_percent": cpu_percent,
                "memory_bytes": memory_bytes,
                "memory_percent": memory_percent,
                "create_time": create_time,
                "num_threads": num_threads,
                "status": status,
                "cwd": cwd,
                "fd_count": fd_count,
            }
        )
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        enriched["restricted"] = True
    except Exception:
        enriched["restricted"] = True
    return enriched


def collect_system_snapshot() -> SystemCollectionResult:
    psutil = _import_psutil()
    errors: list[str] = []
    now = time.time()

    ss_rows, ss_errors = _get_listening_ports_ss_with_errors()
    errors.extend(ss_errors)

    # Backfill missing PIDs from psutil.net_connections() — ss without root
    # cannot show process info for other users' sockets.
    missing_pid = any(r.get("pid") is None for r in ss_rows)
    if missing_pid:
        port_pid_map: dict[tuple[int, str], int] = {}
        try:
            for c in psutil.net_connections(kind="inet"):
                laddr = getattr(c, "laddr", None)
                pid = getattr(c, "pid", None)
                if not laddr or not pid:
                    continue
                port = getattr(laddr, "port", None)
                ip = getattr(laddr, "ip", None) or ""
                if port is not None:
                    port_pid_map[(int(port), str(ip))] = int(pid)
                    # Also store wildcard lookup for 0.0.0.0 / ::
                    port_pid_map[(int(port), "")] = int(pid)
        except Exception:
            pass

        for row in ss_rows:
            if row.get("pid") is None:
                port = int(row.get("port", 0))
                ip = str(row.get("ip", ""))
                pid = port_pid_map.get((port, ip)) or port_pid_map.get((port, ""))
                if pid:
                    row["pid"] = pid

    enriched_rows = [enrich_with_psutil(entry, psutil_module=psutil) for entry in ss_rows]
    enriched_rows, filtered_unknown_count = _apply_well_known_and_noise_filter(enriched_rows)
    if filtered_unknown_count > 5:
        errors.append("Run with sudo for full process details: sudo whosat")

    tcp_count = sum(1 for e in enriched_rows if str(e.get("proto", "")).upper() == "TCP")
    udp_count = sum(1 for e in enriched_rows if str(e.get("proto", "")).upper() == "UDP")
    ipv4_count = sum(1 for e in enriched_rows if str(e.get("family", "")).upper() == "IPV4")
    ipv6_count = sum(1 for e in enriched_rows if str(e.get("family", "")).upper() == "IPV6")

    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for entry in enriched_rows:
        pid = entry.get("pid")
        if pid is not None:
            buckets[("pid", int(pid))].append(entry)
        else:
            fallback_name = str(entry.get("proc_name") or f"port-{entry.get('port')}")
            # Group pid-less rows by logical service+port+proto so multi-bind listeners (0.0.0.0,127.0.0.1,::1) are one row.
            buckets[("anon", fallback_name, entry.get("proto"), entry.get("port"))].append(entry)

    process_records: list[ProcessRecord] = []
    for group_entries in buckets.values():
        first = group_entries[0]
        ports: list[PortBinding] = []
        for e in group_entries:
            proto_l = str(e.get("proto", "TCP")).lower()
            family_l = str(e.get("family", "IPv4")).lower()
            ports.append(
                PortBinding(
                    port=int(e.get("port", 0)),
                    ip=str(e.get("ip") or ""),
                    proto="udp" if proto_l == "udp" else "tcp",
                    family="ipv6" if family_l == "ipv6" else "ipv4",
                    is_listening=str(e.get("state", "LISTEN")).upper() in {"LISTEN", "UNCONN", "NONE"},
                )
            )
        # de-dupe ports within row
        uniq_ports: list[PortBinding] = []
        seen_ports: set[tuple[int, str, str]] = set()
        for p in ports:
            key = (p.port, p.ip, p.proto)
            if key in seen_ports:
                continue
            seen_ports.add(key)
            uniq_ports.append(p)

        pid = first.get("pid")
        name = str(first.get("proc_name") or (f"pid-{pid}" if pid is not None else "unknown"))
        collector_errors = []
        restricted = bool(first.get("restricted")) or any(bool(e.get("restricted")) for e in group_entries)
        if restricted:
            collector_errors.append("restricted process metadata")

        process_records.append(
            ProcessRecord(
                pid=int(pid) if pid is not None else None,
                name=name,
                exe=_first_non_none(group_entries, "exe"),
                cwd=_first_non_none(group_entries, "cwd"),
                cmdline=_first_non_none(group_entries, "cmdline") or [],
                username=_first_non_none(group_entries, "username"),
                create_time=_first_non_none(group_entries, "create_time"),
                cpu_percent=_first_non_none(group_entries, "cpu_percent"),
                memory_bytes=_first_non_none(group_entries, "memory_bytes"),
                memory_percent=_first_non_none(group_entries, "memory_percent"),
                threads=_first_non_none(group_entries, "num_threads"),
                fd_count=_first_non_none(group_entries, "fd_count"),
                status_text=_first_non_none(group_entries, "status"),
                ports=sorted(uniq_ports, key=lambda p: (p.port, p.ip, p.proto)),
                source="sys",
                restricted=restricted,
                collector_errors=collector_errors,
            )
        )

    try:
        total_processes = len(psutil.pids())
    except Exception:
        total_processes = 0

    vm = psutil.virtual_memory()
    boot = getattr(psutil, "boot_time", lambda: now)()
    try:
        cpu_percent = float(psutil.cpu_percent(interval=None))
    except Exception:
        cpu_percent = 0.0
    try:
        per_core = [float(v) for v in psutil.cpu_percent(interval=None, percpu=True)]
    except Exception:
        per_core = []

    local_ips = _local_ips()

    system = SystemSnapshot(
        hostname=platform.node() or "localhost",
        os_version=f"{platform.system()} {platform.release()}".strip(),
        cpu_percent=cpu_percent,
        per_core_percent=per_core,
        memory_used_bytes=int(vm.used),
        memory_total_bytes=int(vm.total),
        uptime_seconds=int(max(0, now - float(boot))),
        local_ips=local_ips,
        total_processes=total_processes,
        processes_with_ports=len(process_records),
        tcp_count=tcp_count,
        udp_count=udp_count,
        ipv4_count=ipv4_count,
        ipv6_count=ipv6_count,
    )
    try:
        du = shutil.disk_usage("/")
        system.disk_used_bytes = int(du.used)
        system.disk_total_bytes = int(du.total)
    except Exception:
        pass
    return SystemCollectionResult(system=system, processes=process_records, errors=errors)


def _first_non_none(entries: list[dict], key: str):
    for e in entries:
        if key in e and e[key] not in (None, ""):
            return e[key]
    return None


def _apply_well_known_and_noise_filter(rows: list[dict]) -> tuple[list[dict], int]:
    kept: list[dict] = []
    filtered_unknown = 0
    for entry in rows:
        e = dict(entry)
        pid = e.get("pid")
        raw_name = str(e.get("proc_name") or "").strip().lower()
        unknownish = raw_name in {"", "-", "unknown", "kernel"}
        if pid is None and (unknownish or not raw_name):
            wk = WELL_KNOWN_PORTS.get(int(e.get("port", -1)))
            if wk:
                e["proc_name"] = wk[0]
                e["well_known"] = True
            else:
                filtered_unknown += 1
                continue
        elif not raw_name and int(e.get("port", -1)) in WELL_KNOWN_PORTS:
            e["proc_name"] = WELL_KNOWN_PORTS[int(e["port"])][0]
            e["well_known"] = True
        kept.append(e)
    return kept, filtered_unknown


def get_systemd_service_status(service_name: str) -> dict:
    systemctl = shutil.which("systemctl")
    if systemctl is None:
        return {"active": False}
    try:
        result = subprocess.run([systemctl, "is-active", service_name], capture_output=True, text=True, timeout=3)
        return {"active": result.stdout.strip() == "active"}
    except Exception:
        return {"active": False}


def _local_ips() -> list[str]:
    ips: set[str] = set()
    try:
        for res in socket.getaddrinfo(socket.gethostname(), None):
            addr = res[4][0]
            if addr and not addr.startswith("127.") and addr != "::1":
                ips.add(addr)
    except OSError:
        pass
    return sorted(ips)
