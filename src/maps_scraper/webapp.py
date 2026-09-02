"""
Basit Streamlit arayüzü: hizmet kategorisi + il/ilçe (veya tüm Türkiye) seç,
"Verileri Çek" ile Google Maps'ten canlı önizleme al, beğenirsen "Dataya
Aktar" ile PostgreSQL'e kaydet.

Çalıştırmak için: `python -m maps_scraper.cli webapp` (veya doğrudan
`streamlit run src/maps_scraper/webapp.py`).

Not: "Tüm Türkiye" seçimi 81 ili (gerekirse ilçeleriyle) tek tek tarar --
saatler sürebilir ve tarayıcı sekmesinin/bağlantının açık kalmasını
gerektirir. Uzun süreli, gözetimsiz/arka planda çalışacak taramalar için
CLI'daki `seed-jobs` + `run` komutları (bkz. runner.py) daha uygun -- o akış
durup devam edebilen bir job kuyruğu içeriyor ve tarayıcı gerektirmiyor.
"""

import asyncio

import pandas as pd
import streamlit as st

from maps_scraper.locations import TURKEY_LOCATIONS
from maps_scraper.scraper.runner import save_results
from maps_scraper.scraper.sync_scrape import scrape_all_ilceler, scrape_preview
from maps_scraper.search_terms import DEFAULT_CATEGORIES

st.set_page_config(page_title="Maps Veri Çekme", layout="wide")
st.title("Google Maps İşletme Veri Çekme")
st.caption(
    "Bir hizmet kategorisi ve şehir (veya tüm Türkiye) seçip Google Maps'ten canlı "
    "sonuç çekin, önizlemeyi kontrol edip beğenirseniz veritabanına aktarın."
)

if "results" not in st.session_state:
    st.session_state.results = None
    st.session_state.meta = None
if "saved_count" not in st.session_state:
    st.session_state.saved_count = 0

TUM_TURKIYE = "(Tüm Türkiye)"
TUM_IL = "(Tüm il)"

iller = sorted(TURKEY_LOCATIONS.keys())

col1, col2, col3 = st.columns(3)

with col1:
    il_options = [TUM_TURKIYE] + iller
    il_choice = st.selectbox("İl", il_options)
    turkey_wide = il_choice == TUM_TURKIYE
    il = None if turkey_wide else il_choice

with col2:
    if turkey_wide:
        st.selectbox("İlçe", [TUM_IL], disabled=True)
        ilce = None
    else:
        ilce_options = [TUM_IL] + TURKEY_LOCATIONS.get(il, [])
        ilce_choice = st.selectbox("İlçe", ilce_options)
        ilce = None if ilce_choice == TUM_IL else ilce_choice

with col3:
    term_options = DEFAULT_CATEGORIES + ["(Özel terim yaz...)"]
    term_choice = st.selectbox("Hizmet / kategori", term_options)
    if term_choice == "(Özel terim yaz...)":
        term = st.text_input("Özel hizmet/kategori", placeholder="örn. nöbetçi eczane")
    else:
        term = term_choice

max_results = st.slider(
    "Sorgu başına maksimum sonuç", min_value=5, max_value=120, value=40, step=5,
    help="Google Maps TEK bir sorguda pratikte ~120 sonuca kadar veriyor; bu gerçek "
    "bir Google sınırı, aşamıyoruz. Daha fazlası için aşağıdaki seçenekleri kullanın.",
)

expand_all = st.checkbox(
    "Her ilde 120 sınırını aşacak şekilde TÜM ilçeleri tek tek tara",
    value=turkey_wide,
    disabled=ilce is not None,
    help="'(Tüm il)' veya '(Tüm Türkiye)' seçiliyken kullanılabilir. Bir il sorgusu "
    "120 sınırına takılırsa o ilin tüm ilçelerini ayrı ayrı tarayıp sonuçları "
    "birleştirir. Büyük iller için epey uzun sürebilir.",
)

auto_save = st.checkbox(
    "Her il bitince otomatik olarak veritabanına kaydet (önerilir)",
    value=turkey_wide,
    help="Uzun sürecek taramalarda (özellikle Tüm Türkiye) bağlantı kesilirse o ana "
    "kadar taranan iller kaybolmasın diye her il tamamlandığında otomatik kaydeder. "
    "Kapatırsanız kayıt sadece elle 'Dataya Aktar'a bastığınızda olur.",
)

if turkey_wide:
    st.warning(
        "Tüm Türkiye taraması 81 ili (gerekirse ilçeleriyle) tek tek gezer, "
        "saatler sürebilir ve bu tarayıcı sekmesinin açık kalmasını gerektirir. "
        "Uzun süreli gözetimsiz taramalar için CLI'daki `seed-jobs` + `run` "
        "komutları (arka planda, tarayıcı gerektirmeden çalışır) daha uygundur."
    )

fetch_clicked = st.button("🔍 Verileri Çek", type="primary", disabled=not term)

if fetch_clicked:
    progress_bar = st.progress(0, text="Aranıyor...")
    status_text = st.empty()
    st.session_state.saved_count = 0

    def _scrape_one_il(il_adi: str, on_progress) -> list[dict]:
        if expand_all:
            return scrape_all_ilceler(
                il_adi, term, max_results_per_query=max_results, progress_callback=on_progress
            )

        def _cb(done: int, total: int, name: str | None) -> None:
            on_progress(il_adi, done, total, name)

        return scrape_preview(il_adi, None, term, max_results=max_results, progress_callback=_cb)

    all_results: list[dict] = []
    error: Exception | None = None

    with st.spinner("Google Maps taranıyor, bu biraz zaman alabilir..."):
        try:
            if turkey_wide:
                for il_index, il_adi in enumerate(iller, start=1):

                    def _on_progress(bolge: str, done: int, total: int, name: str | None) -> None:
                        ratio = done / total if total else 0
                        status_text.text(f"[{il_index}/{len(iller)}] {il_adi} -> {bolge}")
                        progress_bar.progress(
                            ratio, text=f"{il_adi} [{bolge}] {done}/{total}: {name or ''}"
                        )

                    il_results = _scrape_one_il(il_adi, _on_progress)
                    for row in il_results:
                        row["_source_il"] = il_adi
                    all_results.extend(il_results)

                    if auto_save and il_results:
                        saved = asyncio.run(save_results(il_adi, None, term, il_results))
                        st.session_state.saved_count += saved
            elif ilce is None and expand_all:
                def _on_progress(bolge: str, done: int, total: int, name: str | None) -> None:
                    ratio = done / total if total else 0
                    status_text.text(f"Taranıyor: {bolge}")
                    progress_bar.progress(ratio, text=f"[{bolge}] {done}/{total}: {name or ''}")

                all_results = scrape_all_ilceler(
                    il, term, max_results_per_query=max_results, progress_callback=_on_progress
                )
                if auto_save and all_results:
                    saved = asyncio.run(save_results(il, None, term, all_results))
                    st.session_state.saved_count += saved
            else:
                def _on_progress(done: int, total: int, name: str | None) -> None:
                    ratio = done / total if total else 0
                    progress_bar.progress(ratio, text=f"{done}/{total}: {name or ''}")

                all_results = scrape_preview(
                    il, ilce, term, max_results=max_results, progress_callback=_on_progress
                )
                if auto_save and all_results:
                    saved = asyncio.run(save_results(il, ilce, term, all_results))
                    st.session_state.saved_count += saved
        except Exception as exc:  # noqa: BLE001 - kullanıcıya okunabilir hata göster
            error = exc

    progress_bar.empty()
    status_text.empty()

    if error is not None:
        kayit_notu = "otomatik kaydedildi" if auto_save else "'Dataya Aktar' ile kaydedebilirsiniz"
        st.error(
            f"Tarama sırasında hata oluştu: {error}\n\n"
            f"O ana kadar toplanan {len(all_results)} sonuç aşağıda görüntüleniyor ({kayit_notu})."
        )

    st.session_state.results = all_results
    st.session_state.meta = {"il": il, "ilce": ilce, "term": term, "turkey_wide": turkey_wide}
    if all_results:
        st.success(f"{len(all_results)} sonuç bulundu.")
    else:
        st.warning("Sonuç bulunamadı.")

if st.session_state.saved_count:
    st.info(f"Otomatik kayıt: şu ana kadar {st.session_state.saved_count} kayıt veritabanına yazıldı.")

if st.session_state.results:
    df = pd.DataFrame(st.session_state.results)
    display_columns = [
        c
        for c in ["name", "category", "address", "phone", "website", "rating", "review_count"]
        if c in df.columns
    ]
    st.dataframe(df[display_columns], use_container_width=True, hide_index=True)

    meta = st.session_state.meta
    kaynak = "Tüm Türkiye" if meta["turkey_wide"] else (meta["ilce"] or meta["il"])
    st.caption(f"Kaynak: {meta['term']} / {kaynak}")

    if st.button("💾 Dataya Aktar (kalanları da kaydet)"):
        with st.spinner("Veritabanına yazılıyor..."):
            if meta["turkey_wide"]:
                # Tüm Türkiye sonuçlarında her satır kendi ilini/ilçesini
                # `_source_ilce`/scrape sırasında bilinen bilgiyle taşımıyor
                # olabilir (auto_save kapalıysa); güvenli tarafta kalmak için
                # il bazında yeniden gruplayıp kaydediyoruz.
                by_il: dict[str, list[dict]] = {}
                for row in st.session_state.results:
                    by_il.setdefault(row.get("_source_il", meta["il"]), []).append(row)
                saved = 0
                for il_adi, rows in by_il.items():
                    saved += asyncio.run(save_results(il_adi, None, meta["term"], rows))
            else:
                saved = asyncio.run(
                    save_results(meta["il"], meta["ilce"], meta["term"], st.session_state.results)
                )
        st.success(f"{saved} kayıt veritabanına aktarıldı (place_id'ye göre tekilleştirildi).")
