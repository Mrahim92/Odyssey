"""Playwright helpers — launch, context, faster page loads."""
from __future__ import annotations

from playwright.async_api import Browser, BrowserContext, Page, Playwright

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

_STEALTH_INIT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
"""

_LAUNCH_ARGS = ["--disable-blink-features=AutomationControlled"]

# Block images, fonts, and trackers — seat maps use inline SVG, not image requests.
_BLOCKED_TYPES = frozenset({"image", "font", "media"})


async def launch_browser(
    playwright: Playwright,
    *,
    headless: bool,
    channel: str | None = "chrome",
) -> tuple[Browser, str | None]:
    """Launch Chromium, preferring installed Chrome/Edge to reduce Cloudflare blocks."""
    candidates: list[str | None] = []
    for ch in (channel, "chrome", "msedge", None):
        if ch not in candidates:
            candidates.append(ch)

    last_error: Exception | None = None
    for ch in candidates:
        kwargs: dict = {
            "headless": headless,
            "args": _LAUNCH_ARGS,
            "ignore_default_args": ["--enable-automation"],
        }
        label = ch or "chromium"
        if ch:
            kwargs["channel"] = ch
        try:
            browser = await playwright.chromium.launch(**kwargs)
            if ch:
                print(f"[browser] Using installed {label}")
            else:
                print("[browser] Using Playwright Chromium (may be Cloudflare-blocked on AMC)")
            return browser, ch
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue

    assert last_error is not None
    raise last_error


async def new_browser_context(
    browser: Browser,
    *,
    storage_state: str | None = None,
) -> BrowserContext:
    kwargs: dict = {
        "user_agent": USER_AGENT,
        "viewport": {"width": 1920, "height": 1080},
        "locale": "en-US",
        "timezone_id": "America/New_York",
    }
    if storage_state:
        kwargs["storage_state"] = storage_state
    context = await browser.new_context(**kwargs)
    await context.add_init_script(_STEALTH_INIT)
    return context


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
