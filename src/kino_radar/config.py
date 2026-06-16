"""Konfiguracja z .env + stałe źródeł (cinema ID ustalone w rekonesansie)."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# Odstęp między requestami do tego samego źródła (rate limiting).
REQUEST_DELAY_S = 1.0

# Ile dni repertuaru do przodu zbieramy.
DAYS_AHEAD = 14


@dataclass(frozen=True)
class HeliosCinema:
    name: str
    cms_id: int  # numeryczne ID w CMS API (api.helios.pl/api/v1/cinemas/{id}/screenings)


# Ustalone w rekonesansie (źródło #1). Repertuar: jeden request JSON na kino.
HELIOS_CINEMAS: tuple[HeliosCinema, ...] = (
    HeliosCinema(name="Helios Forum Gdańsk", cms_id=13),
    HeliosCinema(name="Helios Metropolia", cms_id=18),
)

# Aliasy kin scalane PRZED zapisem do db (ten sam obiekt pod różnymi nazwami).
CINEMA_ALIASES: dict[str, str] = {
    "Klub Kot": "Kino Spektrum",
}

# Kina studyjne pobierane z coigdzie.pl (źródło #3) — biały listy.
STUDYJNE_CINEMAS: frozenset[str] = frozenset({
    "Kino Żak",
    "Kino Kameralne",
    "Kino Helikon",
    "Kino Spektrum",
    "Kino Muzeum",
    "Kino IKM",
    "Cinema1",
})


def require_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(
            f"Brak zmiennej środowiskowej {name}. "
            f"Skopiuj .env.example do .env i uzupełnij."
        )
    return val


LETTERBOXD_USER = os.getenv("LETTERBOXD_USER", "")
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
