#!/bin/sh
set -e

echo "Veritabanı bağlantısı bekleniyor..."
until python -c "
import asyncio
from maps_scraper.db.session import engine

async def check():
    async with engine.connect():
        pass

asyncio.run(check())
" 2>/dev/null; do
  sleep 2
done

echo "Veritabanı hazır, tablolar kontrol ediliyor/oluşturuluyor..."
python -m maps_scraper.cli init-db

exec "$@"
