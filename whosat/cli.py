from __future__ import annotations

import argparse

from . import __version__
from .app import WhosatApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="whosat", description="Ports/processes TUI dashboard")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    parser.add_argument("--debug", action="store_true", help="enable debug logging")
    parser.add_argument("--no-docker", action="store_true", help="disable Docker integration")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(__version__)
        return 0
    app = WhosatApp(docker_enabled=not args.no_docker, debug=args.debug)
    app.run()
    return 0
