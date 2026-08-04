"""Scraper Kina na 100czni — plenerowe seanse na terenie dawnej Stoczni Gdańskiej.

Wstęp wolny i bez biletów, więc kina nie ma w żadnym agregatorze (te ciągną dane
z systemów biletowych). Cykl idzie co dwa tygodnie, ~21:00 pod żurawiami.

Źródłem jest lista wydarzeń /program/ (WordPress + Elementor). REST API
/wp-json/wp/v2/wydarzenia wygląda wygodniej, ale pola ACF są puste i data seansu
w nim nie występuje — w treści stoi tylko „po zachodzie słońca". Data i godzina
są wyłącznie w kafelku na /program/, dlatego parsujemy HTML.

Klasy Elementora są generowane (elementor-element-eb3f1a2), więc nie da się na
nich oprzeć. Stabilne jest to, że kafelek zawiera dzień, 'Miesiąc // RRRR',
zakres godzin i link do wydarzenia jako pierwszy <a>.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import re

import httpx
from selectolax.parser import HTMLParser

from ..config import DAYS_AHEAD, REQUEST_DELAY_S
from ..models import Screening

log = logging.getLogger(__name__)

SITE = "https://100cznia.pl"
PROGRAM = f"{SITE}/program/"
CINEMA_NAME = "Kino na 100czni"

# Kafelki podają miesiąc w mianowniku, inaczej niż Żak (dopełniacz).
_MONTHS = {
    "styczeń": 1, "luty": 2, "marzec": 3, "kwiecień": 4, "maj": 5,
    "czerwiec": 6, "lipiec": 7, "sierpień": 8, "wrzesień": 9,
    "październik": 10, "listopad": 11, "grudzień": 12,
}
_MONTH_ALT = "|".join(_MONTHS)

# '11 Sierpień // 2026 21:00-22:30'; godzina bywa nieustalona ('??:??') lub brak.
_WHEN = re.compile(
    rf"(\d{{1,2}})\s+({_MONTH_ALT})\s*//\s*(\d{{4}})", re.IGNORECASE
)
_TIME = re.compile(r"\b(\d{1,2}):(\d{2})\b")

# Tylko seanse cyklu; 'urodziny' czy 'Targ Miejski' to nie kino, choć bywają
# tam pokazy filmowe bez podanego repertuaru.
_IS_SCREENING = re.compile(r"kino\s+na\s+100czni", re.IGNORECASE)
# 'KINO NA 100CZNI #8: NIEDŹWIEDZICA' -> 'NIEDŹWIEDZICA'
_PREFIX = re.compile(r"^kino\s+na\s+100czni[^:]*:\s*", re.IGNORECASE)


def _tiles(html: str) -> list:
    return [
        node for node in HTMLParser(html).css("div")
        if "e-loop-item" in (node.attributes.get("class") or "")
    ]


def _pretty(title: str) -> str:
    """'NIEDŹWIEDZICA' -> 'Niedźwiedzica'; tytuły mieszane zostawiamy jak są."""
    letters = [ch for ch in title if ch.isalpha()]
    if letters and all(ch.isupper() for ch in letters):
        return title.capitalize()
    return title


def _poster(tile) -> str | None:
    for img in tile.css("img[src]"):
        src = img.attributes.get("src") or ""
        if src.startswith("http"):
            return src
    return None


def _parse_tile(tile, today: dt.date) -> Screening | None:
    link = tile.css_first("a[href]")
    if link is None:
        return None
    raw_title = re.sub(r"\s+", " ", link.text()).strip()
    if not _IS_SCREENING.search(raw_title):
        return None

    text = re.sub(r"\s+", " ", tile.text())
    when = _WHEN.search(text)
    if when is None:
        log.debug("100cznia: kafelek bez daty: %s", raw_title)
        return None
    day, month, year = int(when.group(1)), when.group(2).lower(), int(when.group(3))
    try:
        date = dt.date(year, _MONTHS[month], day)
    except ValueError:
        log.warning("100cznia: zła data w '%s'", raw_title)
        return None

    # Godzina stoi po dacie; przed nią żadnej nie ma, więc szukamy od tego miejsca.
    clock = _TIME.search(text, when.end())
    if clock is None:
        # Zdarza się przy zapowiedziach — godzinę dopisują bliżej terminu.
        log.info("100cznia: '%s' (%s) bez godziny, pomijam", raw_title, date)
        return None
    hour, minute = int(clock.group(1)), int(clock.group(2))
    if hour > 23 or minute > 59:
        return None

    title = _pretty(_PREFIX.sub("", raw_title).strip())
    if not title:
        return None

    return Screening(
        title=title,
        date=date.isoformat(),
        time=f"{hour:02d}:{minute:02d}",
        cinema=CINEMA_NAME,
        cinema_type="studyjne",
        url=link.attributes.get("href") or PROGRAM,
        poster_path=_poster(tile),
    )


def _parse_program(html: str, today: dt.date) -> list[Screening]:
    out: list[Screening] = []
    for tile in _tiles(html):
        screening = _parse_tile(tile, today)
        if screening is not None:
            out.append(screening)
    return out


async def fetch(client: httpx.AsyncClient, days: int = DAYS_AHEAD) -> list[Screening]:
    """Zbiera seanse Kina na 100czni na najbliższe `days` dni."""
    today = dt.date.today()
    horizon = (today + dt.timedelta(days=days)).isoformat()
    start = today.isoformat()

    await asyncio.sleep(REQUEST_DELAY_S)
    r = await client.get(PROGRAM)
    r.raise_for_status()

    screenings = [
        s for s in _parse_program(r.text, today)
        if start <= s.date <= horizon
    ]
    log.info("100cznia: %d seansów", len(screenings))
    return screenings
