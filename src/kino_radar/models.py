"""Wspólne modele danych dla całego pipeline'u."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

CinemaType = Literal["multiplex", "studyjne"]


@dataclass(slots=True)
class Screening:
    """Pojedynczy seans w konkretnym kinie, dniu i godzinie."""

    title: str
    date: str  # ISO 'YYYY-MM-DD'
    time: str  # 'HH:MM'
    cinema: str
    cinema_type: CinemaType
    url: str
    original_title: Optional[str] = None
    imdb_id: Optional[str] = None
    tmdb_id: Optional[int] = None

    @property
    def dedup_key(self) -> tuple[str, str, str, str]:
        """Klucz deduplikacji: (kino, tytuł, data, godzina)."""
        return (self.cinema, self.title, self.date, self.time)


@dataclass(slots=True)
class WatchlistItem:
    """Film z publicznej watchlisty Letterboxd."""

    slug: str
    title: str
    year: Optional[int] = None
    imdb_id: Optional[str] = None
    tmdb_id: Optional[int] = None
