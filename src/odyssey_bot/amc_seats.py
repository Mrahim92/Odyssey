"""AMC seat map counting — available checkbox seats, optional row filter."""
from __future__ import annotations

from playwright.async_api import Page

from .format_match import is_imax_70mm

# Each seat is a <label> with a checkbox input. Row+seat encoded in input name
# (e.g. H42 = row H, seat 42). Available = enabled, not Occupied, not wheelchair.
_COUNT_AVAILABLE_SEATS_JS = """
(targetRows) => {
  const bodyText = document.body?.innerText || "";
  if (/sold out|no seats available/i.test(bodyText)) return 0;

  const allowedRows = targetRows && targetRows.length
    ? new Set(targetRows.map((r) => String(r).toUpperCase()))
    : null;

  const inputs = [...document.querySelectorAll('label input[type="checkbox"]')];
  if (inputs.length) {
    let count = 0;
    for (const input of inputs) {
      const aria = (input.getAttribute("aria-label") || "").trim();
      const name = (input.getAttribute("name") || "").trim();
      const match = name.match(/^([A-Z]+)(\\d+)$/);
      if (!match) continue;

      const row = match[1];
      if (allowedRows && !allowedRows.has(row)) continue;
      if (input.disabled || /occupied/i.test(aria)) continue;
      if (/wheelchair|companion|accessible|ada/i.test(aria)) continue;
      count += 1;
    }
    return count;
  }

  // Fallback when checkbox map is missing (no row filter — cannot honor rows).
  if (allowedRows) return 0;

  const pathFill = (el) => (el.getAttribute("fill") || "").trim().toLowerCase();

  const isWheelchairSeat = (root) => {
    const label = (
      root.getAttribute("aria-label") ||
      root.getAttribute("title") ||
      ""
    ).toLowerCase();
    if (/wheelchair|companion|accessible|ada/i.test(label)) return true;

    const paths = [...root.querySelectorAll("path, rect, circle")];
    return paths.some((p) => {
      const fill = pathFill(p);
      return fill === "white" || fill === "#fff" || fill === "#ffffff";
    });
  };

  const isSeatTile = (svg) => {
    const rect = svg.getBoundingClientRect();
    if (rect.width < 500 || rect.height < 200) return false;

    const paths = [...svg.querySelectorAll("path")];
    if (!paths.length) return false;

    const fills = paths.map(pathFill);
    const hasGold = fills.includes("#dfc66b");
    const hasOccupied = fills.includes("#4d4337");
    const hasGradient = fills.some((f) => f.startsWith("url("));

    if (hasGold && !hasOccupied && !hasGradient && rect.height < 1000) {
      return false;
    }

    return hasGradient || hasOccupied || (hasGold && rect.height >= 1000);
  };

  const seatTiles = [...document.querySelectorAll("svg")].filter(isSeatTile);
  if (!seatTiles.length) {
    if (/select your seats|choose your seats|seat map/i.test(bodyText)) {
      return null;
    }
    return 0;
  }

  let availableRegular = 0;
  for (const svg of seatTiles) {
    const fills = [...svg.querySelectorAll("path")].map(pathFill);
    const hasGold = fills.includes("#dfc66b");
    const hasOccupied = fills.includes("#4d4337");
    if (hasGold && !hasOccupied && !isWheelchairSeat(svg)) {
      availableRegular += 1;
    }
  }

  return availableRegular;
}
"""

_FIND_SEATS_TO_SELECT_JS = """
([targetRows, minSeats]) => {
  const target = targetRows && targetRows.length
    ? new Set(targetRows.map((r) => String(r).toUpperCase()))
    : null;

  const seats = [];
  for (const input of document.querySelectorAll('label input[type="checkbox"]')) {
    const name = (input.getAttribute("name") || "").trim();
    const aria = (input.getAttribute("aria-label") || "").trim();
    const match = name.match(/^([A-Z]+)(\\d+)$/);
    if (!match) continue;
    if (input.disabled || /occupied/i.test(aria)) continue;
    if (/wheelchair|companion|accessible|ada/i.test(aria)) continue;
    seats.push({ name, row: match[1], num: parseInt(match[2], 10) });
  }

  const byRow = {};
  for (const seat of seats) {
    if (target && !target.has(seat.row)) continue;
    (byRow[seat.row] ||= []).push(seat);
  }

  let searchRows = Object.keys(byRow);
  if (!searchRows.length) {
    for (const seat of seats) {
      (byRow[seat.row] ||= []).push(seat);
    }
    searchRows = Object.keys(byRow);
  }

  let best = null;
  for (const row of searchRows) {
    const arr = byRow[row].sort((a, b) => a.num - b.num);
    if (arr.length < minSeats) continue;
    for (let i = 0; i <= arr.length - minSeats; i++) {
      const window = arr.slice(i, i + minSeats);
      const spread = window[minSeats - 1].num - window[0].num;
      if (!best || spread < best.spread) {
        best = { spread, names: window.map((s) => s.name), row };
      }
    }
  }

  return best ? best.names : null;
}
"""


async def _dismiss_cookie_banner(page: Page) -> None:
    try:
        await page.get_by_role("button", name="Close this consent banner").click(
            timeout=3000
        )
    except Exception:
        pass


async def _showtime_info_text(page: Page) -> str:
    """Read the Showtime Information panel — not the full page (footer mentions IMAX)."""
    try:
        heading = page.get_by_role("heading", name="Showtime Information")
        await heading.wait_for(timeout=5000)
        container = heading.locator("xpath=ancestor::*[self::section or self::div][1]")
        return await container.inner_text(timeout=5000)
    except Exception:  # noqa: BLE001
        return ""


async def wait_for_amc_seat_map(page: Page) -> bool:
    """Wait for AMC seat map to load. Returns False if sold out or blocked."""
    try:
        await page.get_by_text("Seat Map", exact=False).first.wait_for(timeout=25_000)
    except Exception:
        body = (await page.locator("body").inner_text(timeout=5000)).lower()
        if "sold out" in body or "no seats available" in body:
            return False
        return False

    await _dismiss_cookie_banner(page)

    try:
        await page.locator('label input[type="checkbox"]').first.wait_for(timeout=8000)
    except Exception:
        await page.wait_for_timeout(1000)
    return True


async def find_seats_to_select(
    page: Page,
    min_seats: int,
    preferred_rows: list[str] | None = None,
) -> list[str]:
    rows = [r.upper() for r in (preferred_rows or []) if r]
    try:
        names = await page.evaluate(_FIND_SEATS_TO_SELECT_JS, [rows, min_seats])
    except Exception:
        return []
    if not names or len(names) < min_seats:
        return []
    return list(names)


async def select_amc_seats(
    page: Page,
    min_seats: int,
    preferred_rows: list[str] | None = None,
) -> list[str]:
    """Click the best compact block of seats. Returns selected seat names."""
    names = await find_seats_to_select(page, min_seats, preferred_rows)
    selected: list[str] = []
    for name in names:
        checkbox = page.locator(f'label input[type="checkbox"][name="{name}"]')
        try:
            await checkbox.click(timeout=3000)
            selected.append(name)
        except Exception:
            label = page.locator(f'label:has(input[name="{name}"])')
            try:
                await label.click(timeout=3000)
                selected.append(name)
            except Exception:
                break
    return selected


async def count_amc_available_seats(
    page: Page,
    min_seats: int,
    preferred_rows: list[str] | None = None,
) -> int | None:
    """Return available regular seat count, 0 if sold out, None if map did not load."""
    if not await wait_for_amc_seat_map(page):
        body = (await page.locator("body").inner_text(timeout=5000)).lower()
        if "sold out" in body or "no seats available" in body:
            return 0
        if "rate limited" in body or "error 1015" in body:
            return None
        return None

    body = (await page.locator("body").inner_text(timeout=5000)).lower()
    if "sold out" in body or "no seats available" in body:
        return 0

    showtime_info = await _showtime_info_text(page)
    if not showtime_info or not is_imax_70mm(showtime_info):
        if showtime_info:
            format_hint = showtime_info.replace("\n", " ")[:120]
            print(f"[seats] Skipping non-IMAX-70mm showtime: {format_hint}")
        return 0

    rows = [r.upper() for r in (preferred_rows or []) if r]

    try:
        count = await page.evaluate(_COUNT_AVAILABLE_SEATS_JS, rows)
    except Exception:
        return None

    if count is None:
        return None
    if isinstance(count, (int, float)):
        return int(count)
    return None
