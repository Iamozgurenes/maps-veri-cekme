from contextlib import asynccontextmanager

from playwright.async_api import Browser, BrowserContext, Playwright

from maps_scraper.config import settings

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


async def launch_browser(playwright: Playwright) -> Browser:
    return await playwright.chromium.launch(headless=settings.headless)


@asynccontextmanager
async def new_context(browser: Browser, proxy: dict | None = None):
    context: BrowserContext = await browser.new_context(
        locale="tr-TR",
        timezone_id="Europe/Istanbul",
        user_agent=_USER_AGENT,
        viewport={"width": 1366, "height": 900},
        proxy=proxy,
    )
    # Google'ın en bariz otomasyon tespit sinyallerinden birini kapatır.
    await context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
    )
    try:
        yield context
    finally:
        await context.close()
