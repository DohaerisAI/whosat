from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from whosat.theme import THEME_ORDER

CONFIG_DIR = Path.home() / '.whosat'
CONFIG_PATH = CONFIG_DIR / 'config.toml'


@dataclass(slots=True)
class PortNameOverride:
    port: int
    name: str
    icon: str | None = None


@dataclass(slots=True)
class WhosatConfig:
    theme: str = 'matrix'
    port_names: list[PortNameOverride] = field(default_factory=list)


def load_config(path: Path = CONFIG_PATH) -> WhosatConfig:
    if not path.exists():
        return WhosatConfig()
    try:
        import tomllib
        data = tomllib.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return WhosatConfig()
    theme = data.get('theme', 'matrix') if isinstance(data, dict) else 'matrix'
    if theme not in THEME_ORDER:
        theme = 'matrix'
    overrides: list[PortNameOverride] = []
    raw_overrides = data.get('port_names', []) if isinstance(data, dict) else []
    if isinstance(raw_overrides, list):
        for item in raw_overrides:
            if not isinstance(item, dict):
                continue
            try:
                port = int(item.get('port'))
                name = str(item.get('name'))
            except Exception:
                continue
            if not name:
                continue
            icon = item.get('icon')
            overrides.append(PortNameOverride(port=port, name=name, icon=str(icon) if icon else None))
    return WhosatConfig(theme=theme, port_names=overrides)


def save_config(cfg: WhosatConfig, path: Path = CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f'theme = "{cfg.theme}"', '']
    for ov in cfg.port_names:
        lines.append('[[port_names]]')
        lines.append(f'port = {ov.port}')
        lines.append(f'name = "{_esc(ov.name)}"')
        if ov.icon:
            lines.append(f'icon = "{_esc(ov.icon)}"')
        lines.append('')
    path.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')


def _esc(s: str) -> str:
    return s.replace('\\', '\\\\').replace('"', '\\"')
