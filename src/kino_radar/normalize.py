"""Normalizacja tekstu: bez diakrytyków, interpunkcji, lowercase."""
from __future__ import annotations

import re
import unicodedata

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")

# Polskie znaki, których unicodedata nie rozkłada (ł/Ł).
_SPECIAL = str.maketrans({"ł": "l", "Ł": "l"})

# Dopiski wydania/formatu, którymi kina ozdabiają ten sam film
# ('Backrooms. Bez wyjścia - wersja rozszerzona' vs 'Backrooms. Bez wyjścia').
# Doklejane na końcu tytułu; usuwane przed porównaniem, nie przed wyświetleniem.
_EDITION = re.compile(
    r"\s+(wersja\s+\w+|2d|3d|4dx|imax|vip|dubbing|napisy|"
    r"z\s+napisami|premiera|maraton)\b.*$"
)


def strip_diacritics(text: str) -> str:
    text = text.translate(_SPECIAL)
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def normalize_title(text: str) -> str:
    """lower + bez diakrytyków + bez interpunkcji + bez dopisku wydania."""
    text = strip_diacritics(text).lower()
    text = _PUNCT.sub(" ", text)
    text = _WS.sub(" ", text).strip()
    return _EDITION.sub("", text).strip() or text
