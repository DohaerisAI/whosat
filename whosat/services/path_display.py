from __future__ import annotations

import os
from pathlib import Path

from whosat.types import ProcessRecord


def get_display_path(row: ProcessRecord) -> str | None:
    if row.exe:
        return row.exe
    for arg in row.cmdline:
        if _looks_like_path(arg):
            return _normalize(arg)
    if row.cwd:
        return row.cwd
    return None


def _looks_like_path(arg: str) -> bool:
    if not arg or arg.startswith('-'):
        return False
    if '/' in arg or arg.startswith('~'):
        return True
    return any(arg.endswith(ext) for ext in ('.py', '.js', '.ts', '.rb', '.jar', '.sh', '.exe'))


def _normalize(p: str) -> str:
    try:
        p2 = os.path.expanduser(p)
        return str(Path(p2).resolve()) if os.path.exists(p2) else os.path.abspath(p2)
    except Exception:
        return p
