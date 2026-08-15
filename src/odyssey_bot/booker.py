from __future__ import annotations

import asyncio

from .config import Config
from .models import Showtime


async def _book_async(showtime: Showtime, config: Config) -> bool:
    chain = showtime.theater.chain.lower()
    if chain == "amc":
        from .amc_booker import book_amc_showtime

        ok, message = await book_amc_showtime(showtime, config)
        print(f"[book] {message}")
        return ok

    print(f"Auto-book not implemented for chain '{chain}'")
    return False


def attempt_booking(showtime: Showtime, config: Config) -> bool:
    return asyncio.run(_book_async(showtime, config))
