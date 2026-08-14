from __future__ import annotations

import asyncio
import re
from datetime import date, datetime

from urllib.parse import urljoin

from playwright.async_api import Browser, Page

from .browser_helpers import block_heavy_assets
from .config import Config
from .format_match import is_imax_70mm
from .models import Showtime, Theater
from .scraper import TIME_RE, _enrich_with_seat_counts
from .state import StateStore

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

AMC_MOVIE_OPTION = "The Odyssey"
AMC_FORMAT_OPTION = "IMAX 70MM"
PAGE_LOAD_ATTEMPTS = 3
PAGE_RETRY_DELAY_SECONDS = 4

_BLOCK_MARKERS = (
    "error 1015",
    "access denied",
    "just a moment",
    "cf-browser-verification",
    "enable javascript and cookies",
    "sorry, you have been blocked",
)


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


async def _page_blocked(page: Page) -> bool:
    try:
        body = (await page.locator("body").inner_text(timeout=5000)).lower()
    except Exception:  # noqa: BLE001
        return True
    return any(marker in body for marker in _BLOCK_MARKERS)


async def _load_amc_page(page: Page, theater: Theater, config: Config) -> str | None:
    """Load AMC showtimes page and wait for the date dropdown. Returns error text or None."""
    last_error = "unknown error"

    for attempt in range(1, PAGE_LOAD_ATTEMPTS + 1):
        try:
            await page.goto(
                theater.url,
                wait_until="domcontentloaded",
                timeout=config.page_timeout_seconds * 1000,
            )
        except Exception as exc:  # noqa: BLE001
            last_error = f"navigation failed: {exc}"
            print(
                f"[amc] Page load failed (attempt {attempt}/{PAGE_LOAD_ATTEMPTS}): "
                f"{last_error}"
            )
            if attempt < PAGE_LOAD_ATTEMPTS:
                await asyncio.sleep(PAGE_RETRY_DELAY_SECONDS)
            continue

        if await _page_blocked(page):
            last_error = "Cloudflare or bot block detected"
            print(
                f"[amc] Page blocked (attempt {attempt}/{PAGE_LOAD_ATTEMPTS}) — "
                "retrying..."
            )
            if attempt < PAGE_LOAD_ATTEMPTS:
                await asyncio.sleep(PAGE_RETRY_DELAY_SECONDS)
            continue

        date_select = page.locator("select").nth(1)
        try:
            await date_select.wait_for(timeout=15000)
        except Exception as exc:  # noqa: BLE001
            select_count = await page.locator("select").count()
            last_error = (
                f"date dropdown missing ({select_count} select element(s) on page)"
            )
            print(
                f"[amc] Page not ready (attempt {attempt}/{PAGE_LOAD_ATTEMPTS}): "
                f"{last_error}"
            )
            if attempt < PAGE_LOAD_ATTEMPTS:
                await asyncio.sleep(PAGE_RETRY_DELAY_SECONDS)
            continue

        return None

    return (
        f"AMC showtimes page did not load after {PAGE_LOAD_ATTEMPTS} attempts "
        f"({last_error})"
    )


async def _apply_amc_filters(page: Page) -> bool:
    selects = page.locator("select")
    select_count = await selects.count()
    if select_count < 4:
        print(
            f"[amc] Page not ready — found {select_count} select element(s), "
            "expected at least 4 for movie/format filters"
        )
        return False

    movie_select = selects.nth(2)
    format_select = selects.nth(3)

    movie_options = await movie_select.locator("option").all_inner_texts()
    if not any(opt.strip() == AMC_MOVIE_OPTION for opt in movie_options):
        return False
    await movie_select.select_option(label=AMC_MOVIE_OPTION)

    format_options = await format_select.locator("option").all_inner_texts()
    if not any(opt.strip() == AMC_FORMAT_OPTION for opt in format_options):
        return False
    await format_select.select_option(label=AMC_FORMAT_OPTION)

    try:
        await page.locator('section[aria-label*="Showtimes for The Odyssey" i]').first.wait_for(
            timeout=5000
        )
    except Exception:
        pass
    return True


async def _extract_amc_showtimes_for_date(
    page: Page,
    theater: Theater,
    scan_date: str,
) -> list[Showtime]:
    section = page.locator('section[aria-label*="Showtimes for The Odyssey" i]')
    if await section.count() == 0:
        return []

    section_text = await section.first.inner_text()
    if not is_imax_70mm(section_text):
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
    state: StateStore | None = None,
) -> tuple[list[Showtime], list[str]]:
    """Scan an AMC theatre using its showtimes page filters and date dropdown."""
    allowed_dates = set(config.scan_dates)
    today = date.today()
    found: list[Showtime] = []
    dates_checked = 0
    errors: list[str] = []

    context = await browser.new_context(user_agent=USER_AGENT)
    page = await context.new_page()
    await block_heavy_assets(page)

    try:
        load_error = await _load_amc_page(page, theater, config)
        if load_error:
            print(f"[amc] ERROR: {load_error}")
            errors.append(load_error)
            return [], errors

        date_select = page.locator("select").nth(1)

        if not await _apply_amc_filters(page):
            message = "IMAX 70MM filter unavailable on AMC page"
            print(f"[amc] ERROR: {message}")
            errors.append(message)
            return [], errors

        option_labels = await date_select.locator("option").all_inner_texts()
        dates_to_scan: list[tuple[str, str]] = []
        for label in option_labels:
            parsed = _parse_amc_date_label(label, today)
            if parsed is None:
                continue
            iso = parsed.isoformat()
            if iso not in allowed_dates:
                continue
            dates_to_scan.append((iso, label))
        # September first — most likely drops, and partial runs prefer later dates.
        dates_to_scan.sort(key=lambda item: item[0], reverse=True)

        for iso, label in dates_to_scan:
            dates_checked += 1
            await date_select.select_option(label=label)
            try:
                await page.locator(
                    'section[aria-label*="Showtimes for The Odyssey" i]'
                ).first.wait_for(timeout=3000)
            except Exception:
                continue
            found.extend(
                await _extract_amc_showtimes_for_date(page, theater, iso)
            )
    except Exception as exc:  # noqa: BLE001
        message = f"AMC scan failed: {exc}"
        print(f"[amc] ERROR: {message}")
        errors.append(message)
        return [], errors
    finally:
        await context.close()

    if not found:
        print(f"[amc] Scanned {dates_checked} dates — no non-sold-out showtimes")
        return [], errors

    unique: dict[str, Showtime] = {}
    for showtime in found:
        if showtime.purchase_url not in unique:
            unique[showtime.purchase_url] = showtime
    found = list(unique.values())

    print(
        f"[amc] Scanned {dates_checked} dates — "
        f"{len(found)} unique showtime(s) to seat-check"
    )

    if not found:
        return [], errors

    return await _enrich_with_seat_counts(browser, found, config, state), errors


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
            if is_imax_70mm(body):
                slots_seen += len(TIME_RE.findall(await page.locator("body").inner_text()))
    finally:
        await context.close()

    return dates_scanned, slots_seen
