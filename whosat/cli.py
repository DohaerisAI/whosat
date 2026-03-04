"""CLI entry point — TUI (default), port lookup, ls, kill subcommands."""

from __future__ import annotations

import argparse
import sys
import time

from . import __version__


# ── Helpers ──────────────────────────────────────────────────────


def _collect(docker_enabled: bool):
    """Collect a snapshot using the existing data layer."""
    from whosat.services.refresh import RefreshConfig, collect_snapshot

    config = RefreshConfig(docker_enabled=docker_enabled)
    return collect_snapshot(config)


def _find_rows_by_port(rows, port: int):
    """Return rows that have a binding on the given port."""
    return [r for r in rows if any(p.port == port for p in r.ports)]


# ── Subcommands ──────────────────────────────────────────────────


def cmd_port_lookup(port: int, *, as_json: bool, docker_enabled: bool) -> int:
    """whosat <port> — find what's on a port."""
    from whosat.cli_output import (
        print_json,
        print_port_not_found,
        print_port_oneliner,
        process_to_dict,
    )

    snap = _collect(docker_enabled)
    matches = _find_rows_by_port(snap.processes, port)

    if not matches:
        if as_json:
            print_json({"port": port, "found": False, "processes": []})
        else:
            print_port_not_found(port)
        return 1

    if as_json:
        now = snap.collected_at
        print_json({
            "port": port,
            "found": True,
            "processes": [process_to_dict(r, now) for r in matches],
        })
    else:
        for row in matches:
            print_port_oneliner(row, port)
    return 0


def cmd_ls(
    *,
    sort_by: str,
    sort_order: str,
    as_json: bool,
    docker_enabled: bool,
) -> int:
    """whosat ls — list all ports/processes."""
    from whosat.cli_output import print_json, print_process_table, snapshot_to_dict
    from whosat.services.conflicts import detect_conflicts
    from whosat.services.filters import sort_rows

    snap = _collect(docker_enabled)

    if as_json:
        snap.processes = sort_rows(snap.processes, sort_by, sort_order)  # type: ignore[arg-type]
        print_json(snapshot_to_dict(snap))
        return 0

    rows = sort_rows(snap.processes, sort_by, sort_order)  # type: ignore[arg-type]
    conflicts = detect_conflicts(snap.processes)
    print_process_table(rows, sort_by, sort_order, conflicts)
    return 0


def cmd_kill(
    port: int,
    *,
    force: bool,
    sig_name: str | None,
    as_json: bool,
    docker_enabled: bool,
) -> int:
    """whosat kill <port> — find + confirm + kill."""
    import psutil

    from whosat.cli_output import print_json, print_kill_target
    from whosat.services.actions import pid_exists, send_kill, send_term

    snap = _collect(docker_enabled)
    matches = _find_rows_by_port(snap.processes, port)

    if not matches:
        if as_json:
            print_json({"port": port, "killed": False, "error": "Nothing listening"})
        else:
            from whosat.cli_output import print_port_not_found
            print_port_not_found(port)
        return 1

    row = matches[0]
    if row.pid is None:
        msg = f"Cannot kill: no PID for {row.name} on port {port}"
        if as_json:
            print_json({"port": port, "killed": False, "error": msg})
        else:
            from rich.console import Console
            Console(stderr=True, highlight=False).print(f"[red]{msg}[/]")
        return 1

    # Walk up to the root parent that owns this port (e.g. uvicorn master, not worker)
    target_pid = row.pid
    target_name = row.name
    try:
        proc = psutil.Process(row.pid)
        parent = proc.parent()
        while parent and parent.pid > 1:
            try:
                parent_name = parent.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
            # Check if parent is related (same binary lineage, not init/systemd/bash)
            if parent_name in ("init", "systemd", "bash", "zsh", "sh", "fish", "tmux", "screen", "sshd", "sudo"):
                break
            target_pid = parent.pid
            target_name = parent_name
            parent = parent.parent()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

    # Determine signal
    use_sigkill = False
    if sig_name:
        sig_upper = sig_name.upper().removeprefix("SIG")
        if sig_upper == "KILL":
            use_sigkill = True
        elif sig_upper != "TERM":
            msg = f"Unsupported signal: {sig_name} (use SIGTERM or SIGKILL)"
            if as_json:
                print_json({"port": port, "killed": False, "error": msg})
            else:
                from rich.console import Console
                Console(stderr=True, highlight=False).print(f"[red]{msg}[/]")
            return 1

    # Show target (may differ from original match if we found a parent)
    if not force and not as_json:
        from rich.console import Console
        con = Console(highlight=False)
        if target_pid != row.pid:
            con.print(
                f"[dim]Worker pid {row.pid} is a child of[/] [bold]{target_name}[/] [dim](pid {target_pid})[/]"
            )
        print_kill_target(row, port)
        try:
            answer = input(f"Kill {target_name} (pid {target_pid})? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 130
        if answer not in ("y", "yes"):
            print("Cancelled.")
            return 0

    # Send signal — kill the whole process group when possible
    escalated = False

    def _kill_tree(pid: int, sigkill: bool):
        """Kill process and all its children."""
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            children = []
        # Kill parent first, then children
        result = send_kill(pid) if sigkill else send_term(pid)
        for child in children:
            try:
                if sigkill:
                    child.kill()
                else:
                    child.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return result

    if use_sigkill:
        result = _kill_tree(target_pid, sigkill=True)
    else:
        result = _kill_tree(target_pid, sigkill=False)
        if result.ok:
            time.sleep(2)
            result.still_running = pid_exists(target_pid)
            # Offer escalation to SIGKILL if still running
            if result.still_running and not as_json and not force:
                try:
                    answer = input("Process still running. Force kill (SIGKILL)? [y/N] ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print()
                    return 130
                if answer in ("y", "yes"):
                    result = _kill_tree(target_pid, sigkill=True)
                    escalated = True

    final_sig = "SIGKILL" if (use_sigkill or escalated) else "SIGTERM"

    if as_json:
        print_json({
            "port": port,
            "pid": target_pid,
            "name": target_name,
            "killed": result.ok,
            "signal": final_sig,
            "still_running": result.still_running,
            "message": result.message,
        })
    else:
        from rich.console import Console
        con = Console(highlight=False)
        if result.ok:
            con.print(f"[green]Sent {final_sig} to {target_name} (pid {target_pid})[/]")
            if result.still_running and not escalated:
                con.print(f"[yellow]Process still running after {final_sig}[/]")
        else:
            con.print(f"[red]{result.message}[/]")

    return 0 if result.ok else 1


# ── Argument parser ──────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="whosat",
        description="Ports/processes dashboard — TUI, CLI, or JSON",
    )
    parser.add_argument("--version", action="version", version=f"whosat {__version__}")
    parser.add_argument("--json", action="store_true", dest="json", help="output as JSON")
    parser.add_argument("--no-docker", action="store_true", help="disable Docker integration")
    parser.add_argument("--debug", action="store_true", help="enable debug logging")

    sub = parser.add_subparsers(dest="command")

    # whosat ls
    ls_parser = sub.add_parser("ls", help="list all ports/processes (non-interactive)")
    ls_parser.add_argument("--sort", default="port", choices=["port", "name", "created", "cpu", "mem"])
    ls_parser.add_argument("--desc", action="store_true", help="sort descending")
    ls_parser.add_argument("--json", action="store_true", dest="json", help="output as JSON")

    # whosat kill <port>
    kill_parser = sub.add_parser("kill", help="kill process on a port")
    kill_parser.add_argument("port", type=int, help="port number")
    kill_parser.add_argument("--force", action="store_true", help="skip confirmation")
    kill_parser.add_argument("--signal", dest="sig", default=None, help="SIGTERM (default) or SIGKILL")
    kill_parser.add_argument("--json", action="store_true", dest="json", help="output as JSON")

    return parser


# ── Entry point ──────────────────────────────────────────────────


def _extract_port_arg(raw: list[str]) -> tuple[int | None, list[str]]:
    """If first non-flag arg is a bare port number, extract it and return remaining args.

    Returns (port, remaining_args) or (None, original_args).
    """
    # Find first non-flag argument
    for i, arg in enumerate(raw):
        if arg.startswith("-"):
            continue
        # First positional — check if it's a port number
        if arg.isdigit():
            n = int(arg)
            if 1 <= n <= 65535:
                remaining = raw[:i] + raw[i + 1:]
                return n, remaining
            else:
                return None, raw  # let main() handle the error
        break  # first positional isn't a number, stop looking
    return None, raw


def main(argv: list[str] | None = None) -> int:
    raw = argv if argv is not None else sys.argv[1:]

    # Pre-check: bare port number → extract and handle separately
    # e.g. `whosat 3000` or `whosat 3000 --json` or `whosat --json 3000`
    port_arg, remaining = _extract_port_arg(list(raw))

    if port_arg is not None:
        # Parse global flags only (no subcommand)
        parser = build_parser()
        args = parser.parse_args(remaining)
        docker_enabled = not args.no_docker
        as_json = args.json
        try:
            return cmd_port_lookup(port_arg, as_json=as_json, docker_enabled=docker_enabled)
        except KeyboardInterrupt:
            return 130

    # Check for invalid bare number (>65535)
    for arg in raw:
        if arg.startswith("-"):
            continue
        if arg.isdigit():
            n = int(arg)
            if n < 1 or n > 65535:
                print(f"whosat: invalid port number: {n} (must be 1-65535)", file=sys.stderr)
                return 1
        break

    parser = build_parser()
    args = parser.parse_args(raw)

    docker_enabled = not args.no_docker
    as_json = args.json

    try:
        if args.command == "ls":
            return cmd_ls(
                sort_by=args.sort,
                sort_order="desc" if args.desc else "asc",
                as_json=as_json,
                docker_enabled=docker_enabled,
            )

        if args.command == "kill":
            return cmd_kill(
                args.port,
                force=args.force,
                sig_name=args.sig,
                as_json=as_json,
                docker_enabled=docker_enabled,
            )

        # No subcommand: --json → ls --json, otherwise → TUI
        if as_json:
            return cmd_ls(
                sort_by="port",
                sort_order="asc",
                as_json=True,
                docker_enabled=docker_enabled,
            )

        # Default: launch TUI
        from .app import WhosatApp
        app = WhosatApp(docker_enabled=docker_enabled, debug=args.debug)
        app.run()
        return 0

    except KeyboardInterrupt:
        return 130
