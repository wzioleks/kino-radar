"""Testy parserów źródeł na fixture'ach (offline, bez sieci)."""
from kino_radar.letterboxd import _parse_page
from kino_radar.sources.coigdzie import _parse_day
from kino_radar.sources.helios import _parse as helios_parse
from kino_radar.sources.multikino import _parse_films


def test_helios_parse(load_json):
    data = load_json("helios_screenings.json")["data"]
    out = helios_parse(data, "Helios Forum Gdańsk", max_dates=14)
    assert len(out) == 4  # 2 + 1 (16.06) + 1 (17.06)
    s = out[0]
    assert s.title == "Dzień objawienia"
    assert s.original_title == "Disclosure Day"
    assert s.cinema_type == "multiplex"
    assert s.date == "2026-06-16" and s.time == "10:30"
    assert s.url.startswith("https://bilety.helios.pl/screen/")


def test_helios_respects_max_dates(load_json):
    data = load_json("helios_screenings.json")["data"]
    out = helios_parse(data, "Helios Forum Gdańsk", max_dates=1)
    assert {s.date for s in out} == {"2026-06-16"}


def test_multikino_parse(load_json):
    films = load_json("multikino_films.json")["result"]
    out = _parse_films(films)
    assert len(out) == 2  # drugi film nie ma sesji
    s = out[0]
    assert s.title == "Dzień objawienia"
    assert s.original_title == "Disclosure Day"
    assert s.date == "2026-06-16" and s.time == "11:00"
    assert s.url.startswith("https://www.multikino.pl/rezerwacja-biletow/")


def test_coigdzie_filters_studyjne_and_aliases(load_text):
    out = _parse_day(load_text("coigdzie_day.html"))
    cinemas = {s.cinema for s in out}
    # Cinema1 i Klub Kot(->Kino Spektrum) zostają; Multikino odpada
    assert cinemas == {"Cinema1", "Kino Spektrum"}
    assert all(s.cinema_type == "studyjne" for s in out)
    cinema1 = [s for s in out if s.cinema == "Cinema1"]
    assert {s.time for s in cinema1} == {"13:15", "19:45"}
    assert all(s.url.startswith("https://bilety.cinemaone.pl/") for s in cinema1)


def test_coigdzie_klub_kot_alias(load_text):
    out = _parse_day(load_text("coigdzie_day.html"))
    spektrum = [s for s in out if s.cinema == "Kino Spektrum"]
    assert len(spektrum) == 1
    assert spektrum[0].time == "20:00"


def test_letterboxd_parse(load_text):
    items = _parse_page(load_text("letterboxd_watchlist.html"))
    assert len(items) == 3
    assert items[0].slug == "shaun-of-the-dead"
    assert items[0].title == "Shaun of the Dead"
    assert items[0].year == 2004
    # film bez roku w nawiasie
    assert items[2].title == "Untitled Project"
    assert items[2].year is None


def test_letterboxd_empty_page():
    assert _parse_page("<html><body>brak</body></html>") == []
