from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

from .config import Config
from .models import Showtime

SEAT_SELECTORS = [
    "[data-seat-status='available']",
    "[data-status='available']",
    ".seat.available",
    "button.seat:not([disabled]):not(.occupied):not(.sold)",
]


async def _book_async(showtime: Showtime, config: Config) -> bool:
    chain = showtime.theater.chain.lower()
    state_file = config.browser_state_dir / f"{chain}.json"
    if not state_file.exists():
        print(
            f"No saved login for {chain}. Run: python -m odyssey_bot login {chain}"
        )
        return False

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context(storage_state=str(state_file))
        page = await context.new_page()

        try:
            await page.goto(showtime.purchase_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            selected = 0
            for selector in SEAT_SELECTORS:
                seats = page.locator(selector)
                count = await seats.count()
                for index in range(count):
                    if selected >= config.min_seats:
                        break
                    try:
                        await seats.nth(index).click(timeout=2000)
                        selected += 1
                    except Exception:  # noqa: BLE001
                        continue
                if selected >= config.min_seats:
                    break

            if selected < config.min_seats:
                print(
                    f"Could only select {selected}/{config.min_seats} seats at "
                    f"{showtime.theater.name}"
                )
                return False

            # Try common continue buttons; stop before payment if configured.
            for label in ("Continue", "Next", "Checkout", "Review Order"):
                button = page.get_by_role("button", name=label)
                if await button.count():
                    if config.stop_before_payment and label.lower() in {
                        "checkout",
                        "review order",
                    }:
                        print(
                            "Reached checkout — stopping before payment "
                            "(stop_before_payment=true)."
                        )
                        return True
                    try:
                        await button.first.click(timeout=3000)
                        await page.wait_for_timeout(1500)
                    except Exception:  # noqa: BLE001
                        pass

            print(
                "Seat selection complete. Complete payment manually in the browser."
            )
            return True
        finally:
            if config.stop_before_payment:
                print("Browser left open for manual payment. Close when done.")
            else:
                await browser.close()

    return False


def attempt_booking(showtime: Showtime, config: Config) -> bool:
    return asyncio.run(_book_async(showtime, config))
