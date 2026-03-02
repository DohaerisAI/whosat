from __future__ import annotations

import shutil
import subprocess


def copy_text(text: str) -> tuple[bool, str]:
    if not text:
        return False, "Nothing to copy"
    commands = [
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
        ["clip.exe"],  # WSL -> Windows clipboard
        ["wl-copy"],
        ["pbcopy"],
        ["clip"],
    ]
    for cmd in commands:
        if shutil.which(cmd[0]) is None:
            continue
        try:
            res = subprocess.run(cmd, input=text, text=True, capture_output=True, timeout=2)
        except Exception:
            continue
        if res.returncode == 0:
            return True, f"Copied via {cmd[0]}"
    return False, "Clipboard not available"
