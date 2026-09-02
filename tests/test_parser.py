import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from maps_scraper.scraper.parser import (
    _extract_opening_hours,
    _extract_rating_and_reviews,
    extract_coordinates,
    extract_place_id,
)

# Gerçek bir Google Maps detay sayfasından yakalanan aria-label dizisinin
# kısaltılmış hali (bkz. raw_data.aria_labels). Regex'lerin alt kısımdaki
# "benzer işletmeler"/yorum histogramı gibi gürültülü metinlerle yanlış
# eşleşmediğini doğrular.
SAMPLE_ARIA_LABELS = [
    "Google Haritalar", "Ara", "Kapat", "Menü",
    "Klinik Adalar Ağız ve Diş Sağlığı Merkezi",
    "Klinik Adalar Ağız ve Diş Sağlığı Merkezi fotoğrafı",
    "4,3 yıldızlı ", "28 yorum",
    "Adres: Çavuşoğlu, Yakacık Cd. no:108, 34873 Kartal/İstanbul ",
    "Pazartesi,09:00 - 00:00, Çalışma saatlerini kopyala",
    "Salı,09:00 - 00:00, Çalışma saatlerini kopyala",
    "Pazar,Kapalı, Çalışma saatlerini kopyala",
    "5 yıldızlı,23 yorum", "4 yıldızlı,0 yorum",
    "Özel Kartal Diş Polikliniği·4,9 yıldızlı·17 yorum·Diş Kliniği",
    "4,9 yıldızlı 17 Yorum",
]


def test_extract_rating_and_reviews():
    rating, review_count = _extract_rating_and_reviews(SAMPLE_ARIA_LABELS)
    assert rating == 4.3
    assert review_count == 28


def test_extract_opening_hours():
    hours = _extract_opening_hours(SAMPLE_ARIA_LABELS)
    assert hours == {
        "Pazartesi": "09:00 - 00:00",
        "Salı": "09:00 - 00:00",
        "Pazar": "Kapalı",
    }

SAMPLE_URL = (
    "https://www.google.com/maps/place/Örnek+Klinik/@41.0082,28.9784,17z/"
    "data=!3m1!4b1!4m6!3m5!1s0x14cab8123456789a:0xabcdef1234567890"
    "!8m2!3d41.0082376!4d28.9784236!16s%2Fg%2F11abcde"
)


def test_extract_coordinates():
    lat, lng = extract_coordinates(SAMPLE_URL)
    assert lat == 41.0082376
    assert lng == 28.9784236


def test_extract_coordinates_missing():
    lat, lng = extract_coordinates("https://www.google.com/maps/search/klinik")
    assert lat is None
    assert lng is None


def test_extract_place_id():
    place_id = extract_place_id(SAMPLE_URL)
    assert place_id == "0x14cab8123456789a:0xabcdef1234567890"


def test_extract_place_id_missing():
    assert extract_place_id("https://www.google.com/maps/search/klinik") is None
