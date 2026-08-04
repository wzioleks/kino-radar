"""Testy scrapera Kina na 100czni — kafelki Elementora, miesiąc w mianowniku."""
import datetime as dt

from kino_radar.sources.stocznia import _parse_program

TODAY = dt.date(2026, 8, 4)


def tile(title: str, when: str, extra: str = "") -> str:
    return f"""<div class="elementor-element e-loop-item e-loop-item-1">
      <a href="https://100cznia.pl/wydarzenia/x/">{title}</a>
      <div><p class="elementor-heading-title">{when.split(' ', 1)[0]}</p></div>
      <span class="elementor-icon-list-text">{when.split(' ', 1)[1]}</span>
      <span class="elementor-icon-list-text">{extra}</span>
      <img src="https://100cznia.pl/wp-content/uploads/2026/07/plakat.jpg">
      <a href="https://100cznia.pl/wydarzenia/x/">WIĘCEJ INFORMACJI</a>
    </div>"""


def test_parses_screening_with_time_range():
    out = _parse_program(
        tile("KINO NA 100CZNI #8: NIEDŹWIEDZICA", "11 Sierpień // 2026", "21:00-22:30"),
        TODAY,
    )
    assert len(out) == 1
    s = out[0]
    assert s.title == "Niedźwiedzica"  # kafelki krzyczą kapitalikami
    assert s.date == "2026-08-11" and s.time == "21:00"
    assert s.cinema == "Kino na 100czni" and s.cinema_type == "studyjne"
    assert s.poster_path.endswith("plakat.jpg")
    assert s.url == "https://100cznia.pl/wydarzenia/x/"


def test_keeps_mixed_case_title_untouched():
    out = _parse_program(
        tile("KINO NA 100CZNI #10: Broken english", "8 Wrzesień // 2026", "21:00-23:00"),
        TODAY,
    )
    assert [s.title for s in out] == ["Broken english"]


def test_title_with_digits_and_colon():
    out = _parse_program(
        tile("KINO NA 100CZNI #9: ORWELL: 2+2 = 5", "25 Sierpień // 2026", "21:00-23:00"),
        TODAY,
    )
    assert [s.title for s in out] == ["Orwell: 2+2 = 5"]


def test_skips_screening_without_time():
    """Godzinę dopisują bliżej terminu — zgadywanie jej byłoby wymyślaniem danych."""
    assert _parse_program(
        tile("KINO NA 100CZNI #10: Broken english", "8 Wrzesień // 2026"), TODAY
    ) == []


def test_skips_unset_time_placeholder():
    assert _parse_program(
        tile("KINO NA 100CZNI #11: Cokolwiek", "8 Wrzesień // 2026", "??:??"), TODAY
    ) == []


def test_ignores_events_that_are_not_screenings():
    """Urodziny mają pokazy filmowe, ale bez repertuaru — nie są seansem."""
    html = (
        tile("9. urodziny 100czni", "8 Sierpień // 2026", "12:00-2:00")
        + tile("TARG MIEJSKI #8: HOLIDAYS ON", "2 Sierpień // 2026", "12:00-19:00")
        + tile("JOGA NA 100CZNI W SEZONIE LETNIM", "1 Lipiec // 2026", "12:00-13:00")
    )
    assert _parse_program(html, TODAY) == []


def test_invalid_date_is_dropped():
    assert _parse_program(
        tile("KINO NA 100CZNI #7: Nic", "31 Luty // 2026", "21:00-22:30"), TODAY
    ) == []
