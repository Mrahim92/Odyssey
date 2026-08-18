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
([targetRows, groupSizes]) => {
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

  const bestBlockInRow = (arr, size) => {
    if (arr.length < size) return null;
    let best = null;
    for (let i = 0; i <= arr.length - size; i++) {
      const window = arr.slice(i, i + size);
      const spread = window[size - 1].num - window[0].num;
      if (!best || spread < best.spread) {
        best = { spread, names: window.map((s) => s.name) };
      }
    }
    return best;
  };

  const findBestBlock = (size, exclude) => {
    let best = null;
    for (const row of searchRows) {
      const arr = byRow[row]
        .filter((s) => !exclude.has(s.name))
        .sort((a, b) => a.num - b.num);
      const block = bestBlockInRow(arr, size);
      if (block && (!best || block.spread < best.spread)) {
        best = block;
      }
    }
    return best;
  };

  const sizes = [...groupSizes].sort((a, b) => b - a);
  const selected = [];
  const used = new Set();

  for (const size of sizes) {
    const block = findBestBlock(size, used);
    if (!block) return null;
    selected.push(...block.names);
    for (const name of block.names) used.add(name);
  }

  return selected.length ? selected : null;
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


async def _showtime_format_is_imax_70mm(page: Page) -> bool:
    """True when a Showtime Information list item is IMAX 70mm (not plain 70mm)."""
    try:
        heading = page.get_by_role("heading", name="Showtime Information")
        container = heading.locator("xpath=ancestor::*[self::section or self::div][1]")
        for text in await container.locator("li").all_inner_texts():
            if is_imax_70mm(text.strip()):
                return True
    except Exception:  # noqa: BLE001
        pass
    return False


def _showtime_matches_title(info: str, title_match: list[str]) -> bool:
    lowered = info.lower()
    return any(needle in lowered for needle in title_match)


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
    seat_groups: list[int] | None = None,
) -> list[str]:
    rows = [r.upper() for r in (preferred_rows or []) if r]
    groups = seat_groups if seat_groups else [min_seats]
    try:
        names = await page.evaluate(_FIND_SEATS_TO_SELECT_JS, [rows, groups])
    except Exception:
        return []
    if not names or len(names) < min_seats:
        return []
    return list(names)


async def select_amc_seats(
    page: Page,
    min_seats: int,
    preferred_rows: list[str] | None = None,
    seat_groups: list[int] | None = None,
) -> list[str]:
    """Click the best seat block(s). Returns selected seat names."""
    names = await find_seats_to_select(
        page, min_seats, preferred_rows, seat_groups=seat_groups
    )
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
    title_match: list[str] | None = None,
) -> int | None:
    """Return bookable seat count, 0 if none/sold out, None if map did not load."""
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
    if title_match and showtime_info and not _showtime_matches_title(
        showtime_info, title_match
    ):
        print("[seats] Skipping showtime — title does not match filter")
        return 0

    if not await _showtime_format_is_imax_70mm(page):
        if showtime_info:
            format_hint = showtime_info.replace("\n", " ")[:120]
            print(f"[seats] Skipping non-IMAX-70mm showtime: {format_hint}")
        return 0

    rows = [r.upper() for r in (preferred_rows or []) if r]
    selectable = await find_seats_to_select(page, min_seats, preferred_rows)
    if len(selectable) < min_seats:
        try:
            raw = await page.evaluate(_COUNT_AVAILABLE_SEATS_JS, rows)
            if isinstance(raw, (int, float)) and raw >= min_seats:
                print(
                    f"[seats] {int(raw)} seat(s) in target rows but no group of "
                    f"{min_seats} together — not alerting"
                )
        except Exception:
            pass
        return 0

    return len(selectable)
