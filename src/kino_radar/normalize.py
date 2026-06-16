"""Normalizacja tekstu: bez diakrytyków, interpunkcji, lowercase."""
from __future__ import annotations

import re
import unicodedata

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")

# Polskie znaki, których unicodedata nie rozkłada (ł/Ł).
_SPECIAL = str.maketrans({"ł": "l", "Ł": "l"})


def strip_diacritics(text: str) -> str:
    text = text.translate(_SPECIAL)
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def normalize_title(text: str) -> str:
    """lower + bez diakrytyków + bez interpunkcji + pojedyncze spacje."""
    text = strip_diacritics(text).lower()
    text = _PUNCT.sub(" ", text)
    return _WS.sub(" ", text).strip()
