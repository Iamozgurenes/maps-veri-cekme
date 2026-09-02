"""Kısayol: `python scripts/init_db.py` ile veritabanı tablolarını oluşturur.
Eşdeğeri: `python -m maps_scraper.cli init-db`
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from maps_scraper.db.session import init_db  # noqa: E402

if __name__ == "__main__":
    asyncio.run(init_db())
    print("Tablolar oluşturuldu.")
