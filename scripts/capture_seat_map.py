"""Capture AMC seat map HTML + stats to calibrate the seat counter.

Run when you see ANY available seats (even 1) on an Odyssey IMAX 70mm showtime:

    python scripts/capture_seat_map.py "https://www.amctheatres.com/showtimes/XXXXXXXX"

This saves files under scripts/captures/ for debugging. Paste the output in chat
or open a GitHub issue if the bot misses a drop.
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from odyssey_bot.amc_seats import count_amc_available_seats
from playwright.async_api import async_playwright

OUT_DIR = Path(__file__).resolve().parent / "captures"


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/capture_seat_map.py <AMC showtime URL>")
        sys.exit(1)

    url = sys.argv[1].strip()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    prefix = OUT_DIR / f"seat-map-{stamp}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        print("Loading", url)
        await page.goto(url, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(5000)

        html_path = prefix.with_suffix(".html")
        png_path = prefix.with_suffix(".png")
        json_path = prefix.with_suffix(".json")

        html_path.write_text(await page.content(), encoding="utf-8")
        await page.screenshot(path=str(png_path), full_page=True)

        stats = await page.evaluate(
            """() => {
              const buttons = [...document.querySelectorAll('button, [role=\"button\"]')]
                .map(el => ({
                  aria: el.getAttribute('aria-label'),
                  text: (el.innerText || '').trim().slice(0, 80),
                  cursor: getComputedStyle(el).cursor,
                }))
                .filter(x => x.aria || x.text);
              const pointerSvg = [...document.querySelectorAll('svg *')]
                .filter(el => getComputedStyle(el).cursor === 'pointer').length;
              return {
                url: location.href,
                title: document.title,
                bodyPreview: document.body.innerText.slice(0, 1500),
                buttonSamples: buttons.slice(0, 40),
                pointerSvgCount: pointerSvg,
                hasSeatMap: document.body.innerText.includes('Seat Map'),
                hasIMAX70: /imax 70mm/i.test(document.body.innerText),
              };
            }"""
        )

        seats = await count_amc_available_seats(page, min_seats=1)
        stats["botSeatCount"] = seats

        json_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
        print(f"Saved:\n  {html_path}\n  {png_path}\n  {json_path}")
        print(f"Bot counted {seats} available seat(s)")
        print("\nLeave the browser open to inspect, then close it.")
        input("Press Enter to close browser...")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
