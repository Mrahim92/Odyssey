"""Playwright helpers to speed up AMC page loads."""
from __future__ import annotations

from playwright.async_api import Page

# Block images, fonts, and trackers — seat maps use inline SVG, not image requests.
_BLOCKED_TYPES = frozenset({"image", "font", "media"})


async def block_heavy_assets(page: Page) -> None:
    async def _route(route, request) -> None:
        if request.resource_type in _BLOCKED_TYPES:
            await route.abort()
            return
        url = request.url.lower()
        if any(
            host in url
            for host in (
                "google-analytics.com",
                "googletagmanager.com",
                "doubleclick.net",
                "facebook.net",
                "hotjar.com",
                "clarity.ms",
                "adroll.com",
            )
        ):
            await route.abort()
            return
        await route.continue_()

    await page.route("**/*", _route)
