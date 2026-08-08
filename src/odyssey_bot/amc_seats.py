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


async def _dismiss_cookie_banner(page: Page) -> None:
    try:
        await page.get_by_role("button", name="Close this consent banner").click(
            timeout=3000
        )
    except Exception:
        pass


async def count_amc_available_seats(
    page: Page,
    min_seats: int,
    preferred_rows: list[str] | None = None,
) -> int | None:
    """Return available regular seat count, 0 if sold out, None if map did not load."""
    try:
        await page.get_by_text("Seat Map", exact=False).first.wait_for(
            timeout=25_000
        )
    except Exception:
        body = (await page.locator("body").inner_text(timeout=5000)).lower()
        if "sold out" in body or "no seats available" in body:
            return 0
        if "rate limited" in body or "error 1015" in body:
            return None
        return None

    await _dismiss_cookie_banner(page)

    try:
        await page.locator('label input[type="checkbox"]').first.wait_for(timeout=8000)
    except Exception:
        await page.wait_for_timeout(1000)

    body = (await page.locator("body").inner_text(timeout=5000)).lower()
    if "sold out" in body or "no seats available" in body:
        return 0

    if not is_imax_70mm(body):
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
