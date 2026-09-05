"""
Tarama başlatma sayfası.

ÖNEMLİ mimari not: Bu sayfa artık taramayı DOĞRUDAN tarayıcı oturumunda
çalıştırmıyor -- eskiden öyleydi ve sayfa yenilenince/tarayıcı kapanınca
tarama yarıda kesiliyordu (bir Streamlit script'i tek bir tarayıcı oturumuna
bağlıdır, o oturum biterse script de durur). Artık bu sayfa sadece
`scrape_jobs` tablosuna iş ekliyor (`seed_jobs`, aynı CLI'daki `seed-jobs`
komutunun kullandığı fonksiyon); asıl tarama ayrı, sürekli çalışan bir
"worker" konteynerinde (`python -m maps_scraper.cli run`) gerçekleşiyor.
Bu sayede tarayıcıyı kapatsanız, bilgisayarınızı kapatsanız bile worker
konteyneri (EasyPanel'de ayrı bir servis olarak) taramaya devam eder.

Aşağıdaki durum paneli (`_status_widget`) sadece İZLEME içindir -- birkaç
saniyede bir kendini yeniler (tarayıcı sekmesi açıkken). Taramanın kendisinin
kalıcılığı bu otomatik yenilemeden değil, worker'ın ayrı bir süreç/konteyner
olarak sürekli çalışmasından gelir.
"""

import asyncio

import streamlit as st
from sqlalchemy import func, select

from maps_scraper.db.models import Business, ScrapeJob
from maps_scraper.db.session import async_session
from maps_scraper.locations import TURKEY_LOCATIONS
from maps_scraper.scraper.runner import seed_jobs
from maps_scraper.search_terms import DEFAULT_CATEGORIES


def _get_status() -> tuple[dict[str, int], int]:
    async def _query():
        async with async_session() as session:
            job_counts = dict(
                (
                    await session.execute(
                        select(ScrapeJob.status, func.count()).group_by(ScrapeJob.status)
                    )
                ).all()
            )
            business_count = await session.scalar(select(func.count()).select_from(Business))
            return job_counts, business_count or 0

    return asyncio.run(_query())


def _seed(iller: list[str] | None, terms: list[str]) -> int:
    async def _query():
        async with async_session() as session:
            return await seed_jobs(session, terms, iller)

    return asyncio.run(_query())


@st.fragment(run_every="10s")
def _status_widget() -> None:
    job_counts, business_count = _get_status()
    pending = job_counts.get("pending", 0)
    in_progress = job_counts.get("in_progress", 0)
    done = job_counts.get("done", 0)
    failed = job_counts.get("failed", 0)

    st.subheader("📡 Arka Plan Tarama Durumu")
    cols = st.columns(5)
    cols[0].metric("Bekleyen", pending)
    cols[1].metric("İşleniyor", in_progress)
    cols[2].metric("Tamamlanan", done)
    cols[3].metric("Başarısız", failed)
    cols[4].metric("Toplam işletme", business_count)

    if pending or in_progress:
        st.caption(
            "Tarama arka planda (worker servisinde) devam ediyor -- bu sekmeyi "
            "kapatabilir, bilgisayarınızı kapatabilirsiniz, iş kaybolmaz. Bu panel "
            "sadece izleme için birkaç saniyede bir kendini yeniliyor."
        )
    elif failed:
        st.caption(
            "Bekleyen iş yok ama başarısız job'lar var -- CLI'da "
            "`python -m maps_scraper.cli retry-failed` ile yeniden kuyruğa alabilirsiniz."
        )
    else:
        st.caption("Şu anda bekleyen/işlenen bir iş yok.")


def render() -> None:
    st.title("Google Maps İşletme Veri Çekme")
    st.caption(
        "Hizmet kategorisi ve il(ler) seçip taramayı arka planda başlatın. Worker "
        "servisi bu işi kuyruktan alıp işler -- tarayıcıyı kapatsanız bile devam eder. "
        "Sonuçları **Veriler** sayfasından görüntüleyebilirsiniz."
    )

    _status_widget()
    st.divider()

    turkey_wide = st.checkbox("🇹🇷 Tüm Türkiye (81 il)")

    secili_iller: list[str] | None
    if turkey_wide:
        secili_iller = None
        st.caption("81 ilin tamamı kuyruğa eklenecek.")
    else:
        secili_iller = st.multiselect(
            "İl(ler)", sorted(TURKEY_LOCATIONS.keys()), default=["İstanbul"]
        )

    secili_terimler = st.multiselect(
        "Hizmet / kategori(ler)", DEFAULT_CATEGORIES, default=["diş kliniği"]
    )
    ozel_terim_metni = st.text_input(
        "Ek özel terim(ler) (virgülle ayırın)", placeholder="örn. nöbetçi eczane, oto kurtarıcı"
    )
    ek_terimler = [t.strip() for t in ozel_terim_metni.split(",") if t.strip()]
    tum_terimler = secili_terimler + ek_terimler

    hazir = bool(tum_terimler) and (turkey_wide or bool(secili_iller))

    if not hazir:
        st.info("Devam etmek için en az bir il (veya 'Tüm Türkiye') ve en az bir kategori seçin.")

    if st.button("🚀 Taramayı Arka Planda Başlat", type="primary", disabled=not hazir):
        created = _seed(secili_iller, tum_terimler)
        kapsam = "81 il" if turkey_wide else f"{len(secili_iller)} il"
        # NOT: burada bilinçli olarak st.rerun() çağırmıyoruz -- buton
        # tıklaması zaten doğal bir rerun tetikler, ekstra bir st.rerun()
        # bu mesajı kullanıcı göremeden silerdi. Durum paneli ayrı bir
        # fragment olduğu için birkaç saniye içinde kendiliğinden güncellenir.
        st.success(
            f"{created} yeni iş kuyruğa eklendi ({len(tum_terimler)} kategori x {kapsam}). "
            "Worker servisi bunları arka planda işlemeye devam edecek."
        )
