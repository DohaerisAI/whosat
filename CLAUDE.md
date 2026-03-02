# AGENTS.md — whosat development guide
# Read this file completely before touching any code.
# Then read the full codebase. Then act.

## What is whosat
A Python TUI tool (pip install whosat) that shows all running ports, processes,
and Docker containers on your system. Like htop but focused on network ports.
Command: `whosat`
Stack: Python 3.10+ | Textual | psutil | docker SDK (optional)

---

## Design reference
`portwatch-terminal.html` — open this in a browser. It is the pixel-level UI target.
Every color, layout, component comes from this file. Never guess design decisions.
If it's in the HTML, match it exactly. If it's not in the HTML, ask before inventing.

---

## Color system (use these exact values in whosat.tcss)

```css
$bg:      #0a0c0f;   /* main background */
$bg1:     #0e1117;   /* panel/header background */
$bg2:     #13181f;   /* input/button background */
$bg3:     #1a2030;   /* subtle highlights */
$border:  #1e2a38;   /* default borders */
$border2: #243040;   /* stronger borders */

$green:   #00ff88;   /* online, active, logo, accent */
$green2:  #00cc6a;   /* dimmer green */
$cyan:    #00d4ff;   /* IPs, values, SYS tag */
$yellow:  #ffd060;   /* port numbers, warnings */
$red:     #ff4466;   /* offline, errors, kill button */
$purple:  #b084ff;   /* docker scope */
$orange:  #ff8844;   /* secondary warnings */

$text:    #c8d8e8;   /* primary text */
$text2:   #8aa0b0;   /* secondary text */
$text3:   #5a6a7a;   /* dim labels */
$dim:     #3a4a5a;   /* very dim elements */
$muted:   #4a5a6a;   /* muted elements */
```

---

## Full layout (match exactly)

```
┌──────────────────────────────────────────────────────────────────┐ 1 row
│ HEADER BAR                                                       │
├──────────────────────────────────────────────────────────────────┤ 4 rows
│ SYSINFO BAR                                                      │
├──────────────────────────────────────────────────────────────────┤ 3 rows
│ TOOLBAR                                                          │
├──────────────────────────────────────────────────────────────────┤ 1 row
│ REFRESH PROGRESS BAR (thin, 1 row)                               │
├─────────────┬──────────────────────────────┬─────────────────────┤ flex:1
│             │                              │                     │
│  SIDEBAR    │  MAIN CONTENT                │  DETAIL PANEL       │
│  210px      │  flex fill                   │  280px (toggleable) │
│             │                              │                     │
├─────────────┴──────────────────────────────┴─────────────────────┤ 1 row
│ FOOTER NAV BAR                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Component specs

### HEADER BAR
```
● WHOSAT  [SYS] [DOCKER]  ● LIVE  ● PORTS 9  ● DOWN 0  ● DOCKER 0  REFRESH [30s ▾]  ↻ REFRESH  21:31:53
```
- `WHOSAT` bold $green
- `[SYS]` pill: bg=rgba(0,212,255,0.1) border=$cyan color=$cyan
- `[DOCKER]` pill: bg=rgba(176,132,255,0.1) border=$purple color=$purple
- `● LIVE` blinking dot $green + label $text3
- `● PORTS N` dot=$green, label=$text3, value=$green
- `● DOWN N` dot=$yellow (blink if >0), value=$yellow
- `● DOCKER N` dot=$purple, value=$purple
- Refresh selector: bg=$bg2 border=$border color=$text2, options: 15s/30s/1m/2m/off
- Clock: right-aligned, $text3, updates every second

### SYSINFO BAR (8 columns, border-right between each)
Each column: dim label top (9px uppercase $text3) | bright value middle | subtext bottom (9px $text3)

| Column | Value color | Subtext |
|--------|-------------|---------|
| HOSTNAME | $green | OS version |
| CPU CORES | $cyan | mini per-core bars (8px wide each, color by load: green<40% yellow<70% red>70%) |
| CPU LOAD | $yellow if >50% else $green | avg load / 1m |
| MEMORY | $cyan | mini horizontal progress bar (gradient: $cyan → $purple) |
| UPTIME | $green | since date |
| CONTAINERS | $purple | X stopped |
| PROCESSES | $text | X w/ ports |
| LOCAL IP | $cyan | interface names |

### TOOLBAR
```
[$> search process, port, ip...]   [ALL|SYS|DOCKER]   SORT [port ▾]  [ASC|DESC]   [⊞ GROUP VIEW] [≡ FLAT VIEW]
```
- Search: bg=$bg2 border=$border2, prefix `$>` in $green, placeholder $text3
- Scope toggle: ALL=rgba(0,255,136,0.12)/$green, SYS=$cyan tint, DOCKER=$purple tint
- Active scope has matching color border
- Sort select: bg=$bg2 border=$border options: port/name/created/cpu/mem
- ASC/DESC: active one has $green bg tint
- GROUP/FLAT: bordered buttons, active has $green border

### REFRESH PROGRESS BAR
- Height: 1 row (use a Progress widget or custom bar)
- Background: $bg3
- Fill: linear gradient $green → $cyan
- Fills left to right over the refresh interval
- Resets to 0 when data refreshes

### SIDEBAR (210px wide)

**Server card at top:**
```
┌─ SERVER ──────────────────┐
│ SCITHLT0453               │
│ 192.168.1.x               │
│ Linux 5.15 WSL2           │
│ 💾 15.4 GB    ⏱ 2h 8m    │
│ 🔌 9 ports    🐳 0 cont   │
│ 💿 169.8/1006.9 GB        │
└───────────────────────────┘
```
- Border: $border, bg: $bg1
- Hostname: $green bold
- IP: $cyan
- OS: $text3 small
- Stats: icon + value in $text2

**Category sections:**
- Section headers: `CATEGORIES` `SYSTEM` `DATABASE` `DOCKER` — 9px uppercase $text3, line after
- Each item: icon + name + count badge
- Inactive: $text2, left border transparent
- Active: $green text, left border 2px $green, bg rgba(0,255,136,0.05)
- Mini status row under each: `6 up` green pill, `1 warn` yellow pill, `1 down` red pill

**Bottom quick stats:**
```
TCP: 38   UDP: 4
IPv4: 39  IPv6: 3
```

### MAIN CONTENT — GROUP VIEW (default)

**Group header row:**
```
▼  🐍  python3     7 processes · last seen 2s ago     [SYS]  [7 procs]  [6 online]  [1 warn]
```
- Chevron ▼ (open) or ▶ (closed), click to toggle
- Icon + bold name $text
- Meta subtitle $text3 small
- Right pills:
  - `[SYS]` $cyan tint / `[DOCKER]` $purple tint
  - `[N procs]` $bg3 $text3
  - `[N online]` rgba(0,255,136,0.1) $green
  - `[N warn]` rgba(255,208,96,0.1) $yellow
  - `[N down]` rgba(255,68,102,0.1) $red

**Table header (inside each group):**
```
   PORT    NAME/CMD    IP ADDRESS    PROTO    STATUS    CPU/MEM    UPTIME
```
9px uppercase $text3

**Process row (collapsed):**
```
▶  8000   uvicorn [FastAPI]   0.0.0.0   TCP/IPv4   ● ONLINE   0.1%/1.2GB   2h 8m
```
- Expand chevron ▶
- PORT: $yellow bold, monospace
- NAME: $text, tag badge in $bg3/$text3 bordered
- IP: $text3 monospace
- PROTO: $text3
- STATUS badge:
  - ONLINE: bg=rgba(0,255,136,0.1) border=rgba(0,255,136,0.2) color=$green, dot blinks
  - WARN: yellow tints, dot blinks faster
  - OFFLINE: red tints, dot static
- CPU%: $text2, MEM: $text3 below it
- UPTIME: $text3
- Hover: left 2px border $green, bg rgba(0,255,136,0.03)

**Process row (expanded) — 3 column grid:**
```
┌─ OPEN PORTS ──────┬─ PROCESS INFO ────┬─ NETWORK ─────────┐
│ [8000 TCP]        │ PID    12847      │ Connections  14    │
│ [8001 TCP]        │ User   adwitiya   │ RX/TX  2.4/8.1MB  │
│ [5353 UDP]        │ Cmd    python3... │ Bind   0.0.0.0:8k  │
└───────────────────┴───────────────────┴───────────────────┘
```
- Port chips: TCP=rgba(255,208,96,0.12)/$yellow bordered, UDP=$cyan tinted
- Labels $text3, values $text2, highlighted values $cyan
- bg: $bg1, border-bottom: $border

### FLAT VIEW
Same rows but no group headers. All processes in one flat list.

### DETAIL PANEL (280px, right side)

Opens when row clicked. Closes with Esc or ✕ button.

```
[ ✕ close ]
──────────────────────────────
🐍 uvicorn   pid 12847   ● ONLINE   sys
──────────────────────────────
STATUS
  State       ● ONLINE
  Uptime      2h 8m
  Restarts    0
  Last check  2s ago

NETWORK
  Bind        0.0.0.0:8880
  Local IP    192.168.1.x
  Protocol    TCP/IPv4
  Connections 14 active
  RX / TX     2.4 MB / 8.1 MB

ALL OPEN PORTS
  [8880 TCP]  [8881 TCP]

CPU USAGE (LAST 60s)
  [Textual Sparkline widget — green — 30px height]
  Store last 60 cpu_percent readings per process in collections.deque(maxlen=60)
  Update every refresh cycle

RESOURCES
  CPU       0.1%
  Memory    1.2 GB (8.0%)
  Threads   26
  FDs       25

PATH
  /home/adwitiya24/.../server.py   [E to expand]
  When E pressed: show full path, [Y to copy]

CMD
  /home/adwitiya24/.nvm/v20/bin/uvicorn
  main:app --host 0.0.0.0 --port 8880
  (word-wrapped, never truncated, $text2 monospace small)

ACTIONS
  [PING]   [CURL]   [KILL]
```

Section headers: 9px uppercase $text3, border-bottom $border
Labels: $text3, Values: $text2, Highlighted values: $cyan
KILL button: $red border, $red text

---

## Actions — implement exactly these 3

### PING
```python
def action_ping(host: str):
    # Strip port if present, use IP only
    # Command: ping -c 4 {host}
    # Open a modal overlay (Textual Screen)
    # Show live output as it streams line by line
    # Parse and highlight RTT line at bottom in $cyan
    # [Esc] or [Q] closes modal
```

Modal layout:
```
┌─ PING 192.168.1.x ──────────────────── [Q close] ─┐
│ PING 192.168.1.x: 56 data bytes                    │
│ 64 bytes from 192.168.1.x: icmp_seq=0 ttl=64...   │
│ 64 bytes from 192.168.1.x: icmp_seq=1 ttl=64...   │
│ ...                                                │
│ ─────────────────────────────────────────────────  │
│ rtt min/avg/max = 0.1/0.2/0.3 ms                  │
└────────────────────────────────────────────────────┘
```

### CURL
```python
def action_curl(host: str, port: int):
    # Try HTTP first, then HTTPS
    # Command: curl -sv --max-time 5 http://{host}:{port}
    # Open modal overlay
    # Show: status line (colored: 2xx=green, 4xx=yellow, 5xx=red)
    # Then headers in dim color
    # Then truncated body (first 500 chars)
    # [Esc] or [Q] closes
```

Modal layout:
```
┌─ CURL http://0.0.0.0:8880 ───────────── [Q close] ─┐
│ ● 200 OK                                            │
│ ─────────────────────────────────────────────────   │
│ content-type: application/json                      │
│ server: uvicorn                                     │
│ ─────────────────────────────────────────────────   │
│ {"status": "ok", "version": "1.0"}                 │
└─────────────────────────────────────────────────────┘
```

### KILL
```python
def action_kill(pid: int, name: str):
    # Step 1: Show confirmation modal
    # "Kill {name} (pid {pid})?" [Yes] [No]
    # 
    # Step 2 on Yes: send SIGTERM
    # import signal, os
    # os.kill(pid, signal.SIGTERM)
    #
    # Step 3: wait 3 seconds, check if still alive
    # if still alive: show "Process still running. Force kill?" [SIGKILL] [Cancel]
    #
    # Step 4: flash footer message
    # "Sent SIGTERM to {name} (pid {pid})" in $yellow
    # or "Killed {name} (pid {pid})" in $red if SIGKILL
    # or "Kill failed: permission denied" in $red
```

---

## Data collection — use ss as primary source

```python
# Linux/WSL: ss -tlnpH and ss -ulnpH
# macOS: lsof -iTCP -iUDP -sTCP:LISTEN -nP
# Never use psutil connections() as primary — misses other-user processes

def get_ports():
    if sys.platform == "darwin":
        return get_ports_lsof()
    else:
        return get_ports_ss()

def get_ports_ss():
    # Run ss -tlnpH and ss -ulnpH
    # Parse: state, recv-q, send-q, local-addr:port, peer, process
    # Group same port+process: one entry with both TCP and UDP if both exist
    # Enrich with psutil using PID for cpu/mem/threads/cmdline
    # Handle AccessDenied gracefully: show port, mark fields as "-"
```

**Deduplication rule:** same port + same process name = ONE row. Show protocol as `TCP+UDP` or individual badges.

**Well-known port names (fallback when PID unavailable):**
```python
WELL_KNOWN = {
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
    8080: ("http-alt", "🌐", "Web"),
}
```

**Unknown ports:** group into "Other" category, collapsed by default.
If >3 unknown ports detected, show footer hint: `N uncategorized ports — edit ~/.whosat/config.toml`

---

## Config file (~/.whosat/config.toml)

Created automatically on first run with these defaults:

```toml
theme = "matrix"
refresh_interval = 30

[[categories]]
name = "python"
icon = "🐍"
section = "System"
match = ["python3", "python", "uvicorn", "gunicorn", "celery", "fastapi"]

[[categories]]
name = "node"
icon = "⬡"
section = "System"
match = ["node", "nodejs", "npm", "bun", "deno"]

[[categories]]
name = "nginx"
icon = "🌐"
section = "Web"
match = ["nginx", "nginx: master", "nginx: worker", "apache2", "httpd"]

[[categories]]
name = "postgres"
icon = "🐘"
section = "Database"
match = ["postgres", "postgresql"]

[[categories]]
name = "mysql"
icon = "🐬"
section = "Database"
match = ["mysqld", "mysql", "mariadb"]

[[categories]]
name = "redis"
icon = "⚡"
section = "Database"
match = ["redis-server", "redis"]

[[categories]]
name = "mongodb"
icon = "🍃"
section = "Database"
match = ["mongod", "mongos"]

[[categories]]
name = "docker"
icon = "🐳"
section = "Docker"
match = ["__docker__"]  # special flag for docker containers

# User custom port names — highest priority
# [[port_names]]
# port = 8020
# name = "My App"
# icon = "🤖"
```

**Match rules:**
- Exact: `"redis-server"`
- Prefix wildcard: `"nginx*"`
- Contains: `"*spring*"`
- Cmdline: `"cmd:uvicorn"` — checks if string appears in full cmdline args

**Config reload:** `R` key reloads config without restart.

---

## Theme system

`T` key cycles through themes. Active theme stored in config.

```python
THEMES = {
    "matrix": {
        "accent": "#00ff88", "port": "#ffd060",
        "bg": "#0a0c0f", "text": "#c8d8e8"
    },
    "nord": {
        "accent": "#88c0d0", "port": "#ebcb8b",
        "bg": "#2e3440", "text": "#eceff4"
    },
    "dracula": {
        "accent": "#bd93f9", "port": "#f1fa8c",
        "bg": "#282a36", "text": "#f8f8f2"
    },
    "tokyo-night": {
        "accent": "#7aa2f7", "port": "#e0af68",
        "bg": "#1a1b26", "text": "#c0caf5"
    },
    "gruvbox": {
        "accent": "#b8bb26", "port": "#fabd2f",
        "bg": "#282828", "text": "#ebdbb2"
    },
    "solarized": {
        "accent": "#2aa198", "port": "#b58900",
        "bg": "#002b36", "text": "#839496"
    },
}
```

---

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| `↑` `↓` | Navigate rows |
| `Enter` | Expand/collapse row + open detail panel |
| `Escape` | Close detail panel / close modal / clear search |
| `/` | Focus search input |
| `R` | Manual refresh + reload config |
| `G` | Toggle group/flat view |
| `K` | Kill selected process |
| `Tab` | Cycle focus: sidebar → table → detail |
| `S` | Cycle scope ALL → SYS → DOCKER |
| `T` | Cycle theme |
| `E` | Expand/collapse path in detail panel |
| `Y` | Copy IP:PORT to clipboard (when row focused) |
| `Q` | Quit |
| `?` | Help overlay |

---

## Footer nav bar (always visible, 1 row)

```
[↑↓] navigate  [Enter] expand  [K] kill  [/] search  [R] refresh  [G] group  [T] theme  [Q] quit        next 12s · v0.1.0
```

- Keys in dim bordered boxes: bg=$bg2 border=$border2 color=$text3
- Labels: $text3
- Right side: `next Xs` in $cyan, `· v0.1.0` in $text3
- Countdown ticks every second
- Temporarily replaced (3s) by status messages when actions occur:
  - Success: $green message left side
  - Error: $red message left side
  - Then restores to shortcuts automatically

---

## Clipboard (cross-platform)

```python
def copy_to_clipboard(text: str) -> bool:
    if sys.platform == "darwin":
        cmds = [["pbcopy"]]
    elif sys.platform == "win32":
        cmds = [["clip"]]
    else:
        cmds = [
            ["clip.exe"],                          # WSL2
            ["xclip", "-selection", "clipboard"],  # X11
            ["xsel", "--clipboard", "--input"],    # X11 alt
            ["wl-copy"],                           # Wayland
        ]
    for cmd in cmds:
        try:
            subprocess.run(cmd, input=text.encode(),
                         timeout=2, check=True, capture_output=True)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError,
                subprocess.TimeoutExpired):
            continue
    return False
```

---

## Docker (optional, graceful fallback)

```python
try:
    import docker
    client = docker.from_env()
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    # footer hint: "pip install whosat[docker] to enable Docker"
except docker.errors.DockerException:
    DOCKER_AVAILABLE = False
    # footer hint: "Docker daemon not running"
```

Also try subprocess `docker ps` as fallback if SDK unavailable.

---

## CPU Sparkline

```python
from collections import deque

# Per-process rolling buffer
cpu_history: dict[int, deque] = {}  # pid → deque(maxlen=60)

def update_sparkline(pid: int, cpu_percent: float):
    if pid not in cpu_history:
        cpu_history[pid] = deque([0.0] * 60, maxlen=60)
    cpu_history[pid].append(cpu_percent)

# In detail panel widget:
# Use Textual's Sparkline widget
# sparkline = Sparkline(data=list(cpu_history[pid]), summary_function=max)
# Color: $green
```

---

## Platform support

| Platform | Port scan | Clipboard | Logs |
|----------|-----------|-----------|------|
| Linux | `ss` | xclip/xsel/wl-copy | journalctl |
| macOS | `lsof` | pbcopy | log stream |
| WSL2 | `ss` | clip.exe | journalctl |
| Windows | not supported | - | - |

---

## Build sequence — do in this order

1. **Data layer** — `ss`/`lsof` port collection, psutil enrichment, docker optional
2. **Colors + tcss** — apply all CSS vars, nothing unstyled
3. **Header + sysinfo bar** — with cpu mini-bars, memory bar, live clock
4. **Sidebar** — server card, categories, status pills
5. **Main content** — group view with rich headers, process rows with port badges
6. **Refresh progress bar** — thin animated bar
7. **Detail panel** — sparkline, sections, path expand
8. **Footer nav** — shortcuts + countdown
9. **Actions** — PING modal, CURL modal, KILL confirmation
10. **Themes** — T key cycle, config persistence

Screenshot after each step. Do not proceed if current step doesn't match HTML mockup.
