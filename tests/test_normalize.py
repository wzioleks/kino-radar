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


def test_normalize_strips_edition_suffix():
    """Multikino dokleja wydanie do tytułu, Helios nie — muszą się zejść."""
    assert (normalize_title("Backrooms. Bez wyjścia - wersja rozszerzona")
            == normalize_title("Backrooms. Bez wyjścia"))


def test_normalize_strips_format_suffix():
    assert normalize_title("Vaiana 3D") == normalize_title("Vaiana")
    assert normalize_title("Odyseja IMAX") == normalize_title("Odyseja")
    assert normalize_title("Pucio dubbing") == normalize_title("Pucio")


def test_normalize_keeps_title_that_is_only_edition_words():
    """Ucięcie całego tytułu byłoby gorsze niż jego zostawienie."""
    assert normalize_title("Premiera") == "premiera"
