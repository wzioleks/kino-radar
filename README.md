# 🎬 kino-radar

Pokazuje **tylko te filmy z Twojej publicznej watchlisty Letterboxd, które aktualnie
grają w kinach w Gdańsku** — jako statyczny kalendarz HTML, odświeżany raz na dobę.

Zbiera repertuary dziewięciu kin (multipleksy, studyjne i plenerowe), krzyżuje je
z watchlistą i renderuje stronę, gdzie kalendarz pokazuje jeden kafelek na film
w danym dniu, a klik otwiera listę seansów z linkiem do biletu.

Wymaga Pythona 3.11+ i publicznej watchlisty na Letterboxd.

## Skąd biorą się dane

| Kino | Źródło | Typ | Pokrycie |
|---|---|---|---|
| Helios Forum, Helios Metropolia | `api.helios.pl` (JSON) | multipleks | 14 dni |
| Multikino Gdańsk | `multikino.pl` microservice (JSON) | multipleks | 14 dni |
| Kino Żak | `klubzak.com.pl` (HTML) | studyjne | ~miesiąc |
| Kino na 100czni | `100cznia.pl` (HTML) | plenerowe | cykl co 2 tygodnie |
| Spektrum, Kameralne, Cinema1, na Szekspirowskim | `live.coigdzie.pl` (HTML) | studyjne + plenerowe | ~7 dni |

Żak i 100cznia mają własne scrapery, bo agregatory ich nie obsługują: Żak trafia
na coigdzie z tygodniowym opóźnieniem (aktualizuje repertuar w środy), a na 100cznię
wstęp jest wolny, więc nie ma jej w żadnym systemie biletowym. coigdzie zostaje dla
Żaka zapasem — duplikaty ucina wspólna deduplikacja.

## Jak to działa

```
źródła ─┬─ helios     (JSON)  ┐
        ├─ multikino  (JSON)  │
        ├─ zak        (HTML)  ├─ deduplikacja: (kino, tytuł, dzień, godzina)
        ├─ stocznia   (HTML)  │  padnięte źródło = warning, nie crash
        └─ coigdzie   (HTML)  ┘
                                      │
                                      ▼
                    watchlista Letterboxd (HTML, paginowana)
                                      │
                                      ▼
      matcher ── kaskada: imdb_id → tytuł+rok → TMDb, cache w SQLite
                                      │
                                      ▼
                   public/index.html  (kalendarz + lista filmów)
```

### Dopasowanie

**Kluczem jest `tmdb_id`** — żadne źródło nie podaje `imdb_id`, a kina grają polskie
tytuły, więc „Diabeł ubiera się u Prady 2" trzeba połączyć z „The Devil Wears Prada 2"
z watchlisty. Wyniki TMDb siedzą w cache SQLite, żeby nie powtarzać zapytań.

Trzy rzeczy zmniejszają zależność od TMDb:

- **Helios i Multikino podają tytuł oryginalny** we własnym API, a Żak na stronie
  wydarzenia — dla tych źródeł tłumaczenie nie jest potrzebne.
- Multikino zwraca `originalTitle` puste, więc brakujące tytuły uzupełnia mapa
  polski → oryginalny zebrana z pozostałych źródeł.
- Kina dokleją do tytułu wydanie („Backrooms. Bez wyjścia - wersja rozszerzona"),
  co rozjeżdżało dopasowanie — normalizacja ucina `wersja *`, `2D`, `3D`, `IMAX`,
  `dubbing`, `napisy` przed porównaniem.

## Setup

```bash
python -m venv .venv
. .venv/Scripts/activate     # Linux/macOS: source .venv/bin/activate
pip install -e .
cp .env.example .env         # i uzupełnij (patrz niżej)
```

### `.env`

| zmienna | opis |
|---|---|
| `LETTERBOXD_USER` | login z `letterboxd.com/{USER}/watchlist/` — watchlista musi być **publiczna** |
| `TMDB_API_KEY` | klucz TMDb **v3 auth** — [themoviedb.org → Settings → API](https://www.themoviedb.org/settings/api) |

Bez `TMDB_API_KEY` pipeline działa, ale matcher pomija krok TMDb i opiera się tylko
na tytułach ze źródeł — filmy znane wyłącznie z polskiego tytułu nie zostaną
dopasowane, a plakaty pojawią się jedynie tam, gdzie kino podaje własny.

## Uruchomienie

```bash
python -m kino_radar.main
```

Albo `kino-radar` po `pip install -e .`. Tworzy `public/index.html` oraz cache
`kina.sqlite`; stronę otwiera się z pliku.

Pusty kalendarz znaczy, że nic z watchlisty akurat nie gra. Watchlista pusta lub
prywatna daje czytelny błąd, nie ciszę.

## Testy

```bash
pip install -e ".[dev]"
pytest
```

44 testy, wszystkie offline: parsery chodzą na fixture'ach HTML/JSON i wbudowanych
fragmentach, matcher na zamockowanym resolverze TMDb. Żaden nie bije w sieć, więc
zmiana na stronie kina nie wywala buildu — psuje dopiero dane.

## Deploy: GitHub Pages + Actions

Workflow [`.github/workflows/update.yml`](.github/workflows/update.yml) raz na dobę
scrapuje, renderuje `public/` i publikuje na Pages. `public/` idzie jako artefakt,
więc nie musi być w repo.

1. **Pages**: Settings → Pages → *Build and deployment* → Source: **GitHub Actions**.
2. **Sekrety** (Settings → Secrets and variables → Actions): `LETTERBOXD_USER`, `TMDB_API_KEY`.
3. Pierwsze odpalenie: Actions → *Aktualizacja kino-radar* → **Run workflow**,
   albo `gh workflow run update.yml`.

Cron to `0 6 * * *` (08:00 czasu polskiego latem). Strona ląduje pod
`https://{user}.github.io/{repo}/`. Workflow nie ma triggera `push` — sam commit
nie przebuduje strony.

## Struktura

```
src/kino_radar/
├── main.py          # orkiestracja + deduplikacja źródeł
├── config.py        # .env, ID kin, aliasy, whitelist studyjnych
├── models.py        # Screening, WatchlistItem
├── http.py          # async klient httpx + rate limiting
├── normalize.py     # normalizacja tytułów (diakrytyki, interpunkcja, wydania)
├── sources/
│   ├── helios.py    # Helios Forum + Metropolia (JSON)
│   ├── multikino.py # Multikino Gdańsk (JSON + cookie sesji)
│   ├── zak.py       # Kino Żak (HTML, godziny prozą po polsku)
│   ├── stocznia.py  # Kino na 100czni (HTML, kafelki Elementora)
│   └── coigdzie.py  # pozostałe kina studyjne (HTML)
├── letterboxd.py    # watchlista (HTML, paginacja)
├── matcher.py       # kaskada dopasowania (klucz: tmdb_id)
├── tmdb.py          # resolver TMDb + cache
├── db.py            # SQLite (screenings, watchlist, tmdb_cache) + migracje
└── render.py        # public/index.html
tests/               # 44 testy offline, fixture'y w tests/fixtures/
```

## Uwagi

- **Cinema City** i **Helios w Alfa Centrum** nie istnieją już w Gdańsku. Helikon,
  IKM i Muzeum zostały w whitelist, ale nie pojawiają się w żadnym źródle —
  prawdopodobnie nie prowadzą regularnych seansów.
- coigdzie adresuje dni nazwą dnia tygodnia, więc sięga ~7 dni; własne scrapery
  i API multipleksów idą dalej.
- „Klub Kot" to alias „Kina Spektrum" — scalane przed zapisem, by seans nie wszedł
  dwa razy.
- Plakaty przychodzą albo jako ścieżka TMDb, albo jako gotowy adres ze strony kina;
  render obsługuje oba formaty.
- 100cznia ogłasza część seansów bez godziny („po zachodzie słońca"). Takie wpisy
  są pomijane z logiem, zamiast zgadywać godzinę — pojawią się, gdy kino ją poda.
- TMDb jest darmowe do użytku niekomercyjnego; przy monetyzacji wymaga płatnej
  licencji, a wszystkie tytuły oryginalne i część plakatów da się dziś wziąć
  wprost ze źródeł kin.
