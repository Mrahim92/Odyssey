from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

from playwright.async_api import Browser, Page, async_playwright

from .amc_urls import normalize_amc_purchase_url
from .browser_helpers import block_heavy_assets
from .config import Config
from .format_match import is_imax_70mm
from .models import Showtime, Theater
from .state import StateStore


@dataclass
class ScanResult:
    showtimes: list[Showtime]
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

# Patterns for matching showtime blocks in page text / links.
TIME_RE = re.compile(
    r"\b(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))\b",
    re.IGNORECASE,
)
SEAT_AVAILABLE_SELECTORS = [
    "[data-seat-status='available']",
    "[data-status='available']",
    ".seat.available",
    ".available-seat",
    "button.seat:not([disabled]):not(.occupied):not(.sold)",
    "[aria-label*='available' i]",
]


def _contains_any(text: str, needles: list[str]) -> bool:
    lowered = text.lower()
    return any(n in lowered for n in needles)


def _normalize_format(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _parse_time_minutes(value: str) -> int | None:
    match = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)", value.strip(), re.I)
    if not match:
        return None
    hour = int(match.group(1)) % 12
    minute = int(match.group(2))
    if match.group(3).upper() == "PM":
        hour += 12
    return hour * 60 + minute


def _time_in_window(show_time: str, earliest: str, latest: str) -> bool:
    if not earliest and not latest:
        return True
    minutes = _parse_time_minutes(show_time)
    if minutes is None:
        return True
    if earliest:
        start = _parse_time_minutes(earliest)
        if start is not None and minutes < start:
            return False
    if latest:
        end = _parse_time_minutes(latest)
        if end is not None and minutes > end:
            return False
    return True


def _theater_url_for_date(theater: Theater, scan_date: str) -> str:
    base = theater.url.rstrip("/")
    chain = theater.chain.lower()

    if chain == "amc":
        return f"{base}/{scan_date}"
    if chain == "regal":
        return f"{base}?date={scan_date}"
    if chain == "cinemark":
        return f"{base}?date={scan_date}"
    if chain in {"harkins", "celebration", "brenden", "providence"}:
        return base
    return base


async def _count_available_seats(
    page: Page,
    min_seats: int,
    purchase_url: str = "",
    preferred_rows: list[str] | None = None,
) -> int | None:
    if "amctheatres.com" in purchase_url:
        from .amc_seats import count_amc_available_seats

        return await count_amc_available_seats(page, min_seats, preferred_rows)

    for selector in SEAT_AVAILABLE_SELECTORS:
        try:
            seats = page.locator(selector)
            count = await seats.count()
            if count >= min_seats:
                return count
        except Exception:  # noqa: BLE001
            continue

    # Fallback: parse visible seat map text.
    try:
        body = (await page.locator("body").inner_text(timeout=5000)).lower()
        if "sold out" in body or "no seats available" in body:
            return 0
        if "select your seats" in body or "choose seats" in body:
            return min_seats
    except Exception:  # noqa: BLE001
        pass
    return None


async def _extract_showtimes_from_page(
    page: Page,
    theater: Theater,
    scan_date: str,
    config: Config,
) -> list[Showtime]:
    results: list[Showtime] = []
    base_url = page.url

    # Collect candidate links/buttons that mention Odyssey.
    candidates = page.locator("a, button, [role='button']")
    count = await candidates.count()

    seen_urls: set[str] = set()
    for index in range(min(count, 400)):
        node = candidates.nth(index)
        try:
            text = _normalize_format(await node.inner_text(timeout=500))
        except Exception:  # noqa: BLE001
            continue

        if not text or not _contains_any(text, config.movie_title_match):
            continue

        block = text
        try:
            parent_text = _normalize_format(
                await node.locator("xpath=ancestor::*[self::div or self::li][1]").inner_text(
                    timeout=1000
                )
            )
            block = f"{parent_text}\n{text}"
        except Exception:  # noqa: BLE001
            pass

        if not is_imax_70mm(block):
            continue

        time_match = TIME_RE.search(block)
        show_time = time_match.group(1).upper() if time_match else "Unknown"

        if not _time_in_window(show_time, config.earliest_time, config.latest_time):
            continue

        href = await node.get_attribute("href")
        purchase_url = urljoin(base_url, href) if href else base_url
        if purchase_url in seen_urls:
            continue
        seen_urls.add(purchase_url)

        format_label = "IMAX 70MM"

        results.append(
            Showtime(
                theater=theater,
                date=scan_date,
                time=show_time,
                format_label=format_label.upper(),
                purchase_url=purchase_url,
            )
        )

    # Text fallback when ticketing widgets render without obvious links.
    if not results:
        try:
            body = await page.locator("body").inner_text(timeout=8000)
        except Exception:  # noqa: BLE001
            return results

        if not _contains_any(body, config.movie_title_match):
            return results
        if not is_imax_70mm(body):
            return results

        for time_match in TIME_RE.finditer(body):
            show_time = time_match.group(1).upper()
            if not _time_in_window(show_time, config.earliest_time, config.latest_time):
                continue
            results.append(
                Showtime(
                    theater=theater,
                    date=scan_date,
                    time=show_time,
                    format_label="IMAX 70MM",
                    purchase_url=base_url,
                )
            )

    return results


async def _enrich_with_seat_counts(
    browser: Browser,
    showtimes: list[Showtime],
    config: Config,
    state: StateStore | None = None,
) -> list[Showtime]:
    import asyncio

    enriched: list[Showtime] = []
    seen_urls: set[str] = set()
    skipped_cache = 0

    context_kwargs: dict = {
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
    }
    if config.auto_book:
        login_file = config.browser_state_dir / "amc.json"
        if login_file.exists():
            context_kwargs["storage_state"] = str(login_file)

    context = await browser.new_context(**context_kwargs)
    page = await context.new_page()
    await block_heavy_assets(page)

    try:
        for showtime in showtimes:
            if not showtime.purchase_url or showtime.purchase_url == showtime.theater.url:
                continue
            seat_url = (
                normalize_amc_purchase_url(showtime.purchase_url)
                if "amctheatres.com" in showtime.purchase_url
                else showtime.purchase_url
            )
            if seat_url in seen_urls:
                continue
            seen_urls.add(seat_url)

            just_booked = False
            seats: int | None = None
            use_cache = state is not None and not config.auto_book
            if use_cache:
                seats = state.get_cached_seats(
                    seat_url,
                    config.min_seats,
                    config.seat_cache_ttl_minutes,
                )
                if seats is not None:
                    skipped_cache += 1
                    if seats >= config.min_seats:
                        enriched.append(
                            Showtime(
                                theater=showtime.theater,
                                date=showtime.date,
                                time=showtime.time,
                                format_label=showtime.format_label,
                                purchase_url=seat_url,
                                available_seats=seats,
                            )
                        )
                    continue

            try:
                await page.goto(
                    seat_url,
                    wait_until="domcontentloaded",
                    timeout=config.page_timeout_seconds * 1000,
                )
                seats = await _count_available_seats(
                    page,
                    config.min_seats,
                    seat_url,
                    config.preferred_rows or None,
                )
                if state is not None and seats is not None and not config.auto_book:
                    state.cache_seats(seat_url, seats)
                if seats is not None and seats >= config.min_seats:
                    booked = False
                    book_message = ""
                    if config.auto_book and "amctheatres.com" in seat_url:
                        from .amc_booker import try_auto_book_on_page

                        booked, book_message = await try_auto_book_on_page(page, config)
                        if booked:
                            print(f"[book] SUCCESS: {book_message}")
                        else:
                            print(f"[book] FAILED: {book_message}")

                    enriched.append(
                        Showtime(
                            theater=showtime.theater,
                            date=showtime.date,
                            time=showtime.time,
                            format_label=showtime.format_label,
                            purchase_url=seat_url,
                            available_seats=seats,
                            booked=booked,
                            book_message=book_message,
                        )
                    )
                    if config.auto_book and config.stop_after_book and booked:
                        return enriched
                    just_booked = booked
                else:
                    just_booked = False
            except Exception as exc:  # noqa: BLE001
                print(f"[seats] Error checking {seat_url}: {exc}")
                just_booked = False
                continue
            finally:
                if not just_booked:
                    await asyncio.sleep(config.seat_check_delay_seconds)
    finally:
        keep_open = (
            config.auto_book
            and config.stop_before_payment
            and any(st.booked for st in enriched)
        )
        if not keep_open:
            await context.close()
        else:
            print("[book] Browser left open at checkout — complete payment manually.")

    print(
        f"[seats] Checked {len(seen_urls) - skipped_cache} showtime(s) "
        f"({skipped_cache} cached), {len(enriched)} with {config.min_seats}+ seats"
    )
    return enriched


async def scan_theater_date(
    browser: Browser,
    theater: Theater,
    scan_date: str,
    config: Config,
    state: StateStore | None = None,
) -> tuple[list[Showtime], list[str]]:
    url = _theater_url_for_date(theater, scan_date)
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
    )
    page = await context.new_page()
    showtimes: list[Showtime] = []
    errors: list[str] = []
    try:
        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=config.page_timeout_seconds * 1000,
        )
        await page.wait_for_timeout(3000)
        showtimes = await _extract_showtimes_from_page(page, theater, scan_date, config)
    except Exception as exc:  # noqa: BLE001
        message = f"{theater.name} {scan_date}: page load failed ({exc})"
        print(f"[scan] ERROR: {message}")
        errors.append(message)
        showtimes = []
    finally:
        await context.close()

    if not showtimes:
        return [], errors

    return await _enrich_with_seat_counts(browser, showtimes, config, state), errors


async def scan_all(config: Config, state: StateStore | None = None) -> ScanResult:
    from .amc_scraper import scan_amc_theater

    found: list[Showtime] = []
    errors: list[str] = []
    semaphore = asyncio.Semaphore(config.concurrency)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=config.headless and not config.auto_book
        )

        async def run(theater: Theater, scan_date: str | None = None) -> tuple[list[Showtime], list[str]]:
            async with semaphore:
                if theater.chain.lower() == "amc":
                    return await scan_amc_theater(browser, theater, config, state)
                assert scan_date is not None
                return await scan_theater_date(browser, theater, scan_date, config, state)

        tasks: list = []
        for theater in config.theaters:
            if theater.chain.lower() == "amc":
                tasks.append(run(theater))
            else:
                for scan_date in config.scan_dates:
                    tasks.append(run(theater, scan_date))

        batches = await asyncio.gather(*tasks, return_exceptions=True)
        await browser.close()

    for batch in batches:
        if isinstance(batch, Exception):
            message = f"theater scan failed: {batch}"
            print(f"[scan] ERROR: {message}")
            errors.append(message)
            continue
        showtimes, batch_errors = batch
        found.extend(showtimes)
        errors.extend(batch_errors)

    # Deduplicate by key, prefer entries with seat counts.
    deduped: dict[str, Showtime] = {}
    for showtime in found:
        existing = deduped.get(showtime.key)
        if existing is None:
            deduped[showtime.key] = showtime
        elif showtime.available_seats is not None and (
            existing.available_seats is None
            or showtime.available_seats > existing.available_seats
        ):
            deduped[showtime.key] = showtime

    return ScanResult(
        showtimes=sorted(
            deduped.values(),
            key=lambda s: (s.date, s.time, s.theater.name),
        ),
        errors=errors,
    )


def scan_all_sync(config: Config, state: StateStore | None = None) -> ScanResult:
    return asyncio.run(scan_all(config, state))
