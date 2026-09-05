from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from maps_scraper.config import settings
from maps_scraper.db.models import Base

# NullPool: her checkout'ta yeni bir DBAPI bağlantısı açılır, checkin'de kapanır
# -- bağlantı havuzlanmaz. Bu, webapp tarafındaki her `asyncio.run(...)`
# çağrısının (Streamlit her script yeniden çalıştığında YENİ bir event loop
# oluşturur) kendi event loop'una ait yeni bir bağlantı almasını garanti eder.
# Havuzlama açık olsaydı, önceki bir asyncio.run() çağrısından kalan (artık
# kapanmış) bir event loop'a bağlı bir bağlantı yeniden kullanılmaya
# çalışılabilir ve "Future attached to a different loop" hatasına yol açardı.
# CLI'daki tek-event-loop'lu worker (runner.py) için performans maliyeti
# ihmal edilebilir düzeyde.
engine = create_async_engine(settings.database_url, echo=False, poolclass=NullPool)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_session() -> AsyncSession:
    return async_session()
