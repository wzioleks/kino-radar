"""Generuje public/index.html z kalendarzem FullCalendar (CDN, bez build stepu).

Layout: kalendarz (lewa kolumna) + lista wszystkich zmatchowanych filmów z posterami
(prawy sidebar). W obu klik otwiera modal z seansami:
  - kafelek w kalendarzu -> seanse danego filmu w danym dniu,
  - film w sidebarze     -> wszystkie seanse filmu, z podziałem na dni.
Wygląd: „nocne repertuarowe" — ciepła prawie-czerń, bursztyn marquee jako kolor
przewodni, typografia plakatowa (Big Shoulders Display) na masthead.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import logging
from collections import defaultdict
from pathlib import Path
from string import Template

from .models import Screening

log = logging.getLogger(__name__)

DEFAULT_OUT = Path("public/index.html")

# Kolory wg typu kina — znaczenie, nie dekoracja:
# studyjne = bursztyn marquee (dusza projektu), multipleks = chłodny błękit.
COLORS = {
    "multiplex": "#38bdf8",  # błękit
    "studyjne": "#f5a623",   # bursztyn
}

_TEMPLATE = Template("""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kino-radar — Twoja watchlista w kinach Gdańska</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@500;700;800&family=Inter:wght@400;500;600&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.15/index.global.min.js"></script>
<style>
  :root {
    --bg:        #0c0a09;
    --surface:   #1a1614;
    --surface-2: #221d1a;
    --line:      #322a26;
    --ink:       #f5f0e8;
    --muted:     #a8a098;
    --amber:     #f5a623;
    --amber-dim: #c98318;
    --sky:       #38bdf8;

    --fc-border-color: var(--line);
    --fc-page-bg-color: transparent;
    --fc-neutral-bg-color: var(--surface-2);
    --fc-today-bg-color: rgba(245,166,35,.08);
    --fc-list-event-hover-bg-color: var(--surface-2);
  }
  * { box-sizing: border-box; }
  body {
    font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
    margin: 0; padding: clamp(1.25rem, 4vw, 3rem) clamp(1rem, 4vw, 2rem) 4rem;
    background: var(--bg); color: var(--ink);
    -webkit-font-smoothing: antialiased;
    background-image:
      radial-gradient(60rem 30rem at 50% -12rem, rgba(245,166,35,.10), transparent 70%);
  }
  .wrap { max-width: 1180px; margin: 0 auto; }

  /* ---- Masthead: markiza kina ---- */
  header { margin-bottom: clamp(1.5rem, 4vw, 2.5rem); }
  .eyebrow {
    font-family: 'Space Mono', monospace; font-size: .72rem; letter-spacing: .32em;
    text-transform: uppercase; color: var(--amber); margin: 0 0 .5rem;
  }
  h1 {
    font-family: 'Big Shoulders Display', sans-serif; font-weight: 800;
    font-size: clamp(3rem, 13vw, 6.5rem); line-height: .85; letter-spacing: .01em;
    text-transform: uppercase; margin: 0; color: var(--ink);
    text-shadow: 0 0 36px rgba(245,166,35,.28);
  }
  h1 .dash { color: var(--amber); }
  .tagline { color: var(--muted); font-size: 1rem; margin: .9rem 0 0; max-width: 48ch; }
  .tagline strong { color: var(--ink); font-weight: 600; }

  /* ---- Pasek danych: jak stopka biletu ---- */
  .stub {
    display: flex; flex-wrap: wrap; align-items: center; gap: .6rem 1.4rem;
    margin-top: 1.4rem; padding-top: 1.1rem; border-top: 1px solid var(--line);
    font-family: 'Space Mono', monospace; font-size: .8rem; color: var(--muted);
  }
  .stub .count { color: var(--ink); }
  .stub .count b { color: var(--amber); font-size: 1.1rem; }
  .legend { display: flex; gap: 1.1rem; margin-left: auto; }
  .legend span { display: inline-flex; align-items: center; gap: .45rem; }
  .dot { width: .65rem; height: .65rem; border-radius: 2px; display: inline-block; }

  /* ---- Layout: kalendarz + sidebar ---- */
  .layout {
    display: grid; grid-template-columns: minmax(0, 1fr) 300px;
    gap: 1.25rem; align-items: start;
  }

  /* ---- Kalendarz ---- */
  #calendar {
    background: var(--surface); padding: clamp(.75rem, 2vw, 1.4rem);
    border: 1px solid var(--line); border-radius: 14px;
    box-shadow: 0 24px 60px -32px rgba(0,0,0,.8);
  }
  .fc { --fc-small-font-size: .8rem; }
  .fc .fc-toolbar-title {
    font-family: 'Big Shoulders Display', sans-serif; font-weight: 700;
    font-size: 1.7rem; text-transform: uppercase; letter-spacing: .02em;
  }
  .fc .fc-col-header-cell-cushion,
  .fc .fc-daygrid-day-number { color: var(--muted); text-decoration: none; }
  .fc .fc-col-header-cell-cushion {
    font-family: 'Space Mono', monospace; font-size: .7rem;
    letter-spacing: .12em; text-transform: uppercase;
  }
  .fc-theme-standard .fc-scrollgrid { border-radius: 10px; overflow: hidden; }
  .fc .fc-day-today .fc-daygrid-day-number { color: var(--amber); font-weight: 700; }

  /* Przyciski w bursztynowym akcencie */
  .fc .fc-button-primary {
    background: var(--surface-2); border-color: var(--line); color: var(--ink);
    text-transform: lowercase; font-weight: 500; box-shadow: none;
  }
  .fc .fc-button-primary:not(:disabled):hover { background: var(--line); border-color: var(--line); }
  .fc .fc-button-primary:not(:disabled).fc-button-active,
  .fc .fc-button-primary:not(:disabled):active {
    background: var(--amber); border-color: var(--amber); color: #1a1207;
  }
  .fc .fc-button:focus-visible { outline: 2px solid var(--amber); outline-offset: 2px; box-shadow: none; }

  /* ---- Kafelek filmu w kalendarzu (czysty: tytuł + licznik, pasek = typ kina) ---- */
  .fc-event, a.fc-event { cursor: pointer; border: none; background: transparent; }
  .fc-daygrid-event { padding: 0; margin: 2px 2px 0; white-space: normal; }
  .fc-daygrid-event:focus-visible { outline: 2px solid var(--amber); outline-offset: 1px; }
  .film {
    display: flex; flex-direction: column; gap: 1px;
    background: var(--surface-2); border: 1px solid var(--line);
    border-left: 3px solid var(--chip, var(--muted));
    border-radius: 6px; padding: .28rem .45rem; transition: border-color .12s, transform .12s;
  }
  .fc-daygrid-event:hover .film { border-color: var(--amber-dim); transform: translateY(-1px); }
  .film__title {
    color: var(--ink); font-weight: 600; font-size: .8rem; line-height: 1.15;
    overflow: hidden; text-overflow: ellipsis; display: -webkit-box;
    -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  }
  .film__count {
    font-family: 'Space Mono', monospace; font-size: .65rem; color: var(--muted);
    letter-spacing: .02em;
  }
  .fc .fc-list-event-title a { color: var(--ink); font-weight: 600; }
  .fc .fc-list-event:hover td { background: var(--surface-2); }
  .fc-list-event-graphic .fc-list-event-dot { display: none; }

  /* ---- Sidebar: wszystkie filmy ---- */
  .sidebar {
    position: sticky; top: 1rem; background: var(--surface);
    border: 1px solid var(--line); border-radius: 14px; padding: .9rem;
    max-height: calc(100vh - 2rem); overflow: auto;
    box-shadow: 0 24px 60px -32px rgba(0,0,0,.8);
  }
  .sidebar__head {
    font-family: 'Space Mono', monospace; font-size: .72rem; letter-spacing: .18em;
    text-transform: uppercase; color: var(--amber); margin: .2rem .3rem 1rem;
  }
  .film-row {
    display: flex; gap: .65rem; align-items: stretch; width: 100%; text-align: left;
    background: transparent; border: none; border-left: 3px solid var(--chip, var(--muted));
    border-radius: 8px; padding: .4rem .5rem; margin-bottom: .25rem; cursor: pointer;
    color: inherit; font: inherit; transition: background .12s;
  }
  .film-row:hover { background: var(--surface-2); }
  .film-row:focus-visible { outline: 2px solid var(--amber); outline-offset: 1px; }
  .film-row__poster {
    width: 38px; flex: 0 0 38px; aspect-ratio: 2/3; object-fit: cover;
    border-radius: 4px; background: var(--line);
  }
  .film-row__poster--ph { display: grid; place-items: center; color: var(--muted); }
  .film-row__meta { min-width: 0; display: flex; flex-direction: column; justify-content: center; gap: 2px; }
  .film-row__title {
    color: var(--ink); font-weight: 600; font-size: .85rem; line-height: 1.2;
    overflow: hidden; text-overflow: ellipsis; display: -webkit-box;
    -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  }
  .film-row__count {
    font-family: 'Space Mono', monospace; font-size: .68rem; color: var(--muted);
  }

  /* ---- Modal: seanse filmu ---- */
  .modal[hidden] { display: none; }
  .modal { position: fixed; inset: 0; z-index: 50; display: grid; place-items: center; padding: 1rem; }
  .modal__backdrop { position: absolute; inset: 0; background: rgba(8,6,5,.72); backdrop-filter: blur(3px); }
  .modal__card {
    position: relative; width: min(34rem, 100%); max-height: 86vh; overflow: auto;
    background: var(--surface); border: 1px solid var(--line); border-radius: 16px;
    box-shadow: 0 40px 80px -30px rgba(0,0,0,.85); animation: pop .16s ease-out;
  }
  @keyframes pop { from { opacity: 0; transform: translateY(8px) scale(.99); } }
  .modal__close {
    position: absolute; top: .7rem; right: .7rem; z-index: 2;
    width: 2rem; height: 2rem; border-radius: 50%; border: 1px solid var(--line);
    background: var(--surface-2); color: var(--ink); font-size: 1.1rem; cursor: pointer; line-height: 1;
  }
  .modal__close:hover { background: var(--line); }
  .modal__hero { display: flex; gap: 1rem; padding: 1.3rem; border-bottom: 1px solid var(--line); }
  .modal__poster {
    width: 84px; flex: 0 0 84px; aspect-ratio: 2/3; object-fit: cover;
    border-radius: 8px; background: var(--line);
  }
  .modal__poster--ph { display: grid; place-items: center; color: var(--muted); font-size: 1.6rem; }
  .modal__title {
    font-family: 'Big Shoulders Display', sans-serif; font-weight: 700;
    text-transform: uppercase; font-size: 1.7rem; line-height: .95; margin: .1rem 0 .4rem; color: var(--ink);
  }
  .modal__sub {
    font-family: 'Space Mono', monospace; font-size: .75rem; color: var(--amber);
    letter-spacing: .1em; text-transform: uppercase;
  }
  .modal__list { list-style: none; margin: 0; padding: .6rem; }
  .day-head {
    font-family: 'Space Mono', monospace; font-size: .7rem; letter-spacing: .12em;
    text-transform: uppercase; color: var(--muted); padding: .9rem .65rem .3rem;
    border-top: 1px solid var(--line); margin-top: .3rem;
  }
  .day-head:first-child { border-top: none; margin-top: 0; }
  .showing {
    display: flex; align-items: center; gap: .8rem; padding: .55rem .65rem;
    border-radius: 9px; color: var(--ink); text-decoration: none;
    border-left: 3px solid var(--chip, var(--muted));
  }
  .showing:hover { background: var(--surface-2); }
  .showing:focus-visible { outline: 2px solid var(--amber); outline-offset: 1px; }
  .showing__time { font-family: 'Space Mono', monospace; font-weight: 700; font-size: 1rem; }
  .showing__cinema { flex: 1; min-width: 0; color: var(--muted); font-size: .9rem;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .showing__go { color: var(--amber-dim); font-size: .8rem; flex: 0 0 auto; }

  /* ---- Empty state ---- */
  .empty { display: none; text-align: center; padding: 3.5rem 1.5rem; color: var(--muted); }
  .empty.show { display: block; }
  .empty h2 {
    font-family: 'Big Shoulders Display', sans-serif; font-weight: 700;
    text-transform: uppercase; color: var(--ink); font-size: 1.8rem; margin: 0 0 .5rem;
  }

  footer {
    margin-top: 2rem; text-align: center;
    font-family: 'Space Mono', monospace; font-size: .72rem; color: var(--muted);
    letter-spacing: .04em;
  }
  footer a { color: var(--amber-dim); }

  @media (max-width: 880px) {
    .layout { grid-template-columns: 1fr; }
    .sidebar { position: static; max-height: none; order: 2; }
  }
  @media (max-width: 560px) {
    .fc .fc-toolbar.fc-header-toolbar { flex-direction: column; gap: .6rem; align-items: stretch; }
    .legend { margin-left: 0; }
  }
  @media (prefers-reduced-motion: reduce) {
    *, .modal__card { animation: none !important; transition: none !important; }
  }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <p class="eyebrow">Repertuar · Gdańsk</p>
    <h1>Kino<span class="dash">–</span>Radar</h1>
    <p class="tagline">Tylko filmy z watchlisty <strong>$user</strong> na Letterboxd,
      które grają teraz w gdańskich kinach. Klik w film → seanse.</p>
    <div class="stub">
      <span class="count"><b>$count</b> seansów na ekranie</span>
      <span>akt. $updated</span>
      <span class="legend">
        <span><span class="dot" style="background:$c_std"></span>studyjne</span>
        <span><span class="dot" style="background:$c_mux"></span>multipleks</span>
      </span>
    </div>
  </header>

  <div class="layout" id="layout">
    <div id="calendar"></div>
    <aside class="sidebar" id="sidebar"></aside>
  </div>

  <div class="empty" id="empty">
    <h2>Cisza na ekranach</h2>
    <p>Nic z Twojej watchlisty akurat nie gra w Gdańsku.<br>
      Zajrzyj później albo dorzuć tytuły na Letterboxd.</p>
  </div>

  <footer>Kino-Radar · scrape co 24h · <a href="https://github.com/wzioleks/kino-radar">źródło</a></footer>
</div>

<div class="modal" id="modal" hidden>
  <div class="modal__backdrop" data-close></div>
  <div class="modal__card" role="dialog" aria-modal="true" aria-labelledby="modal-title">
    <button class="modal__close" data-close aria-label="Zamknij">×</button>
    <div class="modal__body"></div>
  </div>
</div>

<script>
const EVENTS = $events_json;
const FILMS = $films_json;
const COLORS = $colors_json;
const IMG = 'https://image.tmdb.org/t/p/';

const plural = (n) => {
  if (n === 1) return 'seans';
  const t = n % 10, h = n % 100;
  return (t >= 2 && t <= 4 && (h < 10 || h >= 20)) ? 'seanse' : 'seansów';
};
const pluralDay = (n) => n === 1 ? 'dzień' : 'dni';
const fmtDate = (iso) => new Date(iso + 'T00:00:00').toLocaleDateString('pl-PL',
  { weekday: 'long', day: 'numeric', month: 'long' });
const chipColor = (types) => types.length === 1 ? COLORS[types[0]] : COLORS.studyjne;

function posterEl(path, cls, phCls) {
  if (path) {
    const img = document.createElement('img');
    /* TMDb daje ścieżkę ('/abc.jpg'), kina podają gotowy adres */
    img.className = cls;
    img.src = path.startsWith('http') ? path : IMG + 'w185' + path;
    img.alt = ''; img.loading = 'lazy';
    return img;
  }
  const ph = document.createElement('div');
  ph.className = cls + ' ' + phCls; ph.textContent = '🎞';
  return ph;
}

/* Kafelek w kalendarzu — czysty tekst, bez postera (pasek = typ kina) */
function renderChip(arg) {
  const p = arg.event.extendedProps;
  const wrap = document.createElement('div');
  wrap.className = 'film';
  wrap.style.setProperty('--chip', chipColor(p.types));
  const t = document.createElement('span'); t.className = 'film__title'; t.textContent = arg.event.title;
  const c = document.createElement('span'); c.className = 'film__count';
  c.textContent = p.count + ' ' + plural(p.count);
  wrap.append(t, c);
  return { domNodes: [wrap] };
}

/* Sidebar — wszystkie filmy */
function buildSidebar() {
  const aside = document.getElementById('sidebar');
  const head = document.createElement('div');
  head.className = 'sidebar__head';
  head.textContent = 'Wszystkie filmy · ' + FILMS.length;
  aside.appendChild(head);
  for (const film of FILMS) {
    const row = document.createElement('button');
    row.className = 'film-row'; row.type = 'button';
    row.style.setProperty('--chip', chipColor(film.types));
    row.appendChild(posterEl(film.poster, 'film-row__poster', 'film-row__poster--ph'));
    const meta = document.createElement('div'); meta.className = 'film-row__meta';
    const t = document.createElement('span'); t.className = 'film-row__title'; t.textContent = film.title;
    const c = document.createElement('span'); c.className = 'film-row__count';
    c.textContent = film.count + ' ' + plural(film.count) + ' · ' + film.days.length + ' ' + pluralDay(film.days.length);
    meta.append(t, c); row.appendChild(meta);
    row.addEventListener('click', () => openModal(film));
    aside.appendChild(row);
  }
}

/* ---- Modal ---- */
const modal = document.getElementById('modal');
const modalBody = modal.querySelector('.modal__body');
let lastFocus = null;

function showingRow(s) {
  const a = document.createElement('a');
  a.className = 'showing'; a.href = s.url; a.target = '_blank'; a.rel = 'noopener';
  a.style.setProperty('--chip', COLORS[s.type] || 'var(--muted)');
  const time = document.createElement('span'); time.className = 'showing__time'; time.textContent = s.time;
  const cin = document.createElement('span'); cin.className = 'showing__cinema'; cin.textContent = s.cinema;
  const go = document.createElement('span'); go.className = 'showing__go'; go.textContent = 'bilet →';
  a.append(time, cin, go);
  return a;
}

/* payload: { title, poster, count, types, days: [{date, showings:[...]}] } */
function openModal(film) {
  modalBody.innerHTML = '';
  const multi = film.days.length > 1;

  const hero = document.createElement('div'); hero.className = 'modal__hero';
  hero.appendChild(posterEl(film.poster, 'modal__poster', 'modal__poster--ph'));
  const info = document.createElement('div');
  const sub = document.createElement('div'); sub.className = 'modal__sub';
  sub.textContent = multi ? (film.count + ' ' + plural(film.count) + ' · ' + film.days.length + ' ' + pluralDay(film.days.length))
                          : fmtDate(film.days[0].date);
  const h = document.createElement('h2'); h.className = 'modal__title'; h.id = 'modal-title'; h.textContent = film.title;
  info.append(sub, h); hero.appendChild(info);

  const list = document.createElement('div'); list.className = 'modal__list';
  for (const g of film.days) {
    if (multi) {
      const dh = document.createElement('div'); dh.className = 'day-head'; dh.textContent = fmtDate(g.date);
      list.appendChild(dh);
    }
    const ul = document.createElement('ul'); ul.style.listStyle = 'none'; ul.style.margin = '0'; ul.style.padding = '0';
    for (const s of g.showings) { const li = document.createElement('li'); li.appendChild(showingRow(s)); ul.appendChild(li); }
    list.appendChild(ul);
  }
  modalBody.append(hero, list);

  lastFocus = document.activeElement;
  modal.hidden = false;
  modal.querySelector('.modal__close').focus();
}

function closeModal() { modal.hidden = true; if (lastFocus) lastFocus.focus(); }
modal.addEventListener('click', (e) => { if (e.target.dataset.close !== undefined) closeModal(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !modal.hidden) closeModal(); });

document.addEventListener('DOMContentLoaded', () => {
  if (!EVENTS.length) {
    document.getElementById('layout').style.display = 'none';
    document.getElementById('empty').classList.add('show');
    return;
  }
  buildSidebar();
  const cal = new FullCalendar.Calendar(document.getElementById('calendar'), {
    initialView: 'dayGridMonth',
    locale: 'pl',
    firstDay: 1,
    height: 'auto',
    headerToolbar: { left: 'prev,next today', center: 'title', right: 'dayGridMonth,listMonth' },
    events: EVENTS,
    eventContent: renderChip,
    eventClick: (info) => {
      info.jsEvent.preventDefault();
      const p = info.event.extendedProps;
      openModal({ title: info.event.title, poster: p.poster, count: p.count, types: p.types,
                  days: [{ date: p.date, showings: p.showings }] });
    },
  });
  cal.render();
});
</script>
</body>
</html>
""")


def _showing(s: Screening) -> dict:
    return {"time": s.time, "cinema": s.cinema, "type": s.cinema_type, "url": s.url}


def _film_key(s: Screening):
    return s.tmdb_id if s.tmdb_id is not None else s.title


def _group_events(screenings: list[Screening]) -> list[dict]:
    """Kalendarz: jeden event = film w danym dniu."""
    groups: dict[tuple, list[Screening]] = defaultdict(list)
    for s in screenings:
        groups[(_film_key(s), s.date)].append(s)

    events = []
    for (_, date), items in groups.items():
        items.sort(key=lambda s: s.time)
        title = next((s.original_title for s in items if s.original_title), items[0].title)
        events.append({
            "title": title,
            "start": date,
            "allDay": True,
            "extendedProps": {
                "date": date,
                "poster": next((s.poster_path for s in items if s.poster_path), None),
                "count": len(items),
                "types": sorted({s.cinema_type for s in items}),
                "showings": [_showing(s) for s in items],
            },
        })
    return events


def _film_list(screenings: list[Screening]) -> list[dict]:
    """Sidebar: jeden wpis = film, z seansami pogrupowanymi po dniach."""
    films: dict[object, list[Screening]] = defaultdict(list)
    for s in screenings:
        films[_film_key(s)].append(s)

    result = []
    for items in films.values():
        title = next((s.original_title for s in items if s.original_title), items[0].title)
        by_day: dict[str, list[Screening]] = defaultdict(list)
        for s in items:
            by_day[s.date].append(s)
        days = [
            {"date": date, "showings": [_showing(s) for s in sorted(by_day[date], key=lambda s: s.time)]}
            for date in sorted(by_day)
        ]
        result.append({
            "title": title,
            "poster": next((s.poster_path for s in items if s.poster_path), None),
            "types": sorted({s.cinema_type for s in items}),
            "count": len(items),
            "days": days,
        })
    result.sort(key=lambda f: (-f["count"], f["title"].lower()))
    return result


def render(screenings: list[Screening], user: str,
           out_path: Path | str = DEFAULT_OUT) -> Path:
    """Zapisuje statyczny HTML z kalendarzem. Zwraca ścieżkę pliku."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    events = _group_events(screenings)
    films = _film_list(screenings)
    page = _TEMPLATE.substitute(
        user=html.escape(user or "—"),
        count=len(screenings),
        updated=dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        c_mux=COLORS["multiplex"],
        c_std=COLORS["studyjne"],
        events_json=json.dumps(events, ensure_ascii=False),
        films_json=json.dumps(films, ensure_ascii=False),
        colors_json=json.dumps(COLORS, ensure_ascii=False),
    )
    out.write_text(page, encoding="utf-8")
    log.info("Render: %s (%d filmów, %d filmodni, %d seansów)",
             out, len(films), len(events), len(screenings))
    return out
