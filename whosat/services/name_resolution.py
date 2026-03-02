from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from whosat.types import ProcessRecord


@dataclass(frozen=True, slots=True)
class ResolvedIdentity:
    display_name: str
    origin_label: str
    full_path: str | None
    short_path: str | None
    relative_created: str


_SYSTEM_NAMES = {"systemd", "sshd", "cron", "dockerd", "containerd"}


def resolve_identity(row: ProcessRecord, now: float | None = None) -> ResolvedIdentity:
    now = time.time() if now is None else now
    rel = relative_time_from_epoch(row.create_time, now)

    if row.source == "docker" and row.pid is None:
        display = row.docker_container_name or row.name
        image = row.docker_image or "container"
        cid = row.docker_container_id or "-"
        origin = f"{image} · container id {cid[:12]}"
        return ResolvedIdentity(display, origin, None, None, rel)

    cmd = row.cmdline or []
    proc_name = (row.name or "process").strip()
    lower = proc_name.lower()

    full_path = detect_main_path(row)
    short_path = smart_truncate_path(full_path) if full_path else None

    display = None
    if row.docker_container_name:
        display = row.docker_container_name
    elif lower in {"uvicorn", "gunicorn"}:
        display = extract_app_name(cmd) or proc_name
    elif lower in {"python", "python3"}:
        display = extract_python_name(cmd) or proc_name
    elif lower == "node":
        display = extract_package_json_name(cmd, row.cwd) or extract_node_script_name(cmd) or proc_name
    elif lower == "java":
        display = extract_jar_name(cmd) or proc_name
    elif lower == "ruby":
        display = extract_ruby_name(cmd) or proc_name
    else:
        display = proc_name

    origin = build_origin_line(row, short_path)
    return ResolvedIdentity(display_name=display, origin_label=origin, full_path=full_path, short_path=short_path, relative_created=rel)


def build_origin_line(row: ProcessRecord, short_path: str | None) -> str:
    raw = row.name or "process"
    if row.docker_container_name:
        image = row.docker_image or "docker image"
        cid = (row.docker_container_id or "")[:12]
        return f"{image} · container id {cid}".strip()
    if short_path:
        return f"{raw} · {short_path}"
    if row.exe:
        return f"{raw} · {smart_truncate_path(row.exe)}"
    if raw.lower() in _SYSTEM_NAMES:
        return f"{raw} · system service"
    return raw


def detect_main_path(row: ProcessRecord) -> str | None:
    cmd = row.cmdline or []
    for arg in cmd:
        if not arg or arg.startswith("-"):
            continue
        if arg.endswith(".py") or "/" in arg:
            return os.path.abspath(os.path.expanduser(arg)) if not os.path.isabs(arg) else arg
    if row.exe and "/" in row.exe:
        return row.exe
    return None


def extract_app_name(cmdline: list[str]) -> str | None:
    target = _first_non_flag_target(cmdline)
    if not target:
        return None
    module = target.split(":", 1)[0]
    if not module:
        return None
    return module.split(".")[0]


def extract_python_name(cmdline: list[str]) -> str | None:
    if not cmdline:
        return None
    if "-m" in cmdline:
        idx = cmdline.index("-m")
        if idx + 1 < len(cmdline):
            mod = cmdline[idx + 1]
            root = mod.split(".")[0]
            if root in {"uvicorn", "gunicorn"}:
                target = _first_non_flag_target(cmdline[idx + 2 :])
                if target:
                    return target.split(":", 1)[0].split(".")[0]
            return root
    for arg in cmdline:
        if arg.endswith(".py"):
            p = Path(arg)
            script = p.stem
            parent = p.parent.name
            if parent and parent not in {"src", "app", "lib", "bin", "home"}:
                return f"{parent}/{script}"
            return script
    for arg in cmdline:
        if arg.startswith("-"):
            continue
        p = Path(arg)
        if p.is_dir():
            name = parse_pyproject_name(p / "pyproject.toml")
            if name:
                return name
            return p.name
    return None


def extract_node_script_name(cmdline: list[str]) -> str | None:
    for arg in cmdline[1:]:
        if arg.startswith("-"):
            continue
        if arg.endswith((".js", ".mjs", ".cjs", ".ts")):
            return Path(arg).stem
    return None


def extract_package_json_name(cmdline: list[str], cwd: str | None) -> str | None:
    candidates: list[Path] = []
    if cwd:
        candidates.append(Path(cwd))
    for arg in cmdline:
        if arg.startswith("-"):
            continue
        p = Path(arg)
        if p.suffix in {".js", ".mjs", ".cjs", ".ts"}:
            candidates.append(p.parent)
        elif p.is_dir():
            candidates.append(p)
    for base in candidates:
        found = _find_up(base, "package.json", max_up=4)
        if found:
            return parse_package_json_name(found)
    return None


def extract_jar_name(cmdline: list[str]) -> str | None:
    for i, arg in enumerate(cmdline):
        if arg == "-jar" and i + 1 < len(cmdline):
            return Path(cmdline[i + 1]).stem
        if arg.endswith(".jar"):
            return Path(arg).stem
    return None


def extract_ruby_name(cmdline: list[str]) -> str | None:
    for arg in cmdline[1:]:
        if arg.endswith(".rb"):
            return Path(arg).stem
    return None


def _first_non_flag_target(args: Iterable[str]) -> str | None:
    for arg in args:
        if arg.startswith("-"):
            continue
        return arg
    return None


def smart_truncate_path(path: str | None, max_len: int = 45) -> str | None:
    if not path:
        return None
    path = re.sub(r"^/home/[^/]+/", "~/", path)
    if len(path) <= max_len:
        return path
    parts = list(Path(path).parts)
    if len(parts) < 3:
        return path[-max_len:]
    keep_start = parts[0].rstrip("/") or "/"
    keep_end = "/".join(parts[-2:])
    truncated = f"{keep_start}/.../{keep_end}"
    if len(truncated) > max_len:
        return f".../{parts[-1]}"
    return truncated


def relative_time_from_epoch(ts: float | None, now: float | None = None) -> str:
    if ts is None:
        return "-"
    now = time.time() if now is None else now
    delta = max(0, int(now - ts))
    if delta < 5:
        return "just now"
    if delta < 60:
        return f"{delta}s ago"
    m, s = divmod(delta, 60)
    if m < 60:
        return f"{m}m ago"
    h, m = divmod(m, 60)
    if h < 24:
        return f"{h}h {m}m ago" if m else f"{h}h ago"
    d, h = divmod(h, 24)
    if d < 7:
        return f"{d} day{'s' if d != 1 else ''} ago" if h == 0 else f"{d}d {h}h ago"
    return f"{d} days ago"


def _find_up(base: Path, target: str, max_up: int = 4) -> Path | None:
    cur = base.expanduser()
    for _ in range(max_up + 1):
        candidate = cur / target
        if candidate.exists():
            return candidate
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


@lru_cache(maxsize=256)
def parse_package_json_name(path: Path) -> str | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    name = data.get("name")
    return str(name) if isinstance(name, str) and name.strip() else None


@lru_cache(maxsize=256)
def parse_pyproject_name(path: Path) -> str | None:
    try:
        import tomllib

        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    proj = data.get("project") if isinstance(data, dict) else None
    if isinstance(proj, dict):
        name = proj.get("name")
        if isinstance(name, str) and name.strip():
            return name
    return None
