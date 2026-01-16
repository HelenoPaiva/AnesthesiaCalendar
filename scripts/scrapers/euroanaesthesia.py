# scripts/scrapers/euroanaesthesia.py

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple
from urllib.request import Request, urlopen


def _fetch(url: str) -> str:
  headers = {
    "User-Agent": "Mozilla/5.0 (compatible; AnesthesiaCalendarBot/1.0; +https://helenopaiva.github.io/AnesthesiaCalendar/)"
  }
  req = Request(url, headers=headers)
  with urlopen(req, timeout=20) as resp:  # nosec
    raw = resp.read()
  return raw.decode("utf-8", errors="ignore")


MONTHS_SHORT = {
  "jan": 1,
  "feb": 2,
  "mar": 3,
  "apr": 4,
  "may": 5,
  "jun": 6,
  "jul": 7,
  "aug": 8,
  "sep": 9,
  "oct": 10,
  "nov": 11,
  "dec": 12,
}


def _ymd(y: int, m: int, d: int) -> str:
  return f"{y:04d}-{m:02d}-{d:02d}"


def _scrape_dates_from_esaic_events(url: str, warnings: List[str]) -> Tuple[str | None, str | None]:
  """Returns (start_ymd, end_ymd) or (None, None)."""
  html = _fetch(url)
  text = re.sub(r"\s+", " ", html, flags=re.DOTALL)

  # Example snippet:
  # "Euroanaesthesia 2026. 06 Jun. – 08 Jun. 2026"
  pattern = re.compile(
    r"Euroanaesthesia\s+2026[^0-9]*(\d{2})\s+([A-Za-z]{3})\.\s*[\u2013\-]\s*(\d{2})\s+([A-Za-z]{3})\.\s+(20\d{2})",
    re.IGNORECASE,
  )

  m = pattern.search(text)
  if not m:
    warnings.append("[EUROANAESTHESIA] Could not find 'Euroanaesthesia 2026' block on ESAIC events page.")
    return None, None

  d1 = int(m.group(1))
  mon1 = m.group(2).lower()
  d2 = int(m.group(3))
  mon2 = m.group(4).lower()
  year = int(m.group(5))

  m1 = MONTHS_SHORT.get(mon1)
  m2 = MONTHS_SHORT.get(mon2)
  if not m1 or not m2:
    warnings.append(f"[EUROANAESTHESIA] Unknown month abbreviation(s): {mon1}, {mon2}")
    return None, None

  return _ymd(year, m1, d1), _ymd(year, m2, d2)


def _scrape_location_from_euro_site(url: str, warnings: List[str]) -> str:
  """
  Best-effort: look for 'Rotterdam' / 'Netherlands' on the Euroanaesthesia 2026 site.
  Fallback to a simple 'Rotterdam, Netherlands'.
  """
  try:
    html = _fetch(url)
  except Exception as e:  # pragma: no cover - network
    warnings.append(f"[EUROANAESTHESIA] Failed to fetch Euroanaesthesia site: {e}")
    return "Rotterdam, Netherlands"

  text = re.sub(r"\s+", " ", html, flags=re.DOTALL)

  # Quick heuristic: capture "...Rotterdam Ahoy, the Netherlands..."
  m = re.search(
    r"Rotterdam[^,.]*[, ]+\s*the Netherlands",
    text,
    flags=re.IGNORECASE,
  )
  if m:
    loc = m.group(0)
    loc = re.sub(r"\s+", " ", loc).strip()
    # Normalise case a bit
    loc = loc.replace("the Netherlands", "The Netherlands")
    return loc

  # Fallback
  return "Rotterdam, Netherlands"


def scrape_euroanaesthesia(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
  warnings: List[str] = []
  urls = cfg.get("urls") or []
  if not urls:
    return [], ["[EUROANAESTHESIA] No URLs configured in sources.json."]

  events: List[Dict[str, Any]] = []

  esaic_url = None
  euro_site_url = None
  for u in urls:
    u_lower = u.lower()
    if "esaic.org" in u_lower:
      esaic_url = u
    elif "euroanaesthesia.org" in u_lower:
      euro_site_url = u

  start_date = end_date = None
  if esaic_url:
    try:
      start_date, end_date = _scrape_dates_from_esaic_events(esaic_url, warnings)
    except Exception as e:  # pragma: no cover
      warnings.append(f"[EUROANAESTHESIA] Error scraping ESAIC events page: {e}")
  else:
    warnings.append("[EUROANAESTHESIA] No ESAIC events URL configured.")

  if not start_date or not end_date:
    # If date parsing failed, don't emit an event (better than wrong dates).
    return events, warnings

  location = "Rotterdam, Netherlands"
  if euro_site_url:
    location = _scrape_location_from_euro_site(euro_site_url, warnings)

  events.append(
    {
      "series": "EUROANAESTHESIA",
      "year": 2026,
      "type": "congress",
      "start_date": start_date,
      "end_date": end_date,
      "location": location,
      "link": euro_site_url or esaic_url,
      "priority": 8,
      "title": {
        "en": "Euroanaesthesia 2026 — ESAIC Annual Congress",
        "pt": "Euroanaesthesia 2026 — Congresso anual da ESAIC",
      },
      "source": "scraped",
    }
  )

  return events, warnings
