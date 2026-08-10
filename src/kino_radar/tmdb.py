"""Resolver TMDb: tytuł (+rok) -> tmdb_id, z cache w SQLite.

Implementuje protokół matcher.Resolver. Wyniki (także puste) cache'owane,
by nie powtarzać zapytań i nie bić w rate limit między uruchomieniami.
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
from typing import Optional

import httpx

from . import db
from .config import REQUEST_DELAY_S
from .matcher import Resolved
from .normalize import normalize_title

log = logging.getLogger(__name__)

SEARCH_URL = "https://api.themoviedb.org/3/search/movie"


class TmdbResolver:
    """Rozwiązuje tytuły do filmów TMDb (z cache)."""

    def __init__(self, client: httpx.AsyncClient, conn: sqlite3.Connection,
                 api_key: str, language: str = "pl-PL"):
        self.client = client
        self.conn = conn
        self.api_key = api_key
        self.language = language

    @staticmethod
    def _cache_key(title: str, year: Optional[int]) -> str:
        return f"{normalize_title(title)}|{year or ''}"

    async def resolve(self, title: str, year: Optional[int]) -> Optional[Resolved]:
        if not title or not self.api_key:
            return None

        key = self._cache_key(title, year)
        cached = db.get_cached_tmdb(self.conn, key)
        if cached is not None:
            if cached["tmdb_id"] is None:
                return None
            return Resolved(cached["tmdb_id"], cached["original_title"],
                            cached["year"], cached["poster_path"])

        params = {"api_key": self.api_key, "query": title, "language": self.language}
        if year:
            params["year"] = year

        await asyncio.sleep(REQUEST_DELAY_S)
        try:
            r = await self.client.get(SEARCH_URL, params=params)
            r.raise_for_status()
            results = r.json().get("results") or []
        except (httpx.HTTPError, ValueError) as e:
            log.warning("TMDb: błąd zapytania %r: %s", title, e)
            return None

        if not results:
            db.put_cached_tmdb(self.conn, key, None, None, None, None)
            return None

        # Szukamy najpierw dokładnego trafienia na wypadek, gdyby TMDb rzucił śmieć na 1 miejscu
        top = results[0]
        for res in results:
            if normalize_title(res.get("title", "")) == normalize_title(title) or \
               normalize_title(res.get("original_title", "")) == normalize_title(title):
                top = res
                break

        rel = top.get("release_date") or ""
        ryear = int(rel[:4]) if rel[:4].isdigit() else None
        resolved = Resolved(top["id"], top.get("original_title"), ryear,
                            top.get("poster_path"))
        db.put_cached_tmdb(self.conn, key, resolved.tmdb_id,
                           resolved.original_title, resolved.year,
                           resolved.poster_path)
        return resolved
