"""AMC seat map counting — gold SVG tiles are available seats."""
from __future__ import annotations

from playwright.async_api import Page

# Each AMC seat is a large stacked SVG tile. Available tiles have a #dfc66b
# (gold) background path; occupied tiles use #4d4337. Wheelchair/companion
# seats add white path overlays for the accessibility icon — exclude those.
_COUNT_AVAILABLE_SEATS_JS = """
() => {
  const bodyText = document.body?.innerText || "";
  if (/sold out|no seats available/i.test(bodyText)) return 0;

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

    // Top-of-map screen arc: gold only, short, no chair gradient.
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


async def count_amc_available_seats(page: Page, min_seats: int) -> int | None:
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
    await page.wait_for_timeout(2500)

    body = (await page.locator("body").inner_text(timeout=5000)).lower()
    if "sold out" in body or "no seats available" in body:
        return 0

    if "imax 70mm" not in body and "70mm" not in body:
        return 0

    try:
        count = await page.evaluate(_COUNT_AVAILABLE_SEATS_JS)
    except Exception:
        return None

    if count is None:
        return None
    if isinstance(count, (int, float)):
        return int(count)
    return None
