# 🎬 kino-radar

Pokazuje **tylko te filmy z Twojej publicznej watchlisty Letterboxd, które aktualnie grają w kinach w Gdańsku** — jako statyczny mini-kalendarz HTML.

Zbiera repertuary multipleksów (Helios Forum, Helios Metropolia, Multikino) i kin
studyjnych (Żak, Kameralne, Helikon, Spektrum, Muzeum, IKM, Cinema1), krzyżuje je
z watchlistą i renderuje kalendarz [FullCalendar](https://fullcalendar.io/), gdzie
klik w seans prowadzi do strony zakupu biletu.

## Jak to działa

```
źródła ─┬─ Helios   (JSON: api.helios.pl/api/v1/cinemas/{id}/screenings)
        ├─ Multikino(JSON: multikino.pl/api/microservice/showings/...)
        └─ coigdzie (HTML: live.coigdzie.pl — kina studyjne)
            │
            ▼
   watchlista Letterboxd (HTML, paginowana)
            │
            ▼
   matcher ── kaskada: imdb_id → tytuł+rok → TMDb (PL→oryginał), cache w SQLite
            │
            ▼
   public/index.html  (FullCalendar, kolor wg typu kina)
```

**Klucz dopasowania to `tmdb_id`** — żadne źródło nie podaje `imdb_id`, a kina grają
polskie tytuły. TMDb rozwiązuje polski tytuł → film kanoniczny, więc „Diabeł ubiera
się u Prady 2" trafia na „The Devil Wears Prada 2" z watchlisty. Wyniki TMDb są
cache'owane w SQLite, żeby nie powtarzać zapytań.

## Setup

Wymaga Pythona 3.11+.

```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -e .            # albo: pip install -r requirements.txt
cp .env.example .env        # i uzupełnij (patrz niżej)
```

### `.env`

| zmienna          | opis                                                                 |
|------------------|----------------------------------------------------------------------|
| `LETTERBOXD_USER`| login z `letterboxd.com/{USER}/watchlist/` (watchlista **publiczna**) |
| `TMDB_API_KEY`   | klucz TMDb **v3 auth** — [themoviedb.org → Settings → API](https://www.themoviedb.org/settings/api) |

Bez `TMDB_API_KEY` pipeline działa, ale matcher pomija krok TMDb (tylko tytuł+rok),
więc polskie tłumaczenia tytułów nie zostaną dopasowane.

## Uruchomienie

```bash
python -m kino_radar.main      # albo: kino-radar  (po pip install -e .)
```

Tworzy `public/index.html` i cache `kina.sqlite`. Otwórz plik w przeglądarce.

Jeśli kalendarz jest pusty — to znaczy, że nic z Twojej watchlisty akurat nie gra
(albo watchlista jest pusta/prywatna — wtedy zobaczysz czytelny błąd).

## Testy

```bash
pip install -e ".[dev]"
pytest
```

Testy parserów chodzą na fixture'ach HTML/JSON (offline), matcher na zamockowanym
resolverze TMDb — żadne nie biją w sieć.

## Deploy: GitHub Pages + GitHub Actions (cron 24h)

Workflow [`.github/workflows/update.yml`](.github/workflows/update.yml) raz na dobę:
scrapuje → renderuje `public/` → publikuje na GitHub Pages (`public/` idzie jako
artefakt, więc nie musi być w repo).

1. **Włącz Pages**: Settings → Pages → *Build and deployment* → Source: **GitHub Actions**.
2. **Sekrety repo** (Settings → Secrets and variables → Actions):
   - `LETTERBOXD_USER`
   - `TMDB_API_KEY`
3. Odpal workflow: Actions → *Aktualizacja kino-radar* → **Run workflow**.

Cron ustawiony na `0 6 * * *` (08:00 czasu PL latem). Strona ląduje pod
`https://{user}.github.io/{repo}/`.

## Struktura

```
src/kino_radar/
├── models.py        # Screening, WatchlistItem
├── config.py        # .env + ID kin + aliasy + whitelist studyjnych
├── http.py          # async klient httpx + rate limiting
├── normalize.py     # normalizacja tytułów (bez diakrytyków/interpunkcji)
├── sources/
│   ├── helios.py    # Helios Forum + Metropolia (JSON)
│   ├── multikino.py # Multikino Gdańsk (JSON + auth cookie)
│   └── coigdzie.py  # kina studyjne (HTML)
├── letterboxd.py    # watchlista (HTML, paginacja)
├── matcher.py       # kaskada dopasowania (klucz: tmdb_id)
├── tmdb.py          # resolver TMDb + cache
├── db.py            # SQLite (screenings, watchlist, tmdb_cache)
├── render.py        # public/index.html (FullCalendar)
└── main.py          # orkiestracja
```

## Uwagi

- **Cinema City** nie istnieje już w Gdańsku — pominięte.
- coigdzie adresuje dni nazwą dnia tygodnia, więc kina studyjne pokrywają ~7 dni;
  multipleksy (JSON) sięgają dalej.
- „Klub Kot" to alias „Kina Spektrum" — scalane przed zapisem, by seans nie wszedł
  dwa razy.
- Padnięcie jednego źródła loguje ostrzeżenie i nie wywala reszty pipeline'u.
