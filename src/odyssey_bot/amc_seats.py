"""AMC seat map counting — gold/clickable seats are available."""
from __future__ import annotations

from playwright.async_api import Page

AMC_BASE = "https://www.amctheatres.com"

# JavaScript run in the browser to count selectable seats on AMC's SVG seat map.
# Occupied seats are not clickable; available seats use pointer cursor / are buttons.
_COUNT_AVAILABLE_SEATS_JS = """
() => {
  const bodyText = document.body?.innerText || "";
  if (/sold out|no seats available/i.test(bodyText)) return 0;

  const blocked = (label) =>
    !label ||
    /back|continue|hide|close|sign in|join|screen|legend|seat information/i.test(label);

  const seatLabel = (label) =>
    /row\\s+[a-z0-9]+\\s+seat\\s+\\d+/i.test(label) ||
    (/row/i.test(label) && /seat/i.test(label));

  const buttons = [...document.querySelectorAll("button, [role='button']")];
  const labeledSeats = buttons.filter((el) => {
    const label = (el.getAttribute("aria-label") || "").trim().toLowerCase();
    if (blocked(label)) return false;
    if (/occupied|unavailable|selected|wheelchair companion/i.test(label)) return false;
    return seatLabel(label);
  });
  if (labeledSeats.length) return labeledSeats.length;

  // Fallback: clickable SVG shapes in the seat map (gold available seats).
  const pointerSeats = [...document.querySelectorAll("svg *")].filter((el) => {
    const style = window.getComputedStyle(el);
    if (style.cursor !== "pointer") return false;
    const rect = el.getBoundingClientRect();
    return rect.width >= 8 && rect.height >= 8;
  });
  if (pointerSeats.length) return pointerSeats.length;

  if (/select your seats|choose your seats/i.test(bodyText)) {
    return null;
  }
  return 0;
}
"""


async def count_amc_available_seats(page: Page, min_seats: int) -> int | None:
    """Return available seat count, 0 if sold out, None if map did not load."""
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

    await page.wait_for_timeout(2500)

    body = (await page.locator("body").inner_text(timeout=5000)).lower()
    if "sold out" in body or "no seats available" in body:
        return 0

    # Must be on an IMAX 70mm showtime page when format is listed.
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
