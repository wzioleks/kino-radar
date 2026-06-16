"""Scraper publicznej watchlisty Letterboxd: letterboxd.com/{USER}/watchlist/.

Paginacja /watchlist/page/{N}/ do pierwszej pustej strony. Z każdego kafelka:
  data-item-slug  -> slug
  data-item-name  -> 'Tytuł (RRRR)'  (rok w nawiasie, opcjonalny)
Pusta strona 1 = błąd (watchlista prywatna lub nie istnieje).
"""
from __future__ import annotations

import logging
import re

import httpx
from selectolax.parser import HTMLParser

from .http import get_text
from .models import WatchlistItem

log = logging.getLogger(__name__)

BASE = "https://letterboxd.com"
_NAME_YEAR = re.compile(r"^(.*?)\s*\((\d{4})\)\s*$")


class WatchlistError(RuntimeError):
    """Watchlista pusta/prywatna lub nieosiągalna."""


def _parse_page(html: str) -> list[WatchlistItem]:
    dom = HTMLParser(html)
    items: list[WatchlistItem] = []
    for node in dom.css("[data-item-slug]"):
        slug = node.attributes.get("data-item-slug")
        name = node.attributes.get("data-item-name") or ""
        if not slug:
            continue
        m = _NAME_YEAR.match(name)
        if m:
            title, year = m.group(1).strip(), int(m.group(2))
        else:
            title, year = name.strip(), None
        items.append(WatchlistItem(slug=slug, title=title, year=year))
    return items


async def fetch(client: httpx.AsyncClient, user: str) -> list[WatchlistItem]:
    """Pobiera całą watchlistę użytkownika `user`."""
    if not user:
        raise WatchlistError("Brak LETTERBOXD_USER w .env.")

    all_items: list[WatchlistItem] = []
    page = 1
    while True:
        url = f"{BASE}/{user}/watchlist/" if page == 1 \
            else f"{BASE}/{user}/watchlist/page/{page}/"
        try:
            html = await get_text(client, url)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404 and page == 1:
                raise WatchlistError(
                    f"Watchlista '{user}' nie istnieje (404)."
                ) from e
            break  # 404 na dalszej stronie = koniec paginacji
        items = _parse_page(html)
        if not items:
            if page == 1:
                raise WatchlistError(
                    f"Watchlista '{user}' jest pusta lub prywatna "
                    f"(ustaw ją jako publiczną w ustawieniach Letterboxd)."
                )
            break
        all_items.extend(items)
        page += 1

    log.info("Letterboxd: %d filmów na watchliście '%s'", len(all_items), user)
    return all_items
