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


# AB bölgesi gibi bazı konumlardaki sunucu IP'lerinde Google, arama
# sonuçlarından önce bir çerez onay ekranı (consent.google.com) gösteriyor.
# Bu ekran geçilmeden "div[role=feed]" hiç görünmüyor ve arama yanlışlıkla
# "sonuç bulunamadı" sanılıyor -- bu yüzden context'in İLK navigasyonundan
# hemen sonra bu ekranı tespit edip geçiyoruz.
_CONSENT_BUTTON_TEXTS = (
    "Tümünü reddet", "Reddet", "Tümünü kabul et", "Kabul et",
    "Reject all", "Accept all",
)


async def handle_consent(page: Page) -> None:
    if "consent.google.com" not in page.url:
        return
    for text in _CONSENT_BUTTON_TEXTS:
        button = page.get_by_role("button", name=text)
        if await button.count() > 0:
            try:
                await button.first.click(timeout=5_000)
                await page.wait_for_load_state("domcontentloaded")
            except Exception:
                pass
            return
