"""Kaskada dopasowania seans ↔ watchlista.

Kluczem głównym jest tmdb_id (żadne źródło nie podaje imdb_id niezawodnie).
Kolejność dla każdego seansu:
  1. imdb_id == imdb_id          (bonus, gdy oba mają — rzadkie)
  2. znormalizowany tytuł + rok  (tani filtr, bez API; tytuł oryginalny i polski)
  3. TMDb: tytuł[+rok] -> tmdb_id (cache w SQLite), match po tmdb_id

Resolver TMDb jest wstrzykiwany, więc kroki 1–2 testuje się bez sieci,
a krok 3 na zamockowanym resolverze.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Protocol

from .models import Screening, WatchlistItem
from .normalize import normalize_title

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Resolved:
    tmdb_id: int
    original_title: Optional[str]
    year: Optional[int]
    poster_path: Optional[str] = None


class Resolver(Protocol):
    """Rozwiązuje tytuł (+rok) do filmu TMDb. Zwraca None, gdy brak trafienia."""

    async def resolve(self, title: str, year: Optional[int]) -> Optional[Resolved]:
        ...


def _year_ok(a: Optional[int], b: Optional[int]) -> bool:
    """Rok zgodny, jeśli któryś nieznany albo różnica <= 1 (rozjazd premier PL)."""
    if a is None or b is None:
        return True
    return abs(a - b) <= 1


class WatchlistIndex:
    """Indeksy watchlisty do szybkiego dopasowania."""

    def __init__(self, items: list[WatchlistItem]):
        self.items = items
        self.by_norm: dict[str, list[WatchlistItem]] = {}
        self.by_imdb: dict[str, WatchlistItem] = {}
        self.tmdb_ids: set[int] = set()
        for it in items:
            self.by_norm.setdefault(normalize_title(it.title), []).append(it)
            if it.imdb_id:
                self.by_imdb[it.imdb_id] = it
            if it.tmdb_id:
                self.tmdb_ids.add(it.tmdb_id)

    def match_imdb(self, imdb_id: Optional[str]) -> Optional[WatchlistItem]:
        return self.by_imdb.get(imdb_id) if imdb_id else None

    def match_title(self, title: str, year: Optional[int]) -> Optional[WatchlistItem]:
        for cand in self.by_norm.get(normalize_title(title), []):
            if _year_ok(cand.year, year):
                return cand
        return None


async def _screening_year(s: Screening) -> Optional[int]:
    # Seanse zwykle nie niosą roku; rok dochodzi z TMDb. Zostawiamy None.
    return None


async def match(
    screenings: list[Screening],
    watchlist: list[WatchlistItem],
    resolver: Optional[Resolver] = None,
) -> list[Screening]:
    """Zwraca seanse, których film jest na watchliście (z dopiętym tmdb_id)."""
    index = WatchlistIndex(watchlist)
    posters: dict[int, str] = {}   # tmdb_id -> poster_path
    titles: dict[int, str] = {}    # tmdb_id -> tytuł oryginalny (TMDb)

    # Watchlista -> tmdb_id (dla kroku 3). Wymaga resolvera.
    if resolver is not None:
        for it in watchlist:
            if it.tmdb_id is None:
                r = await resolver.resolve(it.title, it.year)
                if r:
                    it.tmdb_id = r.tmdb_id
                    index.tmdb_ids.add(r.tmdb_id)
                    if r.poster_path:
                        posters.setdefault(r.tmdb_id, r.poster_path)
                    if r.original_title:
                        titles.setdefault(r.tmdb_id, r.original_title)

    matched: list[Screening] = []
    for s in screenings:
        hit: Optional[WatchlistItem] = None

        # 1. imdb_id (bonus)
        hit = index.match_imdb(s.imdb_id)

        # 2. znormalizowany tytuł (+oryginalny) + rok
        if hit is None:
            for cand_title in filter(None, (s.title, s.original_title)):
                hit = index.match_title(cand_title, None)
                if hit:
                    break

        # 3. TMDb -> tmdb_id
        if hit is None and resolver is not None:
            query = s.original_title or normalize_title(s.title)
            r = await resolver.resolve(query, await _screening_year(s))
            if r:
                s.tmdb_id = r.tmdb_id
                if r.poster_path:
                    posters.setdefault(r.tmdb_id, r.poster_path)
                if r.original_title:
                    titles.setdefault(r.tmdb_id, r.original_title)
                if r.tmdb_id in index.tmdb_ids:
                    hit = next((it for it in watchlist if it.tmdb_id == r.tmdb_id), None)

        if hit is not None:
            if s.tmdb_id is None:
                s.tmdb_id = hit.tmdb_id
            matched.append(s)

    for s in matched:
        if s.poster_path is None and s.tmdb_id in posters:
            s.poster_path = posters[s.tmdb_id]
        if s.tmdb_id in titles:
            s.original_title = titles[s.tmdb_id]

    log.info("Matcher: %d/%d seansów z watchlisty", len(matched), len(screenings))
    return matched
