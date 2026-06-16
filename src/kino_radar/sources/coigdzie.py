"""Scraper kin studyjnych przez agregator live.coigdzie.pl.

Strona jest per-film: div.movie -> a.title (tytuł) + wiele div.cinema.row,
każdy z a.cinemaname i seansami:
    <a href="BOOKING_URL"><span class="badge-light" data-time="YYYY-MM-DD HH:MM:SS">

Bierzemy TYLKO kina z whitelisty studyjnych (multipleksy ignorujemy — są z API).
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging

import httpx
from selectolax.parser import HTMLParser

from ..config import DAYS_AHEAD, REQUEST_DELAY_S, STUDYJNE_CINEMAS, CINEMA_ALIASES
from ..models import Screening
from ..normalize import normalize_title

log = logging.getLogger(__name__)

URL_TMPL = "https://live.coigdzie.pl/miasto/Gdansk/dzien/{day}"

# coigdzie adresuje dni nazwą dnia tygodnia (dziś = '0'). Pokrywa rolujący tydzień.
COIGDZIE_MAX_DAYS = 7
# Python weekday(): poniedziałek=0 .. niedziela=6.
_WEEKDAYS = ("poniedziałek", "wtorek", "środa", "czwartek",
             "piątek", "sobota", "niedziela")


def _day_token(offset: int, today: dt.date) -> str:
    """offset 0 -> '0' (dziś); dalej -> polska nazwa dnia tygodnia."""
    if offset == 0:
        return "0"
    return _WEEKDAYS[(today + dt.timedelta(days=offset)).weekday()]

# Mapa znormalizowana nazwa-kanoniczna -> nazwa kanoniczna.
# Klucze whitelisty + aliasy (np. "Klub Kot" -> "Kino Spektrum").
_CANON: dict[str, str] = {}
for _name in STUDYJNE_CINEMAS:
    _CANON[normalize_title(_name)] = _name
for _alias, _target in CINEMA_ALIASES.items():
    _CANON[normalize_title(_alias)] = _target


def _match_cinema(raw_name: str) -> str | None:
    """Dopasowuje nazwę z coigdzie ('Kino Żak w Gdańsku') do kanonicznej.

    Kanoniczna nazwa musi być prefiksem znormalizowanej nazwy z coigdzie
    (sufiksy 'w gdansku' / 'cafe' są odrzucane).
    """
    norm = normalize_title(raw_name)
    for canon_norm, canon in _CANON.items():
        if norm == canon_norm or norm.startswith(canon_norm + " "):
            return canon
    return None


def _parse_day(html: str) -> list[Screening]:
    dom = HTMLParser(html)
    out: list[Screening] = []
    for movie in dom.css("div.movie"):
        title_node = movie.css_first("a.title")
        if not title_node:
            continue
        title = title_node.text().strip()
        for row in movie.css("div.cinema.row"):
            name_node = row.css_first("a.cinemaname")
            if not name_node:
                continue
            canon = _match_cinema(name_node.text())
            if canon is None:
                continue  # multipleks lub kino spoza whitelisty
            for link in row.css("span.shows a[href]"):
                badge = link.css_first("span.badge-light[data-time]")
                if not badge:
                    continue
                data_time = badge.attributes.get("data-time", "")  # 'YYYY-MM-DD HH:MM:SS'
                date, _, time = data_time.partition(" ")
                if not date or not time:
                    continue
                out.append(Screening(
                    title=title,
                    date=date,
                    time=time[:5],
                    cinema=canon,
                    cinema_type="studyjne",
                    url=link.attributes.get("href", ""),
                ))
    return out


async def fetch(client: httpx.AsyncClient, days: int = DAYS_AHEAD) -> list[Screening]:
    """Zbiera seanse kin studyjnych z coigdzie na najbliższe `days` dni."""
    today = dt.date.today()
    seen: set[tuple[str, str, str, str]] = set()
    screenings: list[Screening] = []
    for offset in range(min(days, COIGDZIE_MAX_DAYS)):
        url = URL_TMPL.format(day=_day_token(offset, today))
        await asyncio.sleep(REQUEST_DELAY_S)
        try:
            r = await client.get(url)
            r.raise_for_status()
        except httpx.HTTPError as e:
            log.warning("coigdzie: błąd dnia +%d: %s", offset, e)
            continue
        for sc in _parse_day(r.text):
            if sc.dedup_key not in seen:
                seen.add(sc.dedup_key)
                screenings.append(sc)
    log.info("coigdzie (studyjne): %d seansów", len(screenings))
    return screenings
