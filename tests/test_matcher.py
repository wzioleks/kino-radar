"""Testy kaskady matchera. Resolver TMDb zamockowany (bez sieci)."""
from typing import Optional

import pytest

from kino_radar.matcher import Resolved, match
from kino_radar.models import Screening, WatchlistItem


def _screening(title, original=None, imdb=None, cinema="Helios Forum Gdańsk",
               ctype="multiplex"):
    return Screening(title=title, original_title=original, imdb_id=imdb,
                     date="2026-06-16", time="20:00", cinema=cinema,
                     cinema_type=ctype, url="http://x")


class FakeResolver:
    """Zwraca tmdb_id wg słownika znormalizowanych tytułów."""

    def __init__(self, mapping: dict[str, Resolved]):
        from kino_radar.normalize import normalize_title
        self._norm = normalize_title
        self.mapping = {normalize_title(k): v for k, v in mapping.items()}
        self.calls: list[str] = []

    async def resolve(self, title: str, year: Optional[int]) -> Optional[Resolved]:
        self.calls.append(title)
        return self.mapping.get(self._norm(title))


async def test_match_by_imdb_id():
    wl = [WatchlistItem(slug="a", title="Cokolwiek", imdb_id="tt0000001")]
    scr = [_screening("Inny Tytuł", imdb="tt0000001")]
    out = await match(scr, wl, resolver=None)
    assert len(out) == 1


async def test_match_by_normalized_title_no_api():
    wl = [WatchlistItem(slug="a", title="Shaun of the Dead", year=2004)]
    # różna interpunkcja/wielkość liter, ten sam tytuł
    scr = [_screening("shaun of the dead")]
    out = await match(scr, wl, resolver=None)
    assert len(out) == 1
    assert out[0].title == "shaun of the dead"


async def test_match_by_original_title():
    wl = [WatchlistItem(slug="a", title="The Sheep Detectives")]
    scr = [_screening("Sprawiedliwość owiec", original="The Sheep Detectives")]
    out = await match(scr, wl, resolver=None)
    assert len(out) == 1


async def test_no_match_without_resolver_for_translated_title():
    wl = [WatchlistItem(slug="a", title="The Devil Wears Prada 2")]
    scr = [_screening("Diabeł ubiera się u Prady 2")]  # brak original_title
    out = await match(scr, wl, resolver=None)
    assert out == []


async def test_tmdb_fallback_bridges_polish_to_original():
    wl = [WatchlistItem(slug="a", title="The Devil Wears Prada 2")]
    scr = [_screening("Diabeł ubiera się u Prady 2")]
    resolver = FakeResolver({
        "The Devil Wears Prada 2": Resolved(1314481, "The Devil Wears Prada 2", 2026),
        "Diabeł ubiera się u Prady 2": Resolved(1314481, "The Devil Wears Prada 2", 2026),
    })
    out = await match(scr, wl, resolver)
    assert len(out) == 1
    assert out[0].tmdb_id == 1314481


async def test_year_mismatch_blocks_title_match():
    wl = [WatchlistItem(slug="a", title="Backrooms", year=2026)]
    scr = [_screening("Backrooms")]  # rok seansu nieznany -> dozwolone
    out = await match(scr, wl, resolver=None)
    assert len(out) == 1


async def test_unmatched_returns_empty():
    wl = [WatchlistItem(slug="a", title="Zupełnie Inny Film", year=1990)]
    scr = [_screening("Dzień objawienia", original="Disclosure Day")]
    resolver = FakeResolver({
        "Zupełnie Inny Film": Resolved(111, "Something Else", 1990),
        "Disclosure Day": Resolved(999, "Disclosure Day", 2026),
    })
    out = await match(scr, wl, resolver)
    assert out == []
