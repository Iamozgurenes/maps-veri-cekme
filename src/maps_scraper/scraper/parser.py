"""
Bir Google Maps işletme detay sayfasından alan çıkarma.

ÖNEMLİ: Google Maps'in DOM yapısı ve class isimleri (örn. "DUwDvf") minify
edilmiş ve haber vermeden değişebiliyor. Bu modül elden geldiğince kararlı
işaretlere (h1, `data-item-id`, `aria-label` gibi anlamsal öznitelikler)
dayanıyor, ama %100 garantisi yok. Bir alan parse edilemezse sessizce None
bırakılır ve panelin ham aria-label metinleri `raw_data` içine yazılır --
böylece hiçbir veri tamamen kaybolmaz, ileride yeniden parse edilebilir.
Selector'lar zamanla kırılırsa önce burayı güncelleyin.

Not: `og:title` meta etiketi kasıtlı olarak isim kaynağı olarak KULLANILMIYOR
-- Google Maps SPA navigasyonunda bu etiket genelde güncellenmeden statik
"Google Haritalar" değerinde kalıyor. İsim h1'den okunuyor.
"""

import re

from playwright.async_api import Page

_COORD_RE = re.compile(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)")
_PLACE_ID_RE = re.compile(r"!1s(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)")

# Rating/yorum sayısı ana bilgi panelinde ayrı ayrı elemanlar olarak geçiyor
# (örn. "4,3 yıldızlı " ve "28 yorum"), aynı elemanda birleşik değil. Bu
# yüzden aria_labels dizisinde belge sırasına göre ilk eşleşen değer alınır
# -- alt kısımdaki "benzer işletmeler" veya yorum histogramı gibi bölümlerde
# geçen benzer metinler daha sonra geldiği için yanlış eşleşmiyor.
_RATING_ONLY_RE = re.compile(r"^(\d+[.,]\d+)\s*yıldızlı\s*$", re.IGNORECASE)
_REVIEW_ONLY_RE = re.compile(r"^([\d.,]+)\s*(?:yorum|değerlendirme)\s*$", re.IGNORECASE)

_DAYS = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")
_HOURS_RE = re.compile(
    r"^(" + "|".join(_DAYS) + r"),\s*(.+?),\s*Çalışma saatlerini kopyala$"
)


def extract_place_id(url: str) -> str | None:
    match = _PLACE_ID_RE.search(url)
    return match.group(1) if match else None


def extract_coordinates(url: str) -> tuple[float | None, float | None]:
    match = _COORD_RE.search(url)
    if not match:
        return None, None
    return float(match.group(1)), float(match.group(2))


def _extract_rating_and_reviews(aria_labels: list[str]) -> tuple[float | None, int | None]:
    rating: float | None = None
    review_count: int | None = None
    for label in aria_labels:
        stripped = label.strip()
        if rating is None:
            match = _RATING_ONLY_RE.match(stripped)
            if match:
                rating = float(match.group(1).replace(",", "."))
                continue
        if review_count is None:
            match = _REVIEW_ONLY_RE.match(stripped)
            if match:
                review_count = int(re.sub(r"[.,]", "", match.group(1)))
        if rating is not None and review_count is not None:
            break
    return rating, review_count


def _extract_opening_hours(aria_labels: list[str]) -> dict[str, str] | None:
    hours: dict[str, str] = {}
    for label in aria_labels:
        match = _HOURS_RE.match(label.strip())
        if match:
            day, hours_text = match.group(1), match.group(2).strip()
            hours.setdefault(day, hours_text)
    return hours or None


async def _item_text(page: Page, prefix: str) -> str | None:
    locator = page.locator(f'button[data-item-id^="{prefix}"]').first
    if await locator.count() == 0:
        return None
    label = await locator.get_attribute("aria-label")
    if not label:
        return None
    return label.split(":", 1)[-1].strip()


async def parse_listing(page: Page, url: str) -> dict:
    await page.wait_for_selector("h1", timeout=15_000)

    name = (await page.locator("h1").first.inner_text()).strip()

    category = None
    category_locator = page.locator('button[jsaction*="category"]').first
    if await category_locator.count() > 0:
        category = (await category_locator.inner_text()).strip()

    address = await _item_text(page, "address")
    phone = await _item_text(page, "phone")

    website = None
    website_locator = page.locator('a[data-item-id="authority"]').first
    if await website_locator.count() > 0:
        website = await website_locator.get_attribute("href")

    # Panelin tüm aria-label değerleri; rating/yorum/çalışma saatleri buradan
    # türetiliyor ve debug/yeniden-parse için raw_data içinde de saklanıyor.
    aria_labels = await page.locator("[aria-label]").evaluate_all(
        "els => els.map(e => e.getAttribute('aria-label')).filter(Boolean)"
    )

    rating, review_count = _extract_rating_and_reviews(aria_labels)
    opening_hours = _extract_opening_hours(aria_labels)

    place_id = extract_place_id(url)
    latitude, longitude = extract_coordinates(url)

    return {
        "place_id": place_id,
        "name": name,
        "category": category,
        "address": address,
        "phone": phone,
        "website": website,
        "rating": rating,
        "review_count": review_count,
        "latitude": latitude,
        "longitude": longitude,
        "opening_hours": opening_hours,
        "raw_data": {"url": url, "aria_labels": aria_labels},
    }
