from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ThemePalette:
    name: str
    bg: str
    panel: str
    panel_alt: str
    border: str
    accent: str
    text: str
    text_secondary: str
    text_dim: str
    warn: str
    danger: str
    docker: str
    port_badge_bg: str
    port_badge_fg: str
    secondary: str


THEMES: dict[str, ThemePalette] = {
    'matrix': ThemePalette('matrix', '#0a0c0f', '#0e1117', '#13181f', '#1e2a38', '#00ff88', '#c8d8e8', '#8aa0b0', '#5a6a7a', '#ffd060', '#ff4466', '#b084ff', '#1a3a2a', '#00ff88', '#00d4ff'),
    'nord': ThemePalette('nord', '#2e3440', '#353c4a', '#3b4252', '#4c566a', '#88c0d0', '#eceff4', '#d8dee9', '#81a1c1', '#ebcb8b', '#bf616a', '#b48ead', '#3b4252', '#88c0d0', '#81a1c1'),
    'dracula': ThemePalette('dracula', '#282a36', '#303341', '#44475a', '#4d5066', '#bd93f9', '#f8f8f2', '#d0d0da', '#a7a7b8', '#f1fa8c', '#ff5555', '#bd93f9', '#44475a', '#bd93f9', '#ff79c6'),
    'tokyo-night': ThemePalette('tokyo-night', '#1a1b26', '#1f2335', '#24283b', '#414868', '#7aa2f7', '#c0caf5', '#a9b1d6', '#565f89', '#e0af68', '#f7768e', '#bb9af7', '#24283b', '#7aa2f7', '#bb9af7'),
    'gruvbox': ThemePalette('gruvbox', '#282828', '#32302f', '#3c3836', '#504945', '#b8bb26', '#ebdbb2', '#d5c4a1', '#928374', '#fabd2f', '#fb4934', '#d3869b', '#3c3836', '#b8bb26', '#fabd2f'),
    'solarized-dark': ThemePalette('solarized-dark', '#002b36', '#073642', '#0b3a46', '#194a55', '#2aa198', '#839496', '#93a1a1', '#657b83', '#b58900', '#dc322f', '#6c71c4', '#073642', '#2aa198', '#268bd2'),
}

THEME_ORDER = list(THEMES.keys())


def get_theme(name: str | None) -> ThemePalette:
    if not name:
        return THEMES['matrix']
    return THEMES.get(name, THEMES['matrix'])


def next_theme_name(current: str) -> str:
    try:
        idx = THEME_ORDER.index(current)
    except ValueError:
        return THEME_ORDER[0]
    return THEME_ORDER[(idx + 1) % len(THEME_ORDER)]
