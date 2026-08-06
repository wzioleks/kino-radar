# kino-radar

Cross-references your public [Letterboxd](https://letterboxd.com) watchlist with what's
actually playing in Gdańsk cinemas and renders a static calendar page, rebuilt daily on
GitHub Actions — no server, nothing to host.

Multiplexes drown you in noise and arthouse programmes fly under the radar: a film from
your watchlist plays three evenings in a small studio cinema and is gone before you hear
about it. This page answers one question — *is anything I want to see playing right now?*

**Live:** [wzioleks.github.io/kino-radar](https://wzioleks.github.io/kino-radar/)

## How it works

1. Scrapes showtimes for nine cinemas from five sources (see table below), deduplicating
   screenings that appear in more than one source. A source going down logs a warning and
   the rest carry on.
2. Fetches your public Letterboxd watchlist.
3. Matches screenings against the watchlist. Cinemas list Polish release titles, so
   matching cascades from cheap to expensive: exact title → original title (most sources
   provide one) → TMDb lookup for the rest, cached in SQLite so repeated titles are free.
4. Renders `public/index.html` — a calendar of matches plus a poster sidebar; clicking a
   film opens its showtimes with ticket links.

### Sources

| Cinema | Source | Coverage |
|---|---|---|
| Helios Forum, Helios Metropolia | `api.helios.pl` (JSON) | 14 days |
| Multikino Gdańsk | `multikino.pl` API (JSON) | 14 days |
| Kino Żak | `klubzak.com.pl` (HTML) | ~a month |
| Kino na 100czni | `100cznia.pl` (HTML) | biweekly open-air cycle |
| Spektrum, Kameralne, Cinema1, Szekspirowski | `live.coigdzie.pl` (HTML) | ~7 days |

Żak and 100cznia get dedicated scrapers because aggregators fail them: Żak reaches
coigdzie a week late (it publishes on Wednesdays), and 100cznia — a free open-air cinema
on the old shipyard grounds — sells no tickets, so no booking-driven aggregator ever
lists it.

## Requirements

- Python 3.11+
- A **public** Letterboxd watchlist
- A free [TMDb API key](https://www.themoviedb.org/settings/api) (v3 auth) — optional;
  without it, films the sources only know by Polish title won't match

## Setup

```bash
python -m venv .venv
. .venv/Scripts/activate      # Linux/macOS: source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Fill in `.env`:

| Variable | Purpose |
|---|---|
| `LETTERBOXD_USER` | your login from `letterboxd.com/<user>/watchlist/` |
| `TMDB_API_KEY` | TMDb v3 key (optional, see above) |

Then run:

```bash
python -m kino_radar.main
```

This writes `public/index.html` (open it in a browser) and a `kina.sqlite` cache. An
empty calendar means nothing from your watchlist is playing; a private or empty
watchlist fails loudly instead.

## Deploying to GitHub Pages

The [workflow](.github/workflows/update.yml) scrapes and republishes the page once a day
(`0 6 * * *`); the rendered site ships as an artifact, so `public/` never lands in the
repo.

1. Fork the repo — keep it **public**: Actions minutes are free and unlimited there,
   metered on private repos.
2. *Settings → Pages → Build and deployment* → Source: **GitHub Actions**.
3. Add `LETTERBOXD_USER` and `TMDB_API_KEY` under *Settings → Secrets and variables →
   Actions*.
4. Run the workflow once manually (*Actions → Aktualizacja kino-radar → Run workflow*).

There is no `push` trigger — commits alone don't rebuild the page.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Everything runs offline: parsers against HTML/JSON fixtures, the matcher against a mocked
TMDb resolver. A cinema redesigning its site breaks data, not the build.

## Limitations

- Every source is an undocumented endpoint or scraped page — a redesign on their side
  breaks that source until the parser is updated (the run itself survives).
- coigdzie addresses days by weekday name, capping its cinemas at ~7 days ahead.
- 100cznia announces some screenings as "after sunset" with no time; those are skipped
  until a time is published rather than guessed.
- TMDb's free tier is for non-commercial use — monetizing a deployment needs their
  commercial licence.

## Disclaimer

Unofficial; not affiliated with any of the cinemas, Letterboxd, or TMDb. Reads the same
public schedule data the cinemas' own websites serve, once a day. Intended for personal
use.
