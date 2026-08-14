from __future__ import annotations

import asyncio
import time
from pathlib import Path

from playwright.async_api import async_playwright

from .config import Config, ROOT, load_config
from .notifier import Notifier
from .scraper import scan_all_sync
from .state import StateStore


def run_monitor(config_path: Path | None = None, once: bool = False) -> None:
    config = load_config(config_path)
    state = StateStore(ROOT / "state.json")
    notifier = Notifier(
        console=config.notify_console,
        desktop=config.notify_desktop,
        discord_webhook=config.discord_webhook,
        sound=config.notify_sound,
        auto_open=config.auto_open,
    )

    dates = config.scan_dates
    if dates:
        range_label = f"{dates[0]} through {dates[-1]} ({len(dates)} days)"
    else:
        range_label = "no dates (past end_date)"

    notifier.status(
        f"Odyssey 70mm monitor started — {len(config.theaters)} theaters, "
        f"{range_label}, every {config.poll_interval_seconds}s"
    )

    while True:
        started = time.monotonic()
        try:
            result = scan_all_sync(config, state)
            showtimes = result.showtimes
            fresh = [st for st in showtimes if state.is_new(st.key)]

            if result.errors:
                for error in result.errors:
                    print(f"::warning::{error}", flush=True)
                notifier.status(
                    "Scan incomplete — AMC page may be blocked: "
                    + "; ".join(result.errors)
                )
            elif showtimes:
                notifier.status(
                    f"Scan complete: {len(showtimes)} bookable showtime(s) "
                    f"with {config.min_seats}+ seats, {len(fresh)} new"
                )
            else:
                notifier.status(
                    "Scan complete: no bookable IMAX 70mm Odyssey showtimes "
                    f"with {config.min_seats}+ seats (may be sold out)"
                )

            if fresh:
                notifier.alert(fresh)
                for st in fresh:
                    state.mark_seen(st.key)

                if config.auto_book:
                    from .booker import attempt_booking

                    for st in fresh:
                        attempt_booking(st, config)

            state.save()

            interval = (
                config.poll_interval_fast_seconds
                if showtimes
                else config.poll_interval_seconds
            )
        except KeyboardInterrupt:
            notifier.status("Monitor stopped.")
            return
        except Exception as exc:  # noqa: BLE001
            notifier.status(f"Scan error: {exc}")
            interval = config.poll_interval_seconds
            if once:
                raise

        if once:
            return

        elapsed = time.monotonic() - started
        sleep_for = max(5, interval - elapsed)
        notifier.status(f"Sleeping {int(sleep_for)}s until next scan...")
        time.sleep(sleep_for)


async def _login_async(chain: str, config: Config) -> None:
    login_urls = {
        "amc": "https://www.amctheatres.com/login",
        "regal": "https://www.regmovies.com/login",
        "cinemark": "https://www.cinemark.com/sign-in",
    }
    url = login_urls.get(chain.lower())
    if not url:
        raise ValueError(f"No login URL for chain '{chain}'. Supported: amc, regal, cinemark")

    state_dir = config.browser_state_dir
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / f"{chain.lower()}.json"

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        print(
            f"\nLog in to {chain.upper()} in the browser window.\n"
            "When finished, press Enter here to save the session..."
        )
        input()
        await context.storage_state(path=str(state_file))
        await browser.close()

    print(f"Saved session to {state_file}")


def login(chain: str, config_path: Path | None = None) -> None:
    config = load_config(config_path)
    asyncio.run(_login_async(chain, config))
