from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .monitor import login, run_monitor
from .state import StateStore
from .config import ROOT


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Monitor and book IMAX 70mm showtimes at AMC Lincoln Square."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config.yaml (default: ./config.yaml)",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("run", help="Run continuous monitor loop")
    sub.add_parser("once", help="Run a single scan")
    sub.add_parser("clear-state", help="Forget previously alerted showtimes")

    login_parser = sub.add_parser("login", help="Save a logged-in browser session")
    login_parser.add_argument("chain", choices=["amc", "regal", "cinemark"])

    book_parser = sub.add_parser("book", help="Test auto-book on a seat URL")
    book_parser.add_argument("url", help="AMC /showtimes/.../seats URL")

    args = parser.parse_args(argv)
    command = args.command or "run"

    if command == "clear-state":
        StateStore(ROOT / "state.json").clear()
        print("Cleared state.json")
        return 0

    if command == "login":
        login(args.chain, config_path=args.config)
        return 0

    if command == "book":
        from .amc_urls import normalize_amc_purchase_url
        from .booker import attempt_booking
        from .config import load_config
        from .models import Showtime

        config = load_config(args.config)
        theater = config.theaters[0] if config.theaters else None
        if theater is None:
            print("No theater configured")
            return 1
        showtime = Showtime(
            theater=theater,
            date="test",
            time="TEST",
            format_label=config.amc_format_name,
            purchase_url=normalize_amc_purchase_url(args.url),
        )
        return 0 if attempt_booking(showtime, config) else 1

    if command == "once":
        try:
            run_monitor(config_path=args.config, once=True)
        except Exception:
            return 1
        return 0

    run_monitor(config_path=args.config, once=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
