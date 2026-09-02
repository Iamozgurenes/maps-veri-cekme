import asyncio
import logging
from dataclasses import dataclass

from playwright.async_api import Browser, async_playwright
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from maps_scraper.config import settings
from maps_scraper.db.models import Business, ScrapeJob
from maps_scraper.db.session import async_session
from maps_scraper.locations import TURKEY_LOCATIONS
from maps_scraper.proxy.pool import proxy_pool
from maps_scraper.scraper.browser import launch_browser, new_context
from maps_scraper.scraper.parser import parse_listing
from maps_scraper.scraper.rate_limit import BlockedError, polite_delay
from maps_scraper.scraper.search import collect_result_urls

log = logging.getLogger("maps_scraper.runner")

MAX_ATTEMPTS = 3


def build_query(job: ScrapeJob) -> str:
    where = f"{job.ilce}, {job.il}" if job.ilce else job.il
    return f"{job.search_term} {where}, Türkiye"


async def seed_jobs(session: AsyncSession, terms: list[str], iller: list[str] | None = None) -> int:
    """İl-seviyesi job'ları oluşturur (henüz ilçelere inmez, sadece 120
    sınırına takılanlar `fan_out` ile bölünür)."""
    target_iller = iller or list(TURKEY_LOCATIONS.keys())
    created = 0
    for il in target_iller:
        for term in terms:
            exists = await session.scalar(
                select(ScrapeJob.id).where(
                    ScrapeJob.il == il,
                    ScrapeJob.ilce.is_(None),
                    ScrapeJob.search_term == term,
                )
            )
            if exists:
                continue
            session.add(ScrapeJob(il=il, ilce=None, search_term=term, granularity="il"))
            created += 1
    await session.commit()
    return created


async def _fan_out(session: AsyncSession, job: ScrapeJob) -> None:
    ilceler = TURKEY_LOCATIONS.get(job.il, [])
    for ilce in ilceler:
        exists = await session.scalar(
            select(ScrapeJob.id).where(
                ScrapeJob.il == job.il,
                ScrapeJob.ilce == ilce,
                ScrapeJob.search_term == job.search_term,
            )
        )
        if exists:
            continue
        session.add(
            ScrapeJob(
                il=job.il,
                ilce=ilce,
                search_term=job.search_term,
                granularity="ilce",
                parent_job_id=job.id,
            )
        )


async def _claim_next_job(session: AsyncSession) -> ScrapeJob | None:
    result = await session.execute(
        select(ScrapeJob)
        .where(ScrapeJob.status == "pending")
        .order_by(ScrapeJob.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = result.scalar_one_or_none()
    if job is not None:
        job.status = "in_progress"
        await session.commit()
    return job


@dataclass
class JobTarget:
    """`_upsert_business`'ın ihtiyaç duyduğu (il, ilce, search_term) alanlarını
    taşıyan hafif bir taşıyıcı. Hem gerçek bir `ScrapeJob` hem de webapp'ten
    gelen manuel bir hedef için kullanılabilir (bkz. `save_results`)."""

    il: str
    ilce: str | None
    search_term: str


async def _upsert_business(session: AsyncSession, data: dict, job: "ScrapeJob | JobTarget") -> None:
    if not data.get("name"):
        return

    existing = None
    if data.get("place_id"):
        existing = await session.scalar(
            select(Business).where(Business.place_id == data["place_id"])
        )
    if existing is None:
        existing = await session.scalar(
            select(Business).where(
                Business.name == data["name"],
                Business.il == job.il,
                Business.ilce == job.ilce,
                Business.address == data.get("address"),
            )
        )

    fields = {
        "place_id": data.get("place_id"),
        "name": data["name"],
        "category": data.get("category"),
        "search_term": job.search_term,
        "il": job.il,
        "ilce": job.ilce,
        "address": data.get("address"),
        "phone": data.get("phone"),
        "website": data.get("website"),
        "rating": data.get("rating"),
        "review_count": data.get("review_count"),
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "opening_hours": data.get("opening_hours"),
        "raw_data": data.get("raw_data"),
    }

    if existing is not None:
        for key, value in fields.items():
            if value is not None:
                setattr(existing, key, value)
    else:
        session.add(Business(**fields))


async def save_results(il: str, ilce: str | None, search_term: str, results: list[dict]) -> int:
    """Webapp'te (Streamlit) kullanıcının önizlediği ve "Dataya Aktar"a
    bastığı sonuçları veritabanına yazar. `sync_scrape.scrape_preview` bu
    sonuçları toplar ama veritabanına dokunmaz -- kaydetme kararı kullanıcıya
    ait, bu fonksiyon o onaydan sonra çağrılır.

    `scrape_all_ilceler` ile toplanan sonuçlarda her satır kendi kaynak
    ilçesini `_source_ilce` alanında taşır (birden çok ilçeden gelen
    sonuçlar tek listede birleştiği için); varsa o kullanılır, yoksa `ilce`
    parametresine düşülür."""
    async with async_session() as session:
        for data in results:
            row_ilce = data.get("_source_ilce", ilce)
            target = JobTarget(il=il, ilce=row_ilce, search_term=search_term)
            await _upsert_business(session, data, target)
        await session.commit()
    return len(results)


async def _process_job(browser: Browser, job: ScrapeJob) -> None:
    async with async_session() as session:
        job = await session.get(ScrapeJob, job.id)
        proxy = proxy_pool.next()
        async with new_context(browser, proxy=proxy) as context:
            page = await context.new_page()
            try:
                query = build_query(job)
                urls = await collect_result_urls(page, query)

                capped = len(urls) >= settings.result_cap_threshold
                if capped and job.granularity == "il" and TURKEY_LOCATIONS.get(job.il):
                    log.info("Kırpılma sinyali: %s -> ilçelere bölünüyor", query)
                    await _fan_out(session, job)
                    job.status = "done"
                    await session.commit()
                    return

                for url in urls:
                    detail_page = await context.new_page()
                    try:
                        await detail_page.goto(url, wait_until="domcontentloaded")
                        data = await parse_listing(detail_page, detail_page.url)
                        await _upsert_business(session, data, job)
                        await session.commit()
                    finally:
                        await detail_page.close()
                    await polite_delay()

                job.status = "done"
                job.last_error = None
                await session.commit()

            except BlockedError as exc:
                log.warning("Engellendik, job yeniden kuyruğa alınıyor: %s", exc)
                job.attempts += 1
                job.last_error = str(exc)
                job.status = "pending" if job.attempts < MAX_ATTEMPTS else "failed"
                await session.commit()
                # Engelleme durumunda agresif devam etmek riski artırır; bu
                # worker için uzunca bir soğuma süresi uygula.
                await asyncio.sleep(60)

            except Exception as exc:  # noqa: BLE001 - job bazlı hataları izole ediyoruz
                log.exception("Job %s başarısız oldu", job.id)
                job.attempts += 1
                job.last_error = str(exc)
                job.status = "pending" if job.attempts < MAX_ATTEMPTS else "failed"
                await session.commit()
            finally:
                await page.close()


async def _worker(browser: Browser, worker_id: int) -> None:
    while True:
        async with async_session() as session:
            job = await _claim_next_job(session)
        if job is None:
            return
        log.info("[worker %d] job %d işleniyor: %s / %s / %s",
                  worker_id, job.id, job.il, job.ilce, job.search_term)
        await _process_job(browser, job)


async def run(concurrency: int | None = None) -> None:
    concurrency = concurrency or settings.scrape_concurrency
    async with async_playwright() as playwright:
        browser = await launch_browser(playwright)
        try:
            await asyncio.gather(*(_worker(browser, i) for i in range(concurrency)))
        finally:
            await browser.close()
