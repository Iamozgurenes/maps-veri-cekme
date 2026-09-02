# Maps Veri Çekme

Google Maps üzerinden Türkiye genelindeki işletmelerin (klinik, kuaför, restoran,
avukat, veteriner — herhangi bir hizmet kategorisi) bilgilerini toplayıp
PostgreSQL veritabanına kaydeden bir araç.

## Önemli uyarı

Bu araç Google Maps web arayüzünü Playwright ile tarayıcı otomasyonu kullanarak
kazır (resmi Google Places API değil). Bu, Google'ın Kullanım Şartları'na
aykırıdır ve captcha/geçici IP engeli riski taşır. Kendi sorumluluğunuzda
kullanın; büyük ölçekte çalıştırmadan önce küçük bir pilot ile davranışı
gözlemlemeniz önerilir (bkz. aşağıdaki "Hızlı başlangıç").

## Mimari özeti

- `scrape_jobs` tablosu bir iş kuyruğu gibi çalışır: her satır `(il, ilçe, arama
  terimi)` kombinasyonunu temsil eder. Kuyruk sayesinde işlem durup kaldığı
  yerden devam edebilir.
- Bir il-seviyesi arama Google'ın ~120 sonuç sınırına takılırsa (yoğun bölge),
  o il otomatik olarak ilçelerine bölünüp yeniden taranır ("fan-out").
- Sonuçlar `businesses` tablosuna Google'ın dahili `place_id`'si üzerinden
  tekilleştirilerek (upsert) yazılır.
- Proxy kullanımı tamamen opsiyoneldir; `.env` içindeki `PROXY_LIST` boşsa
  yerel IP ile çalışılır, doldurulursa round-robin proxy rotasyonu devreye
  girer (kod değişikliği gerekmez).

## Hızlı başlangıç

```bash
# 1) PostgreSQL'i ayağa kaldır
docker compose up -d

# 2) Bağımlılıkları kur (sanal ortam önerilir)
python -m venv .venv && . .venv/Scripts/activate   # Windows
pip install -e .
playwright install chromium

# 3) .env dosyasını oluştur
cp .env.example .env

# 4) Şemayı oluştur
python -m maps_scraper.cli init-db

# 5) Küçük bir pilot: tek il, varsayılan kategoriler yerine tek terim
python -m maps_scraper.cli seed-jobs --il "İstanbul" --term "diş kliniği"

# 6) Tarayıcıyı görünür modda çalıştırıp gözlemle (HEADLESS=false .env'de de ayarlanabilir)
python -m maps_scraper.cli run --concurrency 1

# 7) İlerlemeyi kontrol et
python -m maps_scraper.cli status
```

Pilot temiz çalışırsa (captcha/engelle karşılaşılmıyorsa) tam kapsamlı taramaya
geçebilirsiniz:

```bash
# Tüm iller, varsayılan kategori listesi (search_terms.py -> DEFAULT_CATEGORIES)
python -m maps_scraper.cli seed-jobs

# Ya da kendi kategori listenizle:
python -m maps_scraper.cli seed-jobs --term "avukat" --term "muhasebeci"

python -m maps_scraper.cli run --concurrency 3
```

`run` komutu Ctrl+C ile güvenle durdurulabilir; `scrape_jobs` tablosundaki
`in_progress` durumundaki job'lar bir sonraki `run` çağrısında `pending`
job'larla birlikte tekrar denenir (bkz. `attempts`/`last_error` alanları).

## Selector bakımı

`src/maps_scraper/scraper/parser.py` içindeki alan çıkarma mantığı Google
Maps'in DOM yapısına dayanır ve zamanla kırılabilir. Bir alan boş gelmeye
başlarsa:

1. `HEADLESS=false` ile bir örnek sayfa açıp güncel DOM'u inceleyin.
2. `raw_data.aria_labels` alanına bakın — panel elemanlarının güncel
   `aria-label` metinlerinin tam listesini içerir, hangi işaretin değiştiğini
   bulmanıza yardımcı olur.
3. İlgili selector'ı güncelleyin.

## Test

```bash
pip install pytest
pytest tests/
```

`tests/test_parser.py` yalnızca saf regex fonksiyonlarını (koordinat/place_id
çıkarma) test eder; tarayıcı gerektirmez.

## Durum notu

Bu proje bu ortamda (Python/Docker kurulu değildi) yazıldı ama çalıştırılarak
test edilemedi. İlk çalıştırmada küçük bir pilotla (`seed-jobs --il ... --term
...` + `run --concurrency 1 --headless false` gözlemli) doğrulamanız önemle
tavsiye edilir.
