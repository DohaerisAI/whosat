from __future__ import annotations

import math


def fmt_bytes(value: int | None) -> str:
    if value is None:
        return "-"
    if value < 0:
        return "-"
    units = ["B", "KB", "MB", "GB", "TB"]
    n = float(value)
    for unit in units:
        if n < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(n)} {unit}"
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{value} B"


def fmt_percent(value: float | None, digits: int = 1) -> str:
    if value is None or math.isnan(value):
        return "-"
    return f"{value:.{digits}f}%"


def fmt_uptime(seconds: int | float | None) -> str:
    if seconds is None:
        return "-"
    s = int(max(0, seconds))
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, _ = divmod(s, 60)
    if d:
        return f"{d}d {h}h {m}m"
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


def fmt_clock_epoch(ts: float | None) -> str:
    if ts is None:
        return "-"
    import datetime as _dt

    return _dt.datetime.fromtimestamp(ts).strftime("%H:%M:%S")


def safe_text(value: object | None) -> str:
    if value is None:
        return "-"
    return str(value)
