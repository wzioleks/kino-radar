"""Testy normalizacji tytułów."""
from kino_radar.normalize import normalize_title, strip_diacritics


def test_strip_polish_diacritics():
    assert strip_diacritics("Żółć łąka ŚĆ") == "Zolc laka SC"


def test_normalize_lowercases_and_strips_punctuation():
    assert normalize_title("Shaun of the Dead!") == "shaun of the dead"


def test_normalize_collapses_whitespace():
    assert normalize_title("  Diabeł   ubiera  się ") == "diabel ubiera sie"


def test_normalize_equates_translated_punctuation_variants():
    assert normalize_title("Dzień Objawienia") == normalize_title("dzien objawienia")
