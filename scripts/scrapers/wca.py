# scripts/scrapers/wca.py

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


MONTHS_EN = {
  "january": 1,
  "february": 2,
  "march": 3,
  "april": 4,
  "may": 5,
  "june": 6,
  "july": 7,
  "august": 8,
  "september": 9,
  "october": 10,
  "november": 11,
  "december": 12,
}


def _ymd(y: int, m: int, d: int) -> str:
  return f"{y:04d}-{m:02d}-{d:02d}"


def _scrape_congress_from_wfsa(url: str, warnings: List[str]) -> List[Dict[str, Any]]:
  html = _fetch(url)
  text = re.sub(r"\s+", " ", html, flags=re.DOTALL)

  events: List[Dict[str, Any]] = []

  # Example snippet:
  # "19th WCA 2026 – Marrakech, Morocco, 15-19 April 2026"
  pattern = re.compile(
    r"19th\s+WCA\s+(20\d{2}).*?–\s*([^,]+,\s*[^,]+),\s*(\d{1,2})-(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})",
    re.IGNORECASE,
  )

  m = pattern.search(text)
  if not m:
    warnings.append("[WCA] Could not find 19th WCA 2026 block on WFSA page.")
    return events

  congress_year = int(m.group(1))
  loc = m.group(2).strip()
  d1 = int(m.group(3))
  d2 = int(m.group(4))
  month_name = m.group(5).lower()
  year2 = int(m.group(6))

  # Sanity: congress year should be 2026
  if congress_year != 2026 or year2 != 2026:
    warnings.append(f"[WCA] Parsed WCA congress year mismatch: {congress_year} vs {year2}.")
    return events

  month = MONTHS_EN.get(month_name)
  if not month:
    warnings.append(f"[WCA] Unknown month name for congress: {month_name}")
    return events

  start_date = _ymd(2026, month, d1)
  end_date = _ymd(2026, month, d2)

  events.append(
    {
      "series": "WCA",
      "year": 2026,
      "type": "congress",
      "start_date": start_date,
      "end_date": end_date,
      "location": loc,
      "link": "https://wcacongress.org/",
      "priority": 10,
      "title": {
        "en": "WCA 2026 — World Congress of Anaesthesiologists",
        "pt": "WCA 2026 — Congresso Mundial de Anestesiologia",
      },
      "source": "scraped",
    }
  )

  return events


def _scrape_key_dates_from_wca(url: str, warnings: List[str]) -> List[Dict[str, Any]]:
  html = _fetch(url)
  text = re.sub(r"\s+", " ", html, flags=re.DOTALL)

  events: List[Dict[str, Any]] = []

  # Key dates examples:
  # "30 September 2025 – Abstract Submission Deadline"
  # "21 January 2026 – Early Bird Registration Deadline"
  # "31 March 2026 – Regular Registration Deadline"
  pattern = re.compile(
    r"(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})\s*[\u2013\-]\s*([^<]+?Deadline)",
    re.IGNORECASE,
  )

  for m in pattern.finditer(text):
    day = int(m.group(1))
    month_name = m.group(2).lower()
    year = int(m.group(3))
    label = m.group(4).strip()

    month = MONTHS_EN.get(month_name)
    if not month:
      warnings.append(f"[WCA] Unknown month name in key date: {month_name}")
      continue

    date_ymd = _ymd(year, month, day)

    # All these key dates belong to the 2026 congress
    congress_year = 2026

    lower = label.lower()
    if "abstract" in lower:
      etype = "abstract_deadline"
      title_en = "WCA 2026 — Abstract submission deadline"
      title_pt = "WCA 2026 — Prazo final de submissão de resumos"
    elif "early bird" in lower:
      etype = "early_bird_deadline"
      title_en = "WCA 2026 — Early-bird registration deadline"
      title_pt = "WCA 2026 — Prazo de inscrição early-bird"
    elif "regular registration" in lower:
      etype = "registration_deadline"
      title_en = "WCA 2026 — Regular registration deadline"
      title_pt = "WCA 2026 — Prazo de inscrição regular"
    else:
      # Unrecognised label (ignore for now)
      continue

    events.append(
      {
        "series": "WCA",
        "year": congress_year,
        "type": etype,
        "date": date_ymd,
        "location": "Marrakech, Morocco",
        "link": "https://wcacongress.org/",
        "priority": 9,
        "title": {"en": title_en, "pt": title_pt},
        "source": "scraped",
      }
    )

  if not events:
    warnings.append("[WCA] No key dates matched on wcacongress.org (regex may need update).")

  return events


def scrape_wca(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
  warnings: List[str] = []
  urls = cfg.get("urls") or []
  if not urls:
    return [], ["[WCA] No URLs configured in sources.json."]

  events: List[Dict[str, Any]] = []

  wfsa_url = None
  wca_url = None
  for u in urls:
    u_lower = u.lower()
    if "wfsahq.org" in u_lower:
      wfsa_url = u
    elif "wcacongress.org" in u_lower:
      wca_url = u

  if wfsa_url:
    try:
      events.extend(_scrape_congress_from_wfsa(wfsa_url, warnings))
    except Exception as e:  # pragma: no cover - network
      warnings.append(f"[WCA] Error scraping WFSA world-congress page: {e}")
  else:
    warnings.append("[WCA] No WFSA world-congress URL configured.")

  if wca_url:
    try:
      events.extend(_scrape_key_dates_from_wca(wca_url, warnings))
    except Exception as e:  # pragma: no cover
      warnings.append(f"[WCA] Error scraping WCA key dates: {e}")
  else:
    warnings.append("[WCA] No wcacongress.org URL configured for key dates.")

  return events, warnings
