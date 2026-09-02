from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+asyncpg://maps:maps@localhost:5432/maps_scraper"

    scrape_concurrency: int = 2
    scrape_delay_min_ms: int = 1200
    scrape_delay_max_ms: int = 3500
    headless: bool = True

    proxy_list: str = ""

    # Bir arama sorgusunda Google Maps'in pratikte döndürdüğü üst sınır.
    # Bir (il|ilçe, terim) sorgusu bu sayıya yaklaşırsa runner sonucu kırpılmış
    # sayar ve o ili ilçelerine böler (fan-out).
    result_cap_threshold: int = 110

    # Sayfa navigasyonu/aksiyonları için varsayılan zaman aşımı. Playwright'ın
    # 30sn varsayılanı, aynı makinede birden çok tarayıcı context'i paralel
    # çalışırken (yüksek SCRAPE_CONCURRENCY) CPU/ağ yükünden kaynaklı yanlış
    # pozitif zaman aşımlarına yol açabiliyor; bu yüzden biraz daha toleranslı.
    page_timeout_ms: int = 45_000

    @property
    def proxies(self) -> list[str]:
        return [p.strip() for p in self.proxy_list.split(",") if p.strip()]


settings = Settings()
