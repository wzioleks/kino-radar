"""Testy scrapera Kina Żak — godziny są tekstem po polsku, więc parser dat
i heurystyka tytułu oryginalnego to najbardziej kruche miejsca w projekcie."""
import datetime as dt

from kino_radar.sources.zak import (
    _original_title,
    _parse_event,
    _parse_times,
)

TODAY = dt.date(2026, 8, 4)


def times(text: str):
    return _parse_times(text, TODAY)


def test_range_without_spaces():
    assert times("7-9 sierpnia o 20:15") == [
        ("2026-08-07", "20:15"),
        ("2026-08-08", "20:15"),
        ("2026-08-09", "20:15"),
    ]


def test_range_with_en_dash_and_spaces():
    assert times("14 – 16 sierpnia o 18:00") == [
        ("2026-08-14", "18:00"),
        ("2026-08-15", "18:00"),
        ("2026-08-16", "18:00"),
    ]


def test_range_across_months_names_on_both_sides():
    assert times("31 lipca - 2 sierpnia o 18:00") == [
        ("2026-07-31", "18:00"),
        ("2026-08-01", "18:00"),
        ("2026-08-02", "18:00"),
    ]


def test_single_day():
    assert times("3 sierpnia o 20:00") == [("2026-08-03", "20:00")]


def test_single_day_ignores_trailing_note():
    assert times("4 sierpnia o 20:00 seans z prelekcją!") == [("2026-08-04", "20:00")]


def test_multiple_lines():
    assert times("7-9 sierpnia o 20:15\n10-13 sierpnia o 18:00") == [
        ("2026-08-07", "20:15"),
        ("2026-08-08", "20:15"),
        ("2026-08-09", "20:15"),
        ("2026-08-10", "18:00"),
        ("2026-08-11", "18:00"),
        ("2026-08-12", "18:00"),
        ("2026-08-13", "18:00"),
    ]


def test_range_across_new_year_does_not_go_backwards():
    """Bez dopisania roku '2 stycznia' wypadłoby 12 miesięcy w przeszłość."""
    assert _parse_times("31 grudnia – 2 stycznia o 18:00", dt.date(2026, 12, 30)) == [
        ("2026-12-31", "18:00"),
        ("2027-01-01", "18:00"),
        ("2027-01-02", "18:00"),
    ]


def test_price_list_yields_no_dates():
    assert times("20 zł - normalny\n14 zł - Tanie Poniedziałki") == []


def test_original_title_taken_when_present():
    assert _original_title(
        "Koukaku Kidoutai – Mamoru Oshii – animacja – "
        "Japonia, Wielka Brytania – 1995 – 82 min."
    ) == "Koukaku Kidoutai"


def test_original_title_skipped_when_line_starts_with_director():
    """Film polski nie ma tytułu oryginalnego — nazwisko reżysera zepsułoby match."""
    assert _original_title("Michael Haneke – Austria – 1997 – 108 min.") is None
    assert _original_title("Marta Stróżycka – Polska – 2026 – 45 min. – b.o.") is None


def test_original_title_keeps_internal_hyphen():
    assert _original_title(
        "Spider-Man: Brand New Day – Destin Daniel Cretton – USA – 2026 – 120 min."
    ) == "Spider-Man: Brand New Day"


def _event(h1: str, h2: str, body: str, head: str = "Seanse") -> str:
    return f"""<html><body>
      <h1>{h1}</h1>
      <h2>{h2}</h2>
      <h5 class="date-info">22 Sie 16:00</h5>
      <div class="info"><h3>{head}</h3>{body}</div>
      <div class="info"><h3>Bilety</h3>20 zł - normalny<br>14 zł - Poniedziałki</div>
      <img src="/Klub%20Zak/kino/ghost.webp">
    </body></html>"""


def test_parse_event_builds_screenings():
    html = _event(
        "Ghost in the Shell",
        "Koukaku Kidoutai – Mamoru Oshii – Japonia – 1995 – 82 min.",
        "7-9 sierpnia o 20:15<br>10-13 sierpnia o 18:00",
    )
    out = _parse_event(html, "https://klubzak.com.pl/x", TODAY)
    assert len(out) == 7
    assert out[0].title == "Ghost in the Shell"
    assert out[0].original_title == "Koukaku Kidoutai"
    assert out[0].cinema == "Kino Żak" and out[0].cinema_type == "studyjne"
    assert out[0].poster_path == "https://klubzak.com.pl/Klub%20Zak/kino/ghost.webp"


def test_parse_event_strips_cycle_prefix_from_title():
    html = _event("DKF ŻAK: Funny Games", "Michael Haneke – Austria – 1997 – 108 min.",
                  "22 sierpnia o 16:00", head="Seans z dyskusją")
    out = _parse_event(html, "https://klubzak.com.pl/x", TODAY)
    assert [s.title for s in out] == ["Funny Games"]
    assert out[0].original_title is None


def test_parse_event_falls_back_to_date_tile():
    """Pokazy jednorazowe nie mają bloku z godzinami — data jest w kafelku."""
    html = _event("Seans przyjazny sensorycznie: Pucio kocha zwierzaki",
                  "Marta Stróżycka – Polska – 2026 – 45 min.", "", head="")
    out = _parse_event(html, "https://klubzak.com.pl/x", TODAY)
    assert len(out) == 1
    assert out[0].title == "Pucio kocha zwierzaki"
    assert out[0].date == "2026-08-22" and out[0].time == "16:00"
