from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .monitor import login, run_monitor
from .state import StateStore
from .config import ROOT


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Monitor and book The Odyssey in IMAX 70mm."
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("run", help="Run continuous monitor loop")
    sub.add_parser("once", help="Run a single scan")
    sub.add_parser("clear-state", help="Forget previously alerted showtimes")

    login_parser = sub.add_parser("login", help="Save a logged-in browser session")
    login_parser.add_argument("chain", choices=["amc", "regal", "cinemark"])

    args = parser.parse_args(argv)
    command = args.command or "run"

    if command == "clear-state":
        StateStore(ROOT / "state.json").clear()
        print("Cleared state.json")
        return 0

    if command == "login":
        login(args.chain)
        return 0

    if command == "once":
        try:
            run_monitor(once=True)
        except Exception:
            return 1
        return 0

    run_monitor(once=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
