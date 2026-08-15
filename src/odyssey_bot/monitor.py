from __future__ import annotations

from datetime import datetime
import asyncio
import time
from pathlib import Path

from playwright.async_api import async_playwright

from .config import Config, ROOT, load_config
from .notifier import Notifier
from .scraper import scan_all_sync
from .state import StateStore


def _onsale_reached(config: Config) -> bool:
    if config.onsale_at is None:
        return False
    now = datetime.now().astimezone()
    onsale = config.onsale_at
    if onsale.tzinfo is None:
        onsale = onsale.replace(tzinfo=now.tzinfo)
    return now >= onsale


def _wait_for_onsale(config: Config, notifier: Notifier) -> None:
    if config.onsale_at is None:
        return
    now = datetime.now().astimezone()
    onsale = config.onsale_at
    if onsale.tzinfo is None:
        onsale = onsale.replace(tzinfo=now.tzinfo)
    seconds_until = (onsale - now).total_seconds()
    if seconds_until <= 0:
        return
    if seconds_until > 120:
        notifier.status(
            f"On-sale at {onsale.strftime('%Y-%m-%d %I:%M %p %Z')} — "
            f"{int(seconds_until // 60)} min remaining"
        )
        time.sleep(min(seconds_until - 30, 60))
        return
    if seconds_until > 1:
        notifier.status(f"On-sale in {int(seconds_until)}s — standing by...")
        time.sleep(seconds_until)


def run_monitor(config_path: Path | None = None, once: bool = False) -> None:
    config = load_config(config_path)
    if config.auto_book:
        login_file = config.browser_state_dir / "amc.json"
        if not login_file.exists():
            raise SystemExit(
                "auto_book requires AMC login. Run:\n"
                "  python -m odyssey_bot login amc"
                + (f" --config {config_path}" if config_path else "")
            )

    state = StateStore(ROOT / "state.json")
    notifier = Notifier(
        console=config.notify_console,
        desktop=config.notify_desktop,
        discord_webhook=config.discord_webhook,
        sound=config.notify_sound,
        auto_open=config.auto_open and not config.auto_book,
    )

    dates = config.scan_dates
    if dates:
        range_label = f"{dates[0]} through {dates[-1]} ({len(dates)} days)"
    else:
        range_label = "no dates (past end_date)"

    notifier.status(
        f"{config.alert_label} monitor started — {len(config.theaters)} theaters, "
        f"{range_label}, every {config.poll_interval_seconds}s"
    )
    if config.onsale_at:
        notifier.status(
            f"On-sale target: {config.onsale_at.strftime('%Y-%m-%d %I:%M %p %Z')} "
            f"(fast poll every {config.onsale_poll_interval_seconds}s after)"
        )
    if config.auto_book:
        notifier.status(
            "Auto-book ON — will select seats and advance to checkout when found"
        )

    while True:
        started = time.monotonic()
        _wait_for_onsale(config, notifier)
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
                    f"Scan complete: no bookable {config.alert_label} showtimes "
                    f"with {config.min_seats}+ seats (may be sold out)"
                )

            booked = [st for st in showtimes if st.booked]

            if booked:
                notifier.alert(booked)
                for st in booked:
                    state.mark_seen(st.key)
                state.save()
                if config.stop_after_book:
                    notifier.status(
                        "Seats booked — complete payment in the open browser window."
                    )
                    return
            elif fresh:
                notifier.alert(fresh)
                for st in fresh:
                    state.mark_seen(st.key)

            state.save()

            interval = (
                config.onsale_poll_interval_seconds
                if _onsale_reached(config)
                else config.poll_interval_fast_seconds
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
