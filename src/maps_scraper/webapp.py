"""
Streamlit uygulamasının giriş noktası.

ÖNEMLİ mimari not: `require_login()` burada, sayfa listesi (`st.navigation`)
OLUŞTURULMADAN ÖNCE çağrılıyor. Böylece giriş yapılmamış bir ziyaretçi
kenar çubuğunda sayfa isimlerini bile göremiyor -- Streamlit'in klasik
"pages/" klasör otomasyonu bunu garanti etmiyordu (sayfa navigasyonu script
içeriğinden bağımsız, framework seviyesinde render ediliyordu). Bu yüzden
sayfalar artık `pages/` klasöründe değil, `app_pages/` altında birer
fonksiyon (`render()`) olarak tanımlı ve buradan programatik olarak
`st.Page(...)` ile ekleniyor.

Çalıştırmak için: `python -m maps_scraper.cli webapp` (veya doğrudan
`streamlit run src/maps_scraper/webapp.py`).
"""

import streamlit as st

from maps_scraper.app_pages import scrape, veriler
from maps_scraper.auth import logout_button, require_login

st.set_page_config(page_title="Maps Veri Çekme", layout="wide")
require_login()

pages = [
    st.Page(scrape.render, title="Veri Çek", icon="🔍", url_path="veri-cek", default=True),
    st.Page(veriler.render, title="Veriler", icon="📊", url_path="veriler"),
]
navigation = st.navigation(pages)
logout_button()
navigation.run()
