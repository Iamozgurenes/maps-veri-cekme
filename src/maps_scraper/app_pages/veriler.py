"""
Toplanan işletme verilerini filtreleyip görüntüleme/indirme sayfası.

`webapp.py` bu modüldeki `render()` fonksiyonunu `st.navigation` üzerinden
çağırır. Giriş kontrolü merkezi olarak webapp.py'de yapıldığı için bu sayfa
kendi başına ayrıca require_login() çağırmaz -- zaten sayfa listesi bile
giriş yapılmadan oluşturulmuyor.
"""

import asyncio

import pandas as pd
import streamlit as st
from sqlalchemy import delete, distinct, func, or_, select

from maps_scraper.db.models import Business
from maps_scraper.db.session import async_session

_DISPLAY_COLUMNS = [
    "name", "category", "il", "ilce", "address", "phone", "website",
    "rating", "review_count", "search_term", "last_seen_at",
]
_EXTRA_COLUMNS = ["place_id", "latitude", "longitude", "opening_hours", "first_scraped_at"]

# Bar grafikte okunabilirlik için en fazla bu kadar il gösterilir (81 il tek
# grafikte sıkışık/okunaksız olur) -- kalanlar "Diğer" olarak toplanmaz,
# sadece grafikten dışarıda bırakılır, tablo/CSV'de zaten hepsi mevcut.
_CHART_TOP_N = 15


async def _distinct_values(column, where=None) -> list[str]:
    async with async_session() as session:
        query = select(distinct(column)).where(column.is_not(None))
        if where is not None:
            query = query.where(where)
        result = await session.execute(query.order_by(column))
        return [row[0] for row in result.all()]


@st.cache_data(ttl=60)
def _get_iller_and_terms() -> tuple[list[str], list[str]]:
    async def _all():
        iller = await _distinct_values(Business.il)
        terms = await _distinct_values(Business.search_term)
        return iller, terms

    return asyncio.run(_all())


def _get_ilceler(il: str | None) -> list[str]:
    if not il:
        return []
    return asyncio.run(_distinct_values(Business.ilce, where=Business.il == il))


@st.cache_data(ttl=30)
def _get_overview() -> tuple[int, pd.DataFrame]:
    async def _query():
        async with async_session() as session:
            total = await session.scalar(select(func.count()).select_from(Business))
            result = await session.execute(
                select(Business.il, func.count())
                .group_by(Business.il)
                .order_by(func.count().desc())
            )
            df = pd.DataFrame(result.all(), columns=["il", "kayıt"])
            return total or 0, df

    return asyncio.run(_query())


async def _delete_all_businesses() -> int:
    async with async_session() as session:
        result = await session.execute(delete(Business))
        await session.commit()
        return result.rowcount


def _fetch(il, ilce, term, min_rating, search_text, limit):
    async def _query():
        async with async_session() as session:
            conditions = []
            if il:
                conditions.append(Business.il == il)
            if ilce:
                conditions.append(Business.ilce == ilce)
            if term:
                conditions.append(Business.search_term == term)
            if min_rating > 0:
                conditions.append(Business.rating >= min_rating)
            if search_text:
                like = f"%{search_text}%"
                conditions.append(or_(Business.name.ilike(like), Business.address.ilike(like)))

            count_query = select(func.count()).select_from(Business)
            rows_query = select(Business).order_by(Business.last_seen_at.desc()).limit(limit)
            for condition in conditions:
                count_query = count_query.where(condition)
                rows_query = rows_query.where(condition)

            total = await session.scalar(count_query)
            rows = (await session.execute(rows_query)).scalars().all()
            return total, rows

    return asyncio.run(_query())


@st.dialog("⚠️ Tüm verileri sil")
def _confirm_delete_dialog() -> None:
    st.write(
        "Bu işlem veritabanındaki **tüm işletme kayıtlarını** kalıcı olarak "
        "silecek. Bu geri alınamaz."
    )
    confirm_text = st.text_input("Onaylamak için büyük harflerle **SİL** yazın")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Vazgeç", width="stretch"):
            st.rerun()
    with col2:
        if st.button(
            "Evet, kalıcı olarak sil",
            type="primary",
            width="stretch",
            disabled=confirm_text != "SİL",
        ):
            deleted = asyncio.run(_delete_all_businesses())
            _get_overview.clear()
            _get_iller_and_terms.clear()
            st.success(f"{deleted} kayıt silindi.")
            st.rerun()


def render() -> None:
    st.title("📊 Toplanan Veriler")

    total_all, counts_by_il = _get_overview()

    overview_col, action_col = st.columns([3, 1])
    with overview_col:
        st.metric("Toplam kayıt (tüm veritabanı)", total_all)
        if not counts_by_il.empty:
            chart_df = counts_by_il.head(_CHART_TOP_N).set_index("il")
            st.caption(f"İl bazında kayıt sayısı (ilk {min(_CHART_TOP_N, len(counts_by_il))} il)")
            st.bar_chart(chart_df, horizontal=True)
    with action_col:
        st.write("")
        st.write("")
        if st.button("🗑️ Tüm verileri sil", width="stretch"):
            _confirm_delete_dialog()

    st.divider()

    iller, terms = _get_iller_and_terms()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        il_choice = st.selectbox("İl", ["(Tümü)"] + iller)
        il = None if il_choice == "(Tümü)" else il_choice
    with col2:
        ilce_options = _get_ilceler(il)
        ilce_choice = st.selectbox("İlçe", ["(Tümü)"] + ilce_options)
        ilce = None if ilce_choice == "(Tümü)" else ilce_choice
    with col3:
        term_choice = st.selectbox("Hizmet / kategori", ["(Tümü)"] + terms)
        term = None if term_choice == "(Tümü)" else term_choice
    with col4:
        min_rating = st.slider("Min. puan", 0.0, 5.0, 0.0, step=0.5)

    search_col, limit_col, extra_col = st.columns([2, 1, 1])
    with search_col:
        search_text = st.text_input("İsim / adreste ara", placeholder="örn. Kadıköy diş")
    with limit_col:
        limit = st.number_input("Maks. satır", min_value=100, max_value=20_000, value=2000, step=100)
    with extra_col:
        show_extra = st.checkbox("Tüm sütunlar", value=False, help="Koordinat, çalışma saatleri vb.")

    total, rows = _fetch(il, ilce, term, min_rating, search_text, limit)

    st.metric("Eşleşen kayıt sayısı", total or 0)
    if total and total > limit:
        st.caption(f"Sadece ilk {limit} satır gösteriliyor -- daha fazlası için 'Maks. satır'ı artırın.")

    if rows:
        records = []
        columns = _DISPLAY_COLUMNS + (_EXTRA_COLUMNS if show_extra else [])
        for row in rows:
            records.append({col: getattr(row, col) for col in columns})
        df = pd.DataFrame(records).fillna("")
        st.dataframe(df, width="stretch", hide_index=True)

        st.download_button(
            "⬇️ CSV olarak indir",
            data=df.to_csv(index=False).encode("utf-8-sig"),
            file_name="maps_veri.csv",
            mime="text/csv",
        )
    else:
        st.info("Filtrelere uyan kayıt bulunamadı.")
