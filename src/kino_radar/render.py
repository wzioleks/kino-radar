"""Generuje public/index.html z mini-kalendarzem FullCalendar (CDN, bez build stepu).

Eventy = zmatchowane seanse, kolor wg cinema_type. Klik w event -> URL biletu/kina.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import logging
from pathlib import Path

from .models import Screening

log = logging.getLogger(__name__)

DEFAULT_OUT = Path("public/index.html")

# Kolory wg typu kina.
COLORS = {
    "multiplex": "#2563eb",  # niebieski
    "studyjne": "#dc2626",   # czerwony
}

_TEMPLATE = """<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kino-radar — Twoja watchlista w kinach Gdańska</title>
<script src="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.15/index.global.min.js"></script>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
         margin: 0; padding: 1.5rem; background: #0f172a; color: #e2e8f0; }}
  header {{ max-width: 1000px; margin: 0 auto 1rem; }}
  h1 {{ font-size: 1.4rem; margin: 0 0 .3rem; }}
  .meta {{ color: #94a3b8; font-size: .85rem; }}
  .legend {{ display: flex; gap: 1rem; margin-top: .6rem; font-size: .85rem; }}
  .dot {{ display: inline-block; width: .8rem; height: .8rem; border-radius: 50%;
         margin-right: .35rem; vertical-align: middle; }}
  #calendar {{ max-width: 1000px; margin: 0 auto; background: #1e293b;
              padding: 1rem; border-radius: .75rem; }}
  a.fc-event {{ cursor: pointer; }}
</style>
</head>
<body>
<header>
  <h1>🎬 Kino-radar — Gdańsk</h1>
  <div class="meta">Filmy z watchlisty <strong>{user}</strong> grające w kinach.
    {count} seansów · zaktualizowano {updated}</div>
  <div class="legend">
    <span><span class="dot" style="background:{c_mux}"></span>multipleks</span>
    <span><span class="dot" style="background:{c_std}"></span>kino studyjne</span>
  </div>
</header>
<div id="calendar"></div>
<script>
const EVENTS = {events_json};
document.addEventListener('DOMContentLoaded', () => {{
  const cal = new FullCalendar.Calendar(document.getElementById('calendar'), {{
    initialView: 'dayGridMonth',
    locale: 'pl',
    firstDay: 1,
    height: 'auto',
    headerToolbar: {{ left: 'prev,next today', center: 'title',
                     right: 'dayGridMonth,timeGridWeek,listWeek' }},
    eventTimeFormat: {{ hour: '2-digit', minute: '2-digit', hour12: false }},
    events: EVENTS,
    eventClick: (info) => {{
      if (info.event.url) {{ window.open(info.event.url, '_blank'); info.jsEvent.preventDefault(); }}
    }},
  }});
  cal.render();
}});
</script>
</body>
</html>
"""


def _to_event(s: Screening) -> dict:
    return {
        "title": f"{s.title} · {s.cinema}",
        "start": f"{s.date}T{s.time}:00",
        "url": s.url,
        "color": COLORS.get(s.cinema_type, "#64748b"),
    }


def render(screenings: list[Screening], user: str,
           out_path: Path | str = DEFAULT_OUT) -> Path:
    """Zapisuje statyczny HTML z kalendarzem. Zwraca ścieżkę pliku."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    events = [_to_event(s) for s in screenings]
    page = _TEMPLATE.format(
        user=html.escape(user or "—"),
        count=len(screenings),
        updated=dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        c_mux=COLORS["multiplex"],
        c_std=COLORS["studyjne"],
        events_json=json.dumps(events, ensure_ascii=False),
    )
    out.write_text(page, encoding="utf-8")
    log.info("Render: %s (%d eventów)", out, len(events))
    return out
