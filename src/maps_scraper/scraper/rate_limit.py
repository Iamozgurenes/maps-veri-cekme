import asyncio
import random

from playwright.async_api import Page

from maps_scraper.config import settings


class BlockedError(Exception):
    """Google tarafından captcha/"unusual traffic" ile engellendiğimizde fırlatılır."""


async def polite_delay() -> None:
    ms = random.randint(settings.scrape_delay_min_ms, settings.scrape_delay_max_ms)
    await asyncio.sleep(ms / 1000)


_BLOCK_MARKERS = (
    "unusual traffic",
    "olağandışı trafik",
    "recaptcha",
    "/sorry/index",
)


async def raise_if_blocked(page: Page) -> None:
    url = page.url.lower()
    if any(marker in url for marker in _BLOCK_MARKERS):
        raise BlockedError(f"Google engelleme sayfasına yönlendirdi: {page.url}")

    content = (await page.content()).lower()
    if any(marker in content for marker in _BLOCK_MARKERS):
        raise BlockedError("Sayfa içeriğinde captcha/engelleme işareti bulundu")
