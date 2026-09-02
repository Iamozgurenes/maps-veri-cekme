from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Google Maps'in dahili kimliği (detay URL'sindeki !1s(0x...:0x...) deseninden
    # çıkarılır). Bulunamazsa None kalır; tekilleştirme o zaman uygulama
    # katmanında (name, il, ilce, address) üzerinden yapılır (bkz. runner.py).
    place_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)

    name: Mapped[str] = mapped_column(String(500))
    category: Mapped[str | None] = mapped_column(String(200), nullable=True)
    search_term: Mapped[str | None] = mapped_column(String(200), nullable=True)

    il: Mapped[str] = mapped_column(String(100), index=True)
    ilce: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)

    rating: Mapped[float | None] = mapped_column(Numeric(2, 1), nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)

    opening_hours: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    first_scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("ix_businesses_name_address", "name", "address"),
    )


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)

    il: Mapped[str] = mapped_column(String(100), index=True)
    ilce: Mapped[str | None] = mapped_column(String(100), nullable=True)
    search_term: Mapped[str] = mapped_column(String(200))
    granularity: Mapped[str] = mapped_column(String(10), default="il")  # "il" | "ilce"

    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    parent_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("scrape_jobs.id"), nullable=True
    )
    parent: Mapped["ScrapeJob | None"] = relationship(remote_side="ScrapeJob.id")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        UniqueConstraint("il", "ilce", "search_term", name="uq_scrape_job_target"),
    )
