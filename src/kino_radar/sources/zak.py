"""Scraper Kina Żak (Klub Żak) — bezpośrednio ze strony kina.

coigdzie podaje Żaka spóźnionego o tydzień (Żak aktualizuje repertuar w środy),
a własna strona wystawia program ~miesiąc naprzód, razem z tytułem oryginalnym
i plakatem. Dlatego Żaka bierzemy u źródła; coigdzie zostaje jako zapas, bo
duplikaty ucina wspólna deduplikacja w main.

Kalendarz  /pl/kalendarz?category=kino -> kafelki a.box, href '...~z{id}'
Wydarzenie:
    h1                      -> tytuł polski (czasem z prefiksem cyklu)
    h2                      -> 'Tytuł oryginalny – reżyser – kraj – 1995 – 82 min.'
    div.info z h3           -> godziny tekstem: '7-9 sierpnia o 20:15'
    h5.date-info            -> zapas dla pokazów jednorazowych: '22 Sie 16:00'
    img *.webp              -> plakat (pełny URL, nie ścieżka TMDb)

Godziny nie podają roku, więc dopisujemy najbliższe wystąpienie daty — inaczej
przełom grudnia i stycznia wyrzucałby seanse do przeszłości.
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

SITE = "https://klubzak.com.pl"
CALENDAR = f"{SITE}/pl/kalendarz?category=kino"
CINEMA_NAME = "Kino Żak"

_MONTHS = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5,
    "czerwca": 6, "lipca": 7, "sierpnia": 8, "września": 9,
    "października": 10, "listopada": 11, "grudnia": 12,
}
_MONTHS_SHORT = {
    "sty": 1, "lut": 2, "mar": 3, "kwi": 4, "maj": 5, "cze": 6,
    "lip": 7, "sie": 8, "wrz": 9, "paź": 10, "lis": 11, "gru": 12,
}
_MONTH_ALT = "|".join(_MONTHS)

# Separator pól w h2 to myślnik w spacjach — sam myślnik zostaje w tytule
# ('Spider-Man'), więc nie wolno dzielić po każdym wystąpieniu.
_FIELD_SPLIT = re.compile(r"\s+[-–—]\s+")
_DASH = r"[-–—]"

# '7-9 sierpnia o 20:15' / '31 lipca - 2 sierpnia o 18:00' (miesiąc bywa raz)
_RANGE = re.compile(
    rf"(\d{{1,2}})\s*(?:({_MONTH_ALT}))?\s*{_DASH}\s*(\d{{1,2}})\s+({_MONTH_ALT})"
)
_SINGLE = re.compile(rf"(\d{{1,2}})\s+({_MONTH_ALT})")
_TIME = re.compile(r"\bo\s+(\d{1,2}):(\d{2})")
_YEAR = re.compile(r"^(?:19|20)\d{2}$")
# '22 Sie 16:00' z kafelka daty
_TILE = re.compile(r"(\d{1,2})\s+(\w{3})\w*\s+(\d{1,2}):(\d{2})")

# Prefiks cyklu przed tytułem ('DKF ŻAK: Funny Games'). Bez 'kino', żeby nie
# uciąć tytułu filmu, który tak się zaczyna.
_CYCLE_PREFIX = re.compile(
    r"^(?:dkf[^:]*|seans[^:]*|pokaz[^:]*|przegl[ąa]d[^:]*|maraton[^:]*):\s*",
    re.IGNORECASE,
)

# Bloki div.info, w których godziny nie występują — pomijamy, żeby cennik
# ('14 zł - Poniedziałki') nigdy nie trafił do parsera dat.
_SKIP_BLOCKS = ("miejsce", "bilety")

_MAX_RUN_DAYS = 60  # bezpiecznik: dłuższy zakres to błąd parsowania, nie repertuar


def _nearest(day: int, month: int, today: dt.date) -> dt.date | None:
    """Najbliższe wystąpienie (dzień, miesiąc) względem dziś."""
    best: dt.date | None = None
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            cand = dt.date(year, month, day)
        except ValueError:
            continue  # np. 30 lutego
        if best is None or abs((cand - today).days) < abs((best - today).days):
            best = cand
    return best


def _parse_times(text: str, today: dt.date) -> list[tuple[str, str]]:
    """'7-9 sierpnia o 20:15' -> [('2026-08-07', '20:15'), ...] po jednym na dzień."""
    out: list[tuple[str, str]] = []
    for line in text.splitlines():
        tm = _TIME.search(line)
        if not tm:
            continue
        hour, minute = int(tm.group(1)), int(tm.group(2))
        if hour > 23 or minute > 59:
            continue
        time = f"{hour:02d}:{minute:02d}"
        when = line[:tm.start()]

        span = _RANGE.search(when)
        if span:
            first, month_from, last, month_to = span.groups()
            start = _nearest(int(first), _MONTHS[month_from or month_to], today)
            end = _nearest(int(last), _MONTHS[month_to], today)
            if start is None or end is None:
                continue
            if end < start:  # zakres przez Nowy Rok
                end = end.replace(year=end.year + 1)
            if (end - start).days > _MAX_RUN_DAYS:
                log.debug("Żak: podejrzany zakres %s..%s, pomijam", start, end)
                continue
            day = start
            while day <= end:
                out.append((day.isoformat(), time))
                day += dt.timedelta(days=1)
            continue

        one = _SINGLE.search(when)
        if one:
            date = _nearest(int(one.group(1)), _MONTHS[one.group(2)], today)
            if date is not None:
                out.append((date.isoformat(), time))
    return out


def _block_text(node) -> str:
    """Tekst bloku z <br> zamienionym na nowe linie (jedna linia = jeden wpis)."""
    html = re.sub(r"<br\s*/?>", "\n", node.html or "")
    return HTMLParser(html).text()


def _showtimes(dom, today: dt.date) -> list[tuple[str, str]]:
    """Godziny ze wszystkich bloków opisowych, z zapasem w kafelku daty.

    Nagłówek bloku bywa różny ('Seanse', ale też 'Seans z dyskusją'), więc
    zamiast szukać po nazwie, przepuszczamy każdy blok przez parser dat.
    """
    out: list[tuple[str, str]] = []
    for node in dom.css("div.info"):
        head = node.css_first("h3")
        label = head.text().strip().lower() if head is not None else ""
        if any(skip in label for skip in _SKIP_BLOCKS):
            continue
        out.extend(_parse_times(_block_text(node), today))
    if out:
        return out

    tile = dom.css_first("h5.date-info")
    if tile is not None:
        m = _TILE.search(re.sub(r"\s+", " ", tile.text()))
        if m:
            day, short, hour, minute = m.groups()
            month = _MONTHS_SHORT.get(short.lower())
            if month is not None:
                date = _nearest(int(day), month, today)
                if date is not None:
                    out.append((date.isoformat(), f"{int(hour):02d}:{minute}"))
    return out


def _original_title(h2_text: str) -> str | None:
    """Tytuł oryginalny z 'Oryginał – reżyser – kraj – 1995 – 82 min.'.

    Filmy polskie nie mają tytułu oryginalnego i linia zaczyna się wtedy od
    reżysera ('Michael Haneke – Austria – 1997 – 108 min.'). Rozróżniamy po
    liczbie pól przed rokiem: dwa to reżyser i kraj, trzy i więcej znaczy, że
    pierwsze pole jest tytułem. W razie wątpliwości nie zwracamy nic — matcher
    poradzi sobie tytułem polskim, a zły tytuł oryginalny zepsułby dopasowanie.
    """
    fields: list[str] = []
    for field in _FIELD_SPLIT.split(h2_text):
        field = field.strip()
        if not field:
            continue
        if _YEAR.match(field):
            break
        fields.append(field)
    return fields[0] if len(fields) >= 3 else None


def _poster(dom) -> str | None:
    for img in dom.css("img[src]"):
        src = img.attributes.get("src") or ""
        if not src.lower().endswith((".webp", ".jpg", ".jpeg", ".png")):
            continue
        if "logo" in src or "herb" in src:
            continue
        return SITE + src if src.startswith("/") else src
    return None


def _parse_event(html: str, url: str, today: dt.date) -> list[Screening]:
    dom = HTMLParser(html)
    heading = dom.css_first("h1")
    if heading is None:
        return []
    title = _CYCLE_PREFIX.sub("", heading.text().strip()).strip()
    if not title:
        return []

    meta = dom.css_first("h2")
    original = None
    if meta is not None:
        original = _original_title(re.sub(r"\s+", " ", meta.text()).strip())

    poster = _poster(dom)
    return [
        Screening(
            title=title,
            date=date,
            time=time,
            cinema=CINEMA_NAME,
            cinema_type="studyjne",
            url=url,
            original_title=original,
            poster_path=poster,
        )
        for date, time in _showtimes(dom, today)
    ]


def _event_links(html: str) -> list[str]:
    """Linki wydarzeń z kalendarza ('~z' = seans, '~pr' = cykl/przegląd)."""
    seen: set[str] = set()
    out: list[str] = []
    for box in HTMLParser(html).css("a.box[href]"):
        href = box.attributes.get("href") or ""
        if "~z" in href and href not in seen:
            seen.add(href)
            out.append(href)
    return out


async def fetch(client: httpx.AsyncClient, days: int = DAYS_AHEAD) -> list[Screening]:
    """Zbiera seanse Kina Żak na najbliższe `days` dni."""
    today = dt.date.today()
    horizon = (today + dt.timedelta(days=days)).isoformat()
    start = today.isoformat()

    await asyncio.sleep(REQUEST_DELAY_S)
    r = await client.get(CALENDAR)
    r.raise_for_status()

    screenings: list[Screening] = []
    for href in _event_links(r.text):
        await asyncio.sleep(REQUEST_DELAY_S)
        url = SITE + href
        try:
            page = await client.get(url)
            page.raise_for_status()
        except httpx.HTTPError as e:
            log.warning("Żak: nie pobrano %s: %s", href, e)
            continue
        for s in _parse_event(page.text, url, today):
            if start <= s.date <= horizon:
                screenings.append(s)

    log.info("Żak: %d seansów", len(screenings))
    return screenings
