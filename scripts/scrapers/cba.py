# scripts/scrapers/cba.py

from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Tuple
from urllib.request import Request, urlopen


def _fetch(url: str) -> str:
  headers = {
    "User-Agent": "Mozilla/5.0 (compatible; AnesthesiaCalendarBot/1.0; +https://helenopaiva.github.io/AnesthesiaCalendar/)"
  }
  req = Request(url, headers=headers)
  with urlopen(req, timeout=20) as resp:  # nosec - GitHub Actions sandbox
    raw = resp.read()
  return raw.decode("utf-8", errors="ignore")


MONTHS_PT = {
  "janeiro": 1,
  "fevereiro": 2,
  "março": 3,
  "marco": 3,
  "abril": 4,
  "maio": 5,
  "junho": 6,
  "julho": 7,
  "agosto": 8,
  "setembro": 9,
  "outubro": 10,
  "novembro": 11,
  "dezembro": 12,
}


def _ymd(y: int, m: int, d: int) -> str:
  return f"{y:04d}-{m:02d}-{d:02d}"


def scrape_cba(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
  """
  Scrapes the official CBA site for the main congress dates.

  For now we only handle CBA 2026:
    - 26 a 29 de novembro de 2026
    - Centro de Eventos do Ceará - Fortaleza/CE
  """
  warnings: List[str] = []
  urls = cfg.get("urls") or []
  if not urls:
    return [], ["[CBA] No URLs configured in sources.json."]

  html = ""
  last_url = None
  for u in urls:
    last_url = u
    try:
      html = _fetch(u)
      if html:
        break
    except Exception as e:  # pragma: no cover - network
      warnings.append(f"[CBA] Failed to fetch {u}: {e}")

  if not html:
    return [], warnings or ["[CBA] Failed to fetch any configured URL."]

  text = re.sub(r"\s+", " ", html, flags=re.DOTALL).lower()

  # Pattern: "26 a 29 de novembro de 2026"
  m = re.search(
    r"(\d{1,2})\s*a\s*(\d{1,2})\s*de\s*([a-zç]+)\s*de\s*(20\d{2})",
    text,
  )
  if not m:
    warnings.append("[CBA] Could not find congress date range in page text.")
    return [], warnings

  d1 = int(m.group(1))
  d2 = int(m.group(2))
  month_name = m.group(3).replace("ç", "c")
  year = int(m.group(4))

  month = MONTHS_PT.get(month_name)
  if not month:
    warnings.append(f"[CBA] Unknown month name: {month_name}")
    return [], warnings

  start_date = _ymd(year, month, d1)
  end_date = _ymd(year, month, d2)

  # Try to grab the location snippet after the date (best-effort).
  loc = "Fortaleza, Brazil"
  after = text[m.end() : m.end() + 160]
  loc_match = re.search(
    r"centro de eventos[^.]+", after
  )
  if loc_match:
    loc = loc_match.group(0)
    loc = re.sub(r"\s+", " ", loc).strip()
    # Capitalize roughly
    loc = loc.replace(" - ", " – ").title().replace("Ceará", "Ceará")

  events: List[Dict[str, Any]] = []

  events.append(
    {
      "series": "CBA",
      "year": year,
      "type": "congress",
      "start_date": start_date,
      "end_date": end_date,
      "location": loc,
      "link": last_url or urls[0],
      "priority": 10,
      "title": {
        "en": f"CBA {year} — Brazilian Congress of Anaesthesiology",
        "pt": f"CBA {year} — Congresso Brasileiro de Anestesiologia",
      },
      "source": "scraped",
    }
  )

  return events, warnings
