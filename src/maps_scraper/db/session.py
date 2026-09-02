from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from maps_scraper.config import settings
from maps_scraper.db.models import Base

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_session() -> AsyncSession:
    return async_session()
