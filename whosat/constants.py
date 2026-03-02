"""Shared constants for whosat — icon mapping, well-known ports, etc."""

from __future__ import annotations

# Process name → icon mapping.
# ALL icons are 2-cell-wide emoji for consistent alignment.
# Match by lowercased process name. Used by sidebar categories AND process rows.
PROCESS_ICON_MAP: dict[str, str] = {
    # Python
    "python": "\U0001f40d",       # 🐍
    "python3": "\U0001f40d",
    "python3.10": "\U0001f40d",
    "python3.11": "\U0001f40d",
    "python3.12": "\U0001f40d",
    "python3.13": "\U0001f40d",
    "uvicorn": "\U0001f40d",
    "gunicorn": "\U0001f40d",
    "flask": "\U0001f40d",
    "django": "\U0001f40d",
    "fastapi": "\U0001f40d",
    "celery": "\U0001f40d",
    # Node / JS
    "node": "\U0001f4d7",         # 📗
    "nodejs": "\U0001f4d7",
    "npm": "\U0001f4d7",
    "yarn": "\U0001f4d7",
    "bun": "\U0001f4d7",
    "deno": "\U0001f4d7",
    "next-server": "\U0001f4d7",
    "ts-node": "\U0001f4d7",
    # Rust
    "rust": "\U0001f980",         # 🦀
    "cargo": "\U0001f980",
    # Go
    "go": "\U0001f439",           # 🐹
    "golang": "\U0001f439",
    # Java / JVM
    "java": "\u2615\ufe0f",      # ☕️ (with variation selector for 2-cell)
    "jvm": "\u2615\ufe0f",
    "gradle": "\u2615\ufe0f",
    "maven": "\u2615\ufe0f",
    "mvn": "\u2615\ufe0f",
    "kotlin": "\u2615\ufe0f",
    "scala": "\u2615\ufe0f",
    "tomcat": "\u2615\ufe0f",
    # Ruby
    "ruby": "\U0001f48e",         # 💎
    "rails": "\U0001f48e",
    "puma": "\U0001f48e",
    "sidekiq": "\U0001f48e",
    # Databases
    "postgres": "\U0001f418",     # 🐘
    "postgresql": "\U0001f418",
    "mysql": "\U0001f42c",        # 🐬
    "mysqld": "\U0001f42c",
    "mariadb": "\U0001f42c",
    "mongod": "\U0001f343",       # 🍃
    "mongos": "\U0001f343",
    "mongodb": "\U0001f343",
    "redis": "\U0001f525",        # 🔥
    "redis-server": "\U0001f525",
    "sqlite": "\U0001f4be",       # 💾
    "elasticsearch": "\U0001f50d", # 🔍
    # Docker
    "docker": "\U0001f433",       # 🐳
    "dockerd": "\U0001f433",
    "containerd": "\U0001f433",
    "containers": "\U0001f433",
    # Web servers
    "nginx": "\U0001f310",        # 🌐
    "apache": "\U0001f310",
    "apache2": "\U0001f310",
    "httpd": "\U0001f310",
    "caddy": "\U0001f310",
    # Browsers
    "firefox": "\U0001f98a",      # 🦊
    "chrome": "\U0001f310",
    "chromium": "\U0001f310",
    # System services
    "systemd": "\U0001f527",      # 🔧
    "cups": "\U0001f527",         # 🔧
    "cupsd": "\U0001f527",
    "sshd": "\U0001f512",         # 🔒
    "ssh": "\U0001f512",
    "cron": "\U0001f527",         # 🔧
    "crond": "\U0001f527",
    "dbus": "\U0001f527",
    "avahi": "\U0001f527",
    "snapd": "\U0001f4e6",        # 📦
    "resolved": "\U0001f527",
    "networkd": "\U0001f527",
    "udevd": "\U0001f527",
    "journald": "\U0001f527",
    "logind": "\U0001f527",
    # Package managers (as processes)
    "pip": "\U0001f4e6",          # 📦
    "pip3": "\U0001f4e6",
}

# Default fallback — 2-cell emoji
DEFAULT_ICON = "\U0001f4cb"  # 📋


def icon_for_process(name: str) -> str:
    """Look up icon for a process name (case-insensitive)."""
    return PROCESS_ICON_MAP.get(name.lower().strip(), DEFAULT_ICON)
