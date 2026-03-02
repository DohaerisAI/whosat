# whosat

A terminal dashboard for viewing listening ports, processes, and Docker containers. Like `htop` but focused on network ports.

Built with [Textual](https://github.com/Textualize/textual) for a rich TUI experience.

## Features

- **Port & Process Monitoring** -- See all listening ports with owning processes, CPU/memory usage, and uptime
- **Memory View** -- System-wide process memory usage with GPU memory tracking (NVIDIA)
- **Docker Integration** -- Optional container monitoring alongside system processes
- **Group & Flat Views** -- Group processes by name or view as a flat list
- **Detail Panel** -- Expand any process to see full network info, open ports, resource usage, and CPU sparkline
- **Actions** -- Ping, curl, and kill processes directly from the TUI
- **Live Refresh** -- Configurable auto-refresh (15s / 30s / 1m / 2m / off)
- **Theming** -- 6 built-in themes (matrix, nord, dracula, tokyo-night, gruvbox, solarized)
- **Search & Filter** -- Search by process name, port, or IP; filter by scope (system / docker)
- **Keyboard Driven** -- Full keyboard navigation with vim-style shortcuts
- **Cross-platform** -- Linux, macOS, and WSL2

## Install

```bash
pip install whosat
```

With Docker support:

```bash
pip install 'whosat[docker]'
```

## Usage

```bash
whosat
```

That's it. `whosat` will scan your system and display all listening ports and their processes.

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `1` / `2` | Switch to Ports / Memory view |
| `Up` / `Down` | Navigate rows |
| `Enter` | Expand/collapse row + open detail panel |
| `Esc` | Close detail panel / modal / clear search |
| `/` | Focus search |
| `R` | Refresh data |
| `G` | Toggle group/flat view |
| `K` | Kill selected process |
| `S` | Cycle scope (ALL / SYS / DOCKER) |
| `T` | Cycle theme |
| `Y` | Copy IP:PORT to clipboard |
| `Q` | Quit |

## Configuration

On first run, whosat creates `~/.whosat/config.toml` with default categories and settings.

```toml
theme = "matrix"
refresh_interval = 30

[[categories]]
name = "python"
icon = "snake"
section = "System"
match = ["python3", "python", "uvicorn", "gunicorn", "celery"]

# Add your own:
# [[port_names]]
# port = 8020
# name = "My App"
# icon = "robot"
```

## Requirements

- Python 3.10+
- Linux, macOS, or WSL2
- Optional: Docker SDK for container monitoring
- Optional: NVIDIA GPU for GPU memory tracking in memory view

## License

MIT
