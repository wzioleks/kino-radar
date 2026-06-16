"""Scraper Helios Forum Gdańsk + Metropolia — CMS JSON API.

Endpoint (ustalony w rekonesansie):
  GET https://api.helios.pl/api/v1/cinemas/{cmsId}/screenings

Jeden request na kino zwraca cały repertuar:
  data.movies[m{id}]                     -> {title, titleOriginal, slug, id}
  data.screenings[YYYY-MM-DD][m{id}].screenings[]
                                         -> {timeFrom, sourceId, cinemaSourceId}

URL biletu: https://bilety.helios.pl/screen/{sourceId}?cinemaId={cinemaSourceId}
imdb_id niedostępny (jest tylko imdbRating); titleOriginal zwykle obecny.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from ..config import DAYS_AHEAD, HELIOS_CINEMAS, REQUEST_DELAY_S
from ..models import Screening

log = logging.getLogger(__name__)

API = "https://api.helios.pl/api/v1/cinemas/{cms_id}/screenings"
TICKET = "https://bilety.helios.pl/screen/{sid}?cinemaId={cid}"


def _parse(data: dict, cinema_name: str, max_dates: int) -> list[Screening]:
    movies = data.get("movies") or {}
    by_date = data.get("screenings") or {}
    out: list[Screening] = []
    for date in sorted(by_date)[:max_dates]:
        for movie_key, block in by_date[date].items():
            movie = movies.get(movie_key) or {}
            title = (movie.get("title") or "").strip()
            if not title:
                continue
            original = (movie.get("titleOriginal") or "").strip() or None
            for ses in block.get("screenings") or []:
                time_from = ses.get("timeFrom") or ""  # 'YYYY-MM-DD HH:MM:SS'
                _, _, time = time_from.partition(" ")
                if not time:
                    continue
                sid = ses.get("sourceId")
                cid = ses.get("cinemaSourceId")
                url = TICKET.format(sid=sid, cid=cid) if sid and cid else ""
                out.append(Screening(
                    title=title,
                    original_title=original,
                    date=date,
                    time=time[:5],
                    cinema=cinema_name,
                    cinema_type="multiplex",
                    url=url,
                ))
    return out


async def fetch(client: httpx.AsyncClient, days: int = DAYS_AHEAD) -> list[Screening]:
    """Zbiera seanse obu kin Helios. Padnięte jedno kino nie wywala drugiego."""
    screenings: list[Screening] = []
    for cinema in HELIOS_CINEMAS:
        url = API.format(cms_id=cinema.cms_id)
        await asyncio.sleep(REQUEST_DELAY_S)
        try:
            r = await client.get(url, headers={"Accept": "application/json"})
            r.raise_for_status()
            data = r.json().get("data") or {}
        except (httpx.HTTPError, ValueError) as e:
            log.warning("Helios %s: błąd pobierania: %s", cinema.name, e)
            continue
        screenings.extend(_parse(data, cinema.name, days))
    log.info("Helios: %d seansów", len(screenings))
    return screenings
