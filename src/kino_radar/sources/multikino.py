"""Scraper Multikino Gdańsk — JSON API microservice 'showings'.

Endpoint (ustalony w rekonesansie):
  POST /api/microservice/auth/token            -> ustawia cookie sesji
  GET  /api/microservice/showings/cinemas/{id}/films?showingDate=YYYY-MM-DD

cinemaId Gdańsk = '0004'. Pola: filmTitle, originalTitle, releaseDate,
showingGroups[].sessions[] {startTime, bookingUrl}.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging

import httpx

from ..config import DAYS_AHEAD, REQUEST_DELAY_S
from ..models import Screening

log = logging.getLogger(__name__)

BASE = "https://www.multikino.pl/api/microservice"
SHOWINGS = f"{BASE}/showings"
AUTH_URL = f"{BASE}/auth/token"
CINEMA_ID = "0004"
CINEMA_NAME = "Multikino Gdańsk"
SITE = "https://www.multikino.pl"


async def _ensure_session(client: httpx.AsyncClient) -> None:
    """Pobiera anonimowy token sesji (cookie). Bez tego /films zwraca 401."""
    await asyncio.sleep(REQUEST_DELAY_S)
    r = await client.post(AUTH_URL, headers={"Content-Type": "application/json"})
    r.raise_for_status()


def _year(release_date: str | None) -> int | None:
    if not release_date:
        return None
    try:
        return dt.date.fromisoformat(release_date[:10]).year
    except ValueError:
        return None


def _parse_films(films: list[dict]) -> list[Screening]:
    out: list[Screening] = []
    for f in films:
        title = (f.get("filmTitle") or "").strip()
        if not title:
            continue
        original = (f.get("originalTitle") or "").strip() or None
        film_url = f.get("filmUrl") or SITE
        for group in f.get("showingGroups") or []:
            for ses in group.get("sessions") or []:
                start = ses.get("startTime")  # 'YYYY-MM-DDTHH:MM:SS'
                if not start:
                    continue
                date, _, time = start.partition("T")
                booking = ses.get("bookingUrl") or ""
                url = SITE + booking if booking.startswith("/") else (booking or film_url)
                out.append(Screening(
                    title=title,
                    original_title=original,
                    date=date,
                    time=time[:5],
                    cinema=CINEMA_NAME,
                    cinema_type="multiplex",
                    url=url,
                ))
    return out


async def fetch(client: httpx.AsyncClient, days: int = DAYS_AHEAD) -> list[Screening]:
    """Zbiera seanse Multikino Gdańsk na najbliższe `days` dni."""
    await _ensure_session(client)
    today = dt.date.today()
    screenings: list[Screening] = []
    for offset in range(days):
        day = (today + dt.timedelta(days=offset)).isoformat()
        url = f"{SHOWINGS}/cinemas/{CINEMA_ID}/films?showingDate={day}"
        await asyncio.sleep(REQUEST_DELAY_S)
        try:
            r = await client.get(url, headers={"Accept": "application/json"})
            r.raise_for_status()
            films = r.json().get("result") or []
        except (httpx.HTTPError, ValueError) as e:
            log.warning("Multikino: błąd dnia %s: %s", day, e)
            continue
        screenings.extend(_parse_films(films))
    log.info("Multikino: %d seansów", len(screenings))
    return screenings
