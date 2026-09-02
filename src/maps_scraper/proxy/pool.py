"""
Basit round-robin proxy havuzu.

PROXY_LIST env değişkeni boşsa `next()` her zaman None döner ve tarayıcı
context'leri proxy'siz (yerel IP ile) açılır -- yani bu modül tamamen
opsiyoneldir/no-op'tur. Bir proxy sağlayıcısı eklemek isterseniz .env
dosyasındaki PROXY_LIST'i doldurmanız yeterli, kodda değişiklik gerekmez.
"""

import itertools
from urllib.parse import urlsplit

from maps_scraper.config import settings


class ProxyPool:
    def __init__(self, proxies: list[str] | None = None) -> None:
        proxies = proxies if proxies is not None else settings.proxies
        self._cycle = itertools.cycle(proxies) if proxies else None

    def next(self) -> dict | None:
        """Playwright'ın `proxy=` parametresine verilebilecek dict döner, ya da None."""
        if self._cycle is None:
            return None

        raw = next(self._cycle)
        parsed = urlsplit(raw)
        server = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
        proxy: dict = {"server": server}
        if parsed.username:
            proxy["username"] = parsed.username
        if parsed.password:
            proxy["password"] = parsed.password
        return proxy


proxy_pool = ProxyPool()
