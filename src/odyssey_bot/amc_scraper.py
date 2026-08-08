from __future__ import annotations

import re
from datetime import date, datetime

from urllib.parse import urljoin

from playwright.async_api import Browser, Page

from .config import Config
from .models import Showtime, Theater
from .scraper import TIME_RE, _enrich_with_seat_counts

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

AMC_MOVIE_OPTION = "The Odyssey"
AMC_FORMAT_OPTION = "IMAX 70MM"


def _parse_amc_date_label(label: str, today: date) -> date | None:
    cleaned = label.strip()
    if not cleaned:
        return None
    if cleaned.lower() == "today":
        return today
    try:
        parsed = datetime.strptime(f"{cleaned}, {today.year}", "%a, %b %d, %Y")
        return parsed.date()
    except ValueError:
        return None


async def _apply_amc_filters(page: Page) -> None:
    selects = page.locator("select")
    if await selects.count() < 4:
        return

    movie_select = selects.nth(2)
    format_select = selects.nth(3)

    movie_options = await movie_select.locator("option").all_inner_texts()
    if any(opt.strip() == AMC_MOVIE_OPTION for opt in movie_options):
        await movie_select.select_option(label=AMC_MOVIE_OPTION)

    format_options = await format_select.locator("option").all_inner_texts()
    if any(opt.strip() == AMC_FORMAT_OPTION for opt in format_options):
        await format_select.select_option(label=AMC_FORMAT_OPTION)

    await page.wait_for_timeout(2000)


async def _extract_amc_showtimes_for_date(
    page: Page,
    theater: Theater,
    scan_date: str,
    config: Config,
) -> list[Showtime]:
    await _apply_amc_filters(page)

    section = page.locator('section[aria-label*="Showtimes for The Odyssey" i]')
    if await section.count() == 0:
        return []

    container = section.first
    results: list[Showtime] = []
    nodes = container.locator("button, a, [role='button']")
    count = await nodes.count()

    for index in range(count):
        node = nodes.nth(index)
        try:
            text = (await node.inner_text(timeout=1000)).strip().replace("\n", " ")
        except Exception:  # noqa: BLE001
            continue

        time_match = TIME_RE.search(text)
        if not time_match:
            continue

        if "sold out" in text.lower():
            continue

        href = await node.get_attribute("href")
        if not href or "/showtimes/" not in href:
            continue

        show_time = time_match.group(1).upper()
        purchase_url = urljoin("https://www.amctheatres.com", href)
        results.append(
            Showtime(
                theater=theater,
                date=scan_date,
                time=show_time,
                format_label=AMC_FORMAT_OPTION,
                purchase_url=purchase_url,
            )
        )

    return results


async def scan_amc_theater(
    browser: Browser,
    theater: Theater,
    config: Config,
) -> list[Showtime]:
    """Scan an AMC theatre using its showtimes page filters and date dropdown."""
    allowed_dates = set(config.scan_dates)
    today = date.today()
    found: list[Showtime] = []

    context = await browser.new_context(user_agent=USER_AGENT)
    page = await context.new_page()

    try:
        await page.goto(
            theater.url,
            wait_until="domcontentloaded",
            timeout=config.page_timeout_seconds * 1000,
        )
        await page.wait_for_timeout(8000)

        date_select = page.locator("select").nth(1)
        if await date_select.count() == 0:
            return []

        option_labels = await date_select.locator("option").all_inner_texts()
        for label in option_labels:
            parsed = _parse_amc_date_label(label, today)
            if parsed is None:
                continue
            iso = parsed.isoformat()
            if iso not in allowed_dates:
                continue

            await date_select.select_option(label=label)
            await page.wait_for_timeout(2000)
            found.extend(
                await _extract_amc_showtimes_for_date(page, theater, iso, config)
            )
    finally:
        await context.close()

    if not found:
        return []

    return await _enrich_with_seat_counts(browser, found, config)


async def count_amc_odyssey_70mm_slots(
    browser: Browser,
    theater: Theater,
    config: Config,
) -> tuple[int, int]:
    """Return (dates_scanned, odyssey_70mm_buttons_seen) for diagnostics."""
    allowed_dates = set(config.scan_dates)
    today = date.today()
    dates_scanned = 0
    slots_seen = 0

    context = await browser.new_context(user_agent=USER_AGENT)
    page = await context.new_page()
    try:
        await page.goto(
            theater.url,
            wait_until="domcontentloaded",
            timeout=config.page_timeout_seconds * 1000,
        )
        await page.wait_for_timeout(8000)
        date_select = page.locator("select").nth(1)
        for label in await date_select.locator("option").all_inner_texts():
            parsed = _parse_amc_date_label(label, today)
            if parsed is None or parsed.isoformat() not in allowed_dates:
                continue
            dates_scanned += 1
            await date_select.select_option(label=label)
            await page.wait_for_timeout(1500)
            await _apply_amc_filters(page)
            body = (await page.locator("body").inner_text()).lower()
            if "odyssey" in body and "imax 70mm" in body:
                slots_seen += len(TIME_RE.findall(await page.locator("body").inner_text()))
    finally:
        await context.close()

    return dates_scanned, slots_seen
