# Playwright'ın Chromium + gerekli OS bağımlılıklarını (fontlar, libs vb.)
# derleme sırasında kurar; sürüm uyumsuzluğu riskini önlemek için Playwright'ı
# önce requirements.txt'ten kurup, TAM O SÜRÜME uygun tarayıcıyı sonra indiriyoruz.
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY pyproject.toml requirements.txt ./
RUN pip install -r requirements.txt \
    && playwright install --with-deps chromium

# Streamlit'in ilk çalıştırmada sorduğu e-posta promptunu (interaktif olmayan
# ortamda EOF alıp takılabiliyor) baştan devre dışı bırakır.
RUN mkdir -p /root/.streamlit \
    && printf '[general]\nemail = ""\n' > /root/.streamlit/credentials.toml

COPY . .
RUN pip install -e . \
    && chmod +x docker-entrypoint.sh

EXPOSE 8501

# Entrypoint: DB hazır olana kadar bekler, tabloları oluşturur, sonra CMD'yi çalıştırır.
ENTRYPOINT ["./docker-entrypoint.sh"]

# EasyPanel'de "web" servisi bu varsayılan komutla çalışır (Streamlit arayüzü).
# "worker" servisi için EasyPanel'de Start Command'i şu şekilde override edin:
#   python -m maps_scraper.cli run
CMD ["streamlit", "run", "src/maps_scraper/webapp.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
