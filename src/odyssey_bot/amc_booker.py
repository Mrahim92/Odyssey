"""AMC auto-booking — select checkbox seats and advance checkout."""
from __future__ import annotations

from playwright.async_api import Page, async_playwright

from .amc_seats import select_amc_seats, wait_for_amc_seat_map
from .amc_urls import normalize_amc_purchase_url
from .config import Config
from .models import Showtime

from .browser_helpers import launch_browser, new_browser_context
def _amc_login_file(config: Config):
    return config.browser_state_dir / "amc.json"


def _require_amc_login(config: Config) -> str | None:
    state_file = _amc_login_file(config)
    if not state_file.exists():
        print(
            "[book] ERROR: No AMC login saved. Run:\n"
            "  python -m odyssey_bot login amc --config config.dune.yaml"
        )
        return None
    return str(state_file)


async def _wait_for_continue(page: Page, timeout_ms: int = 20_000) -> None:
    button = page.get_by_role("button", name="Continue")
    await button.first.wait_for(state="visible", timeout=timeout_ms)
    deadline = timeout_ms // 200
    for _ in range(deadline):
        if await button.first.is_enabled():
            return
        await page.wait_for_timeout(200)
    raise TimeoutError("Continue button stayed disabled")


async def _click_named_button(page: Page, names: tuple[str, ...]) -> bool:
    for name in names:
        button = page.get_by_role("button", name=name)
        if await button.count():
            try:
                await button.first.click(timeout=4000)
                return True
            except Exception:  # noqa: BLE001
                continue
    return False


async def _at_payment_step(page: Page) -> bool:
    body = (await page.locator("body").inner_text(timeout=5000)).lower()
    url = page.url.lower()
    markers = (
        "credit card",
        "card number",
        "payment method",
        "complete purchase",
        "pay now",
        "billing",
    )
    return "purchase" in url or any(marker in body for marker in markers)


async def advance_amc_checkout(page: Page, config: Config) -> tuple[bool, str]:
    """Click through Tickets / Food steps until payment or confirmation."""
    for step in ("tickets", "food", "review"):
        await page.wait_for_timeout(1000)
        if await _at_payment_step(page):
            if config.stop_before_payment:
                return True, "Seats held — complete payment in the open browser window"
            return False, "Reached payment but auto-pay is disabled"

        body = (await page.locator("body").inner_text(timeout=5000)).lower()
        if "thank you" in body or "confirmation" in body:
            return True, "Order confirmed"

        clicked = await _click_named_button(
            page,
            ("No Thanks", "Skip", "Continue", "Next"),
        )
        if not clicked:
            print(f"[book] No checkout button found at step {step} ({page.url})")
            break

    if await _at_payment_step(page):
        if config.stop_before_payment:
            return True, "Seats held — complete payment in the open browser window"
        return False, "Reached payment but auto-pay is disabled"

    return False, f"Checkout stalled at {page.url}"


async def book_amc_on_current_page(page: Page, config: Config) -> tuple[bool, str]:
    """Select seats on the current AMC seat-map page and advance checkout."""
    selected = await select_amc_seats(
        page,
        config.min_seats,
        config.preferred_rows or None,
        seat_groups=config.seat_groups or None,
    )
    if len(selected) < config.min_seats:
        return False, f"Could only select {len(selected)}/{config.min_seats} seats"

    print(f"[book] Selected {len(selected)} seats: {', '.join(selected)}")

    try:
        await _wait_for_continue(page)
        await page.get_by_role("button", name="Continue").first.click(timeout=5000)
    except Exception as exc:  # noqa: BLE001
        return False, f"Continue button failed: {exc}"

    return await advance_amc_checkout(page, config)


async def book_amc_showtime(showtime: Showtime, config: Config) -> tuple[bool, str]:
    """Open a showtime seat page and book (standalone browser)."""
    state_file = _require_amc_login(config)
    if state_file is None:
        return False, "Missing AMC login session"

    seat_url = normalize_amc_purchase_url(showtime.purchase_url)

    ok = False
    message = "Booking failed"
    async with async_playwright() as playwright:
        browser, _ = await launch_browser(
            playwright,
            headless=False,
            channel=config.browser_channel,
        )
        context = await new_browser_context(
            browser,
            storage_state=state_file,
        )
        page = await context.new_page()
        try:
            await page.goto(
                seat_url,
                wait_until="domcontentloaded",
                timeout=config.page_timeout_seconds * 1000,
            )
            if not await wait_for_amc_seat_map(page):
                return False, "Seat map did not load"

            from .amc_seats import _showtime_format_is_imax_70mm

            if not await _showtime_format_is_imax_70mm(page):
                return False, "Showtime is not IMAX 70mm"

            ok, message = await book_amc_on_current_page(page, config)
            if ok and config.stop_before_payment:
                print(
                    "\n[book] Browser left open at checkout. "
                    "Complete payment, then close the window.\n"
                )
                return ok, message
        finally:
            if not config.stop_before_payment:
                await browser.close()

    return ok, message


async def try_auto_book_on_page(page: Page, config: Config) -> tuple[bool, str]:
    if not config.auto_book:
        return False, ""
    if _require_amc_login(config) is None:
        return False, "Missing AMC login session"
    return await book_amc_on_current_page(page, config)
