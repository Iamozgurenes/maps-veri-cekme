import asyncio
import logging
import subprocess
import sys
from pathlib import Path

import typer
from sqlalchemy import func, select

from maps_scraper.db.models import Business, ScrapeJob
from maps_scraper.db.session import async_session, init_db as _init_db
from maps_scraper.locations import TURKEY_LOCATIONS
from maps_scraper.scraper.runner import run as _run
from maps_scraper.scraper.runner import seed_jobs as _seed_jobs
from maps_scraper.search_terms import DEFAULT_CATEGORIES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = typer.Typer(help="Google Maps işletme veri toplama aracı")


@app.command("init-db")
def init_db() -> None:
    """Veritabanı tablolarını oluşturur."""
    asyncio.run(_init_db())
    typer.echo("Tablolar oluşturuldu.")


@app.command("seed-jobs")
def seed_jobs(
    il: list[str] = typer.Option(
        None, "--il", help="Belirli il(ler). Verilmezse 81 ilin tamamı kullanılır."
    ),
    term: list[str] = typer.Option(
        None, "--term", help="Aranacak kategori/terim. Verilmezse varsayılan liste kullanılır."
    ),
) -> None:
    """Arama kuyruğuna (scrape_jobs) il-seviyesi görevler ekler."""
    iller = list(il) if il else None
    if iller:
        bilinmeyen = [i for i in iller if i not in TURKEY_LOCATIONS]
        if bilinmeyen:
            typer.echo(f"Bilinmeyen il(ler): {', '.join(bilinmeyen)}", err=True)
            raise typer.Exit(code=1)

    terms = list(term) if term else DEFAULT_CATEGORIES

    async def _seed() -> int:
        async with async_session() as session:
            return await _seed_jobs(session, terms, iller)

    created = asyncio.run(_seed())
    typer.echo(f"{created} yeni job eklendi (terim sayısı: {len(terms)}).")


@app.command("run")
def run(
    concurrency: int = typer.Option(None, "--concurrency", help="Paralel tarayıcı sayısı."),
) -> None:
    """Bekleyen (pending) job'ları işler, sonuçları veritabanına yazar."""
    asyncio.run(_run(concurrency))


@app.command("status")
def status() -> None:
    """Job ilerlemesi ve toplam kayıt sayısını özetler."""

    async def _status() -> dict:
        async with async_session() as session:
            job_counts = dict(
                (await session.execute(
                    select(ScrapeJob.status, func.count()).group_by(ScrapeJob.status)
                )).all()
            )
            business_count = await session.scalar(select(func.count()).select_from(Business))
            return {"jobs": job_counts, "businesses": business_count}

    result = asyncio.run(_status())
    typer.echo(f"Job durumları: {result['jobs']}")
    typer.echo(f"Toplam işletme kaydı: {result['businesses']}")


@app.command("webapp")
def webapp() -> None:
    """Görsel arayüzü (Streamlit) başlatır: hizmet/il seç, çek, önizle, aktar."""
    webapp_path = Path(__file__).resolve().parent / "webapp.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(webapp_path)], check=False)


if __name__ == "__main__":
    app()
