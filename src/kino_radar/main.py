"""Orkiestracja: zbierz seanse -> wczytaj watchlistę -> match -> db -> render."""
from __future__ import annotations

import asyncio
import logging

from . import db, render
from .config import DAYS_AHEAD, LETTERBOXD_USER, TMDB_API_KEY
from .http import make_client
from .letterboxd import WatchlistError, fetch as fetch_watchlist
from .matcher import match
from .models import Screening
from .normalize import normalize_title
from .sources import coigdzie, helios, multikino
from .tmdb import TmdbResolver

log = logging.getLogger(__name__)

SOURCES = {
    "helios": helios.fetch,
    "multikino": multikino.fetch,
    "coigdzie": coigdzie.fetch,
}


async def collect_screenings(client, days: int) -> list[Screening]:
    """Zbiera seanse ze wszystkich źródeł. Padnięte źródło = warning, nie crash."""
    results = await asyncio.gather(
        *(fn(client, days) for fn in SOURCES.values()),
        return_exceptions=True,
    )
    screenings: list[Screening] = []
    for name, res in zip(SOURCES, results):
        if isinstance(res, Exception):
            log.warning("Źródło '%s' padło: %s", name, res)
            continue
        screenings.extend(res)
    return screenings


def share_original_titles(screenings: list[Screening]) -> int:
    """Uzupełnia brakujące tytuły oryginalne mapą tytuł polski -> oryginalny.

    Multikino zwraca originalTitle puste dla każdego filmu, Helios podaje je
    niezawodnie. Ten sam film w obu sieciach ma praktycznie ten sam tytuł
    polski, więc mapa z Heliosa domyka lukę bez pytania TMDb.
    """
    pl_to_original: dict[str, str] = {}
    for s in screenings:
        if s.original_title:
            pl_to_original.setdefault(normalize_title(s.title), s.original_title)

    filled = 0
    for s in screenings:
        if not s.original_title:
            original = pl_to_original.get(normalize_title(s.title))
            if original:
                s.original_title = original
                filled += 1
    return filled


async def run(days: int = DAYS_AHEAD) -> None:
    conn = db.connect()
    async with make_client() as client:
        screenings = await collect_screenings(client, days)
        log.info("Zebrano %d seansów ze wszystkich źródeł", len(screenings))

        filled = share_original_titles(screenings)
        log.info("Tytuł oryginalny uzupełniony z innego źródła: %d seansów", filled)

        watchlist = await fetch_watchlist(client, LETTERBOXD_USER)

        resolver = TmdbResolver(client, conn, TMDB_API_KEY) if TMDB_API_KEY else None
        if resolver is None:
            log.warning("Brak TMDB_API_KEY — kaskada bez kroku TMDb (tylko tytuł+rok).")

        matched = await match(screenings, watchlist, resolver)

    db.save_watchlist(conn, watchlist)
    db.save_screenings(conn, matched)
    render.render(matched, LETTERBOXD_USER)
    conn.close()
    log.info("Gotowe: %d seansów z watchlisty.", len(matched))


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        asyncio.run(run())
    except WatchlistError as e:
        logging.error("Watchlista: %s", e)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
