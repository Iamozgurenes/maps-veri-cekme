"""
Webapp (Streamlit arayüzü) için tek seferlik, senkron (sync) Google Maps
taraması.

Bu modül `runner.py`'daki asenkron/job-kuyruklu toplu tarama akışından
KASITLI olarak ayrı: kullanıcı arayüzden "Çek" butonuna bastığında tek bir
(il, ilçe, terim) sorgusunu anında çalıştırıp sonucu döner, veritabanına
YAZMAZ. Streamlit'in senkron callback modeliyle uyumlu olsun diye Playwright'ın
sync API'si kullanılıyor (async runner.py ile aynı olay döngüsünde
çalıştırmak gereksiz karmaşıklık yaratırdı).

Alan çıkarma mantığı (`parser.py`) ile aynı, sadece Page çağrıları sync.
"""

import random
import time
from collections.abc import Callable
from urllib.parse import quote

from playwright.sync_api import sync_playwright

from maps_scraper.config import settings
from maps_scraper.proxy.pool import proxy_pool
from maps_scraper.scraper.parser import (
    _extract_opening_hours,
    _extract_rating_and_reviews,
    extract_coordinates,
    extract_place_id,
)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_FEED_SELECTOR = 'div[role="feed"]'
_RESULT_LINK_SELECTOR = f'{_FEED_SELECTOR} a[href*="/maps/place/"]'
_MAX_STALE_SCROLLS = 4

ProgressCallback = Callable[[int, int, str | None], None]


def build_query(il: str, ilce: str | None, term: str) -> str:
    where = f"{ilce}, {il}" if ilce else il
    return f"{term} {where}, Türkiye"


def _build_search_url(query: str) -> str:
    return f"https://www.google.com/maps/search/{quote(query)}?hl=tr"


def _polite_delay() -> None:
    ms = random.randint(settings.scrape_delay_min_ms, settings.scrape_delay_max_ms)
    time.sleep(ms / 1000)


def _collect_result_urls(page, query: str, max_results: int) -> list[str]:
    page.goto(_build_search_url(query), wait_until="domcontentloaded")
    try:
        page.wait_for_selector(_FEED_SELECTOR, timeout=15_000)
    except Exception:
        if "/maps/place/" in page.url:
            return [page.url]
        return []

    seen: dict[str, None] = {}
    stale_rounds = 0
    while len(seen) < max_results and stale_rounds < _MAX_STALE_SCROLLS:
        links = page.locator(_RESULT_LINK_SELECTOR).evaluate_all(
            "els => els.map(e => e.href)"
        )
        before = len(seen)
        for href in links:
            seen.setdefault(href, None)
        stale_rounds = stale_rounds + 1 if len(seen) == before else 0

        page.locator(_FEED_SELECTOR).hover()
        page.mouse.wheel(0, 2000)
        _polite_delay()

    return list(seen.keys())[:max_results]


def _item_text(page, prefix: str) -> str | None:
    locator = page.locator(f'button[data-item-id^="{prefix}"]').first
    if locator.count() == 0:
        return None
    label = locator.get_attribute("aria-label")
    return label.split(":", 1)[-1].strip() if label else None


def _parse_listing(page, url: str) -> dict:
    page.wait_for_selector("h1", timeout=15_000)

    name = page.locator("h1").first.inner_text().strip()

    category = None
    category_locator = page.locator('button[jsaction*="category"]').first
    if category_locator.count() > 0:
        category = category_locator.inner_text().strip()

    address = _item_text(page, "address")
    phone = _item_text(page, "phone")

    website = None
    website_locator = page.locator('a[data-item-id="authority"]').first
    if website_locator.count() > 0:
        website = website_locator.get_attribute("href")

    aria_labels = page.locator("[aria-label]").evaluate_all(
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


def scrape_preview(
    il: str,
    ilce: str | None,
    term: str,
    max_results: int = 40,
    progress_callback: ProgressCallback | None = None,
) -> list[dict]:
    """Tek bir (il, ilçe, terim) için canlı arama yapar ve sonuçları döner.
    Veritabanına yazmaz -- webapp.py bunu önizleme için kullanır, kullanıcı
    "Dataya Aktar"a basınca ayrıca `runner.save_results` çağrılır."""
    query = build_query(il, ilce, term)
    results: list[dict] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=settings.headless)
        try:
            context = browser.new_context(
                locale="tr-TR",
                timezone_id="Europe/Istanbul",
                user_agent=_USER_AGENT,
                viewport={"width": 1366, "height": 900},
                proxy=proxy_pool.next(),
            )
            context.set_default_timeout(settings.page_timeout_ms)
            # Google'ın en bariz otomasyon tespit sinyallerinden birini kapatır
            # (browser.py'deki async yoldakiyle aynı, tutarlılık için).
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
            )
            page = context.new_page()
            urls = _collect_result_urls(page, query, max_results)

            for index, url in enumerate(urls):
                detail_page = context.new_page()
                try:
                    detail_page.goto(url, wait_until="domcontentloaded")
                    data = _parse_listing(detail_page, detail_page.url)
                    results.append(data)
                    if progress_callback:
                        progress_callback(index + 1, len(urls), data.get("name"))
                finally:
                    detail_page.close()
                _polite_delay()
        finally:
            browser.close()

    return results


DistrictProgressCallback = Callable[[str, int, int, str | None], None]


def scrape_all_ilceler(
    il: str,
    term: str,
    max_results_per_query: int = 120,
    progress_callback: DistrictProgressCallback | None = None,
) -> list[dict]:
    """Google'ın tek sorguda verdiği ~120 sonuç sınırını aşmak için: önce
    il genelinde arar, sonuç sınıra takılırsa (kırpılma sinyali) o ilin
    ilçelerini tek tek tarayıp sonuçları `place_id` üzerinden tekilleştirerek
    birleştirir. Büyük iller için uzun sürebilir (her ilçe ayrı bir tarama).
    `progress_callback(bölge, done, total, name)` şeklinde çağrılır."""
    from maps_scraper.locations import TURKEY_LOCATIONS

    merged: dict[str, dict] = {}

    def _merge(results: list[dict], source_ilce: str | None) -> None:
        for r in results:
            # Bu sonucun hangi ilçe sorgusundan geldiğini işaretler; webapp.py
            # "Dataya Aktar"da her satırı doğru ilçeyle kaydetmek için kullanır.
            r["_source_ilce"] = source_ilce
            key = r.get("place_id") or f"{r.get('name')}|{r.get('address')}"
            merged[key] = r

    def _wrap(bolge: str) -> ProgressCallback | None:
        if not progress_callback:
            return None
        return lambda done, total, name: progress_callback(bolge, done, total, name)

    il_results = scrape_preview(il, None, term, max_results_per_query, _wrap(il))
    _merge(il_results, None)

    if len(il_results) >= max_results_per_query:
        for ilce in TURKEY_LOCATIONS.get(il, []):
            sub_results = scrape_preview(il, ilce, term, max_results_per_query, _wrap(ilce))
            _merge(sub_results, ilce)

    return list(merged.values())
