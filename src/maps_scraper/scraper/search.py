from urllib.parse import quote

from playwright.async_api import Page

from maps_scraper.config import settings
from maps_scraper.scraper.rate_limit import polite_delay, raise_if_blocked

_FEED_SELECTOR = 'div[role="feed"]'
_RESULT_LINK_SELECTOR = f'{_FEED_SELECTOR} a[href*="/maps/place/"]'

# Art arda scroll'da yeni sonuç gelmezse aramanın tükendiğini varsayıyoruz.
_MAX_STALE_SCROLLS = 4


def build_search_url(query: str) -> str:
    return f"https://www.google.com/maps/search/{quote(query)}?hl=tr"


async def collect_result_urls(page: Page, query: str) -> list[str]:
    """Bir arama sorgusu için sonuç listesini sonuna kadar scroll edip
    her işletmenin detay URL'sini döner (kırpılma sinyali için
    settings.result_cap_threshold'a kadar toplar)."""
    await page.goto(build_search_url(query), wait_until="domcontentloaded")
    await raise_if_blocked(page)

    try:
        await page.wait_for_selector(_FEED_SELECTOR, timeout=15_000)
    except Exception:
        # Tek sonuç varsa Google doğrudan detay sayfasına yönlendirebilir;
        # bu durumda mevcut sayfanın kendisi tek sonuçtur.
        if "/maps/place/" in page.url:
            return [page.url]
        return []

    seen: dict[str, None] = {}
    stale_rounds = 0

    while len(seen) < settings.result_cap_threshold and stale_rounds < _MAX_STALE_SCROLLS:
        links = await page.locator(_RESULT_LINK_SELECTOR).evaluate_all(
            "els => els.map(e => e.href)"
        )
        before = len(seen)
        for href in links:
            seen.setdefault(href, None)

        if len(seen) == before:
            stale_rounds += 1
        else:
            stale_rounds = 0

        await page.locator(_FEED_SELECTOR).hover()
        await page.mouse.wheel(0, 2000)
        await polite_delay()

    return list(seen.keys())[: settings.result_cap_threshold]
