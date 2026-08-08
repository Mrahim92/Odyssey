import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from odyssey_bot.amc_scraper import scan_amc_theater
from odyssey_bot.config import load_config
from playwright.async_api import async_playwright


async def main() -> None:
    config = load_config()
    # Limit to 3 days for a quick verification run.
    config.end_date = date.today() + timedelta(days=2)
    theater = config.theaters[0]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        found = await scan_amc_theater(browser, theater, config)
        await browser.close()

    print(f"Dates scanned through {config.end_date}")
    print(f"Bookable showtimes with {config.min_seats}+ seats: {len(found)}")
    for st in found[:15]:
        print(f"  {st.date} {st.time} seats={st.available_seats} {st.purchase_url}")


asyncio.run(main())
