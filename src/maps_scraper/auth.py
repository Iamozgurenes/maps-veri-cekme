"""
Webapp için basit oturum bazlı giriş kontrolü.

Bu bir çoklu kullanıcı/hesap sistemi DEĞİL -- tek bir paylaşılan kullanıcı
adı/parola ile "içeri giren görür, girmeyen görmez" seviyesinde bir kapı.
Parola kod içine gömülü değil; `AUTH_USERNAME`/`AUTH_PASSWORD` ortam
değişkenlerinden okunur (bkz. config.py). `AUTH_PASSWORD` ayarlanmadığı
sürece webapp KİMSEYE açılmaz (fail-closed) -- bu, "unutulup açık bırakılan"
bir dağıtımın yanlışlıkla herkese açık kalmasını önlemek için kasıtlı.

Streamlit'te `st.session_state` tarayıcı sekmesi/oturumu bazlıdır; sayfa
tamamen yenilenirse (yeni oturum) tekrar giriş istenir. Kalıcı "beni hatırla"
gibi bir özellik için ayrı bir çözüm (örn. imzalı çerez) gerekir -- bu basit
gate o kapsamda değil.
"""

import hmac

import streamlit as st

from maps_scraper.config import settings


def require_login() -> None:
    """Girişi doğrulanmamış bir kullanıcı için giriş formunu gösterip
    script'in geri kalanının çalışmasını durdurur (st.stop())."""
    if st.session_state.get("authenticated"):
        return

    if not settings.auth_password:
        st.error(
            "Bu uygulama için giriş yapılandırılmamış (AUTH_PASSWORD ortam "
            "değişkeni ayarlanmamış). Güvenlik nedeniyle uygulama kimseye "
            "açılmıyor -- lütfen AUTH_USERNAME ve AUTH_PASSWORD'ü ayarlayıp "
            "yeniden dağıtın."
        )
        st.stop()

    # `layout="wide"` tüm sayfaya uygulandığı için formu ortalanmış, dar bir
    # kart içine alıyoruz -- aksi halde tam ekrana yayılıp çirkin duruyor.
    st.markdown("<div style='height: 12vh'></div>", unsafe_allow_html=True)
    _, center, _ = st.columns([1, 1.1, 1])
    with center:
        with st.container(border=True):
            st.markdown(
                "<h2 style='text-align:center; margin-top:0;'>🔒 Giriş Yap</h2>",
                unsafe_allow_html=True,
            )
            with st.form("login_form"):
                username = st.text_input("Kullanıcı adı")
                password = st.text_input("Parola", type="password")
                submitted = st.form_submit_button(
                    "Giriş Yap", width="stretch", type="primary"
                )

            if submitted:
                user_ok = hmac.compare_digest(username, settings.auth_username)
                pass_ok = hmac.compare_digest(password, settings.auth_password)
                if user_ok and pass_ok:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Kullanıcı adı veya parola hatalı.")

    st.stop()


def logout_button() -> None:
    if st.session_state.get("authenticated") and st.sidebar.button("🚪 Çıkış Yap"):
        st.session_state.authenticated = False
        st.rerun()
