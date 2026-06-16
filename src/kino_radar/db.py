"""SQLite: screenings, watchlist, tmdb_cache. Dedup + aliasy kin przed zapisem."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from .config import CINEMA_ALIASES
from .models import Screening, WatchlistItem

DEFAULT_DB = Path("kina.sqlite")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS screenings (
    cinema         TEXT NOT NULL,
    title          TEXT NOT NULL,
    original_title TEXT,
    imdb_id        TEXT,
    tmdb_id        INTEGER,
    date           TEXT NOT NULL,
    time           TEXT NOT NULL,
    cinema_type    TEXT NOT NULL,
    url            TEXT NOT NULL,
    PRIMARY KEY (cinema, title, date, time)
);
CREATE TABLE IF NOT EXISTS watchlist (
    slug    TEXT PRIMARY KEY,
    title   TEXT NOT NULL,
    year    INTEGER,
    imdb_id TEXT,
    tmdb_id INTEGER
);
CREATE TABLE IF NOT EXISTS tmdb_cache (
    query          TEXT PRIMARY KEY,
    tmdb_id        INTEGER,
    original_title TEXT,
    year           INTEGER
);
"""


def connect(path: Path | str = DEFAULT_DB) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def _canon_cinema(name: str) -> str:
    return CINEMA_ALIASES.get(name, name)


def save_screenings(conn: sqlite3.Connection, screenings: Iterable[Screening]) -> int:
    """Zapis z dedupem po (cinema, title, date, time). Aliasy kin przed zapisem."""
    rows = [
        (_canon_cinema(s.cinema), s.title, s.original_title, s.imdb_id, s.tmdb_id,
         s.date, s.time, s.cinema_type, s.url)
        for s in screenings
    ]
    conn.executemany(
        "INSERT OR REPLACE INTO screenings "
        "(cinema, title, original_title, imdb_id, tmdb_id, date, time, cinema_type, url) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return len(rows)


def save_watchlist(conn: sqlite3.Connection, items: Iterable[WatchlistItem]) -> int:
    rows = [(i.slug, i.title, i.year, i.imdb_id, i.tmdb_id) for i in items]
    conn.executemany(
        "INSERT OR REPLACE INTO watchlist (slug, title, year, imdb_id, tmdb_id) "
        "VALUES (?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return len(rows)


def get_cached_tmdb(conn: sqlite3.Connection, query: str) -> Optional[sqlite3.Row]:
    cur = conn.execute(
        "SELECT tmdb_id, original_title, year FROM tmdb_cache WHERE query = ?",
        (query,),
    )
    return cur.fetchone()


def put_cached_tmdb(conn: sqlite3.Connection, query: str, tmdb_id: Optional[int],
                    original_title: Optional[str], year: Optional[int]) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO tmdb_cache (query, tmdb_id, original_title, year) "
        "VALUES (?,?,?,?)",
        (query, tmdb_id, original_title, year),
    )
    conn.commit()
