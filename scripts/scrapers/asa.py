from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple, Optional

from scripts.scrapers.http import fetch_text


# --------------------------------
# Helpers
# --------------------------------

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def _norm_month(s: str) -> str:
  return re.sub(r"[^a-z]", "", s.strip().lower())


def _ymd(month: str, day: str, year: str) -> str:
  m_key = _norm_month(month)
  if m_key not in MONTHS:
      raise ValueError(f"Unknown month name: {month}")
  m = MONTHS[m_key]
  d = int(day)
  y = int(year)
  return f"{y:04d}-{m:02d}-{d:02d}"


def _iter_sources(cfg: Dict[str, Any]) -> List[Tuple[int, str]]:
  """
  Supports:
    - cfg["sources"] = [{url, trust?}, ...]
    - cfg["urls"]    = [url, ...]
  Returns list of (trust, url), highest trust first.
  """
  out: List[Tuple[int, str]] = []

  srcs = cfg.get("sources")
  if isinstance(srcs, list) and srcs:
      for s in srcs:
          if not isinstance(s, dict):
              continue
          url = str(s.get("url", "")).strip()
          if not url:
              continue
          trust_raw = s.get("trust", 10)
          try:
              trust = int(trust_raw)
          except Exception:
              trust = 10
          out.append((trust, url))

  if not out:
      for u in cfg.get("urls", []) or []:
          url = str(u).strip()
          if url:
              out.append((10, url))

  # sort by trust desc, then url (for stability)
  out.sort(key=lambda pair: (-pair[0], pair[1]))
  # dedupe by url
  seen = set()
  uniq: List[Tuple[int, str]] = []
  for trust, url in out:
      if url in seen:
          continue
      seen.add(url)
      uniq.append((trust, url))
  return uniq


def _find_meeting_ranges(text: str) -> List[Tuple[int, str, str, str]]:
  """
  Finds all date ranges of the form:
    "October 16-20, 2026"
    "Oct 8 – 12, 2027"

  Returns list of tuples:
    (year, start_ymd, end_ymd, matched_snippet)
  """
  pattern = r"\b([A-Za-z]{3,9})\s+(\d{1,2})\s*[-–—]\s*(\d{1,2}),\s*(20\d{2})\b"
  results: List[Tuple[int, str, str, str]] = []
  for m in re.finditer(pattern, text):
      month, d1, d2, year = m.group(1), m.group(2), m.group(3), m.group(4)
      try:
          s = _ymd(month, d1, year)
          e = _ymd(month, d2, year)
      except Exception:
          continue
      results.append((int(year), s, e, m.group(0)))
  return results


def _find_scientific_windows(text: str) -> List[Tuple[int, str, str, str]]:
  """
  Finds windows like:
    "Scientific Abstracts Jan 6-Mar 31, 2026"
    "Scientific abstracts January 6 – March 31, 2027"

  Returns list of tuples:
    (year, open_ymd, close_ymd, matched_snippet)
  """
  pattern = (
      r"Scientific\s+Abstracts.*?"
      r"([A-Za-z]{3,9})\s*([0-9]{1,2})(?:,\s*([0-9]{4}))?\s*"
      r"[-–—]\s*"
      r"([A-Za-z]{3,9})\s*([0-9]{1,2}),\s*(20\d{2})"
  )
  results: List[Tuple[int, str, str, str]] = []
  for m in re.finditer(pattern, text, flags=re.IGNORECASE | re.DOTALL):
      sm, sd, sy_opt, em, ed, ey = (
          m.group(1),
          m.group(2),
          m.group(3),
          m.group(4),
          m.group(5),
          m.group(6),
      )
      sy = sy_opt if sy_opt else ey
      try:
          open_ymd = _ymd(sm, sd, sy)
          close_ymd = _ymd(em, ed, ey)
      except Exception:
          continue
      results.append((int(ey), open_ymd, close_ymd, m.group(0).strip()))
  return results


# --------------------------------
# Main scraper
# --------------------------------

def scrape_asa(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
  """
  ASA scraper – multi-year, no hard-coded year.

  Strategy:
    1) Fetch all configured URLs (data/sources.json).
    2) From each page, extract:
         - one or more meeting date ranges "Month d–d, YYYY"
         - one or more "Scientific Abstracts" windows
    3) Merge by (year, dates), keeping highest-trust source when duplicates exist.
    4) Emit events for all future-ish years found (e.g., this year and beyond).

  If nothing parses at all, this returns an empty list plus warnings – in that
  case you can rely on manual_overrides.json for baseline ASA data.
  """
  warnings: List[str] = []
  events: List[Dict[str, Any]] = []

  sources = _iter_sources(cfg)
  if not sources:
      warnings.append("ASA: no URLs configured in data/sources.json.")
      return events, warnings

  # maps
  meeting_map: Dict[Tuple[int, str, str], Dict[str, Any]] = {}
  sci_map: Dict[int, Dict[str, Any]] = {}  # key: year

  for trust, url in sources:
      try:
          text, _ct = fetch_text(url)
      except Exception as e:
          warnings.append(f"ASA: failed to fetch {url}: {e}")
          continue

      # Meetings (congress dates)
      for year, start_ymd, end_ymd, snippet in _find_meeting_ranges(text):
          key = (year, start_ymd, end_ymd)
          prev = meeting_map.get(key)
          if prev is None or trust > prev["trust"]:
              meeting_map[key] = {
                  "year": year,
                  "start": start_ymd,
                  "end": end_ymd,
                  "trust": trust,
                  "url": url,
                  "snippet": snippet[:220],
              }

      # Scientific abstract windows
      for year, open_ymd, close_ymd, snippet in _find_scientific_windows(text):
          prev = sci_map.get(year)
          if prev is None or trust > prev["trust"]:
              sci_map[year] = {
                  "year": year,
                  "open": open_ymd,
                  "close": close_ymd,
                  "trust": trust,
                  "url": url,
                  "snippet": snippet[:220],
              }

  if not meeting_map and not sci_map:
      warnings.append("ASA: no meetings or abstract windows detected in any source.")
      return events, warnings

  # Emit congress events for each meeting we found
  for key, info in sorted(meeting_map.items(), key=lambda kv: kv[0]):
      year, start_ymd, end_ymd = key
      ev = {
          "series": "ASA",
          "year": year,
          "type": "congress",
          "start_date": start_ymd,
          "end_date": end_ymd,
          # Location is hard to parse generically; keep generic + link as source of truth.
          "location": "ASA Annual Meeting",
          "link": info["url"],
          "priority": 10,
          "title": {
              "en": f"ANESTHESIOLOGY {year} — ASA Annual Meeting",
              "pt": f"ANESTHESIOLOGY {year} — Congresso anual da ASA",
          },
          "evidence": {
              "url": info["url"],
              "snippet": info["snippet"],
              "field": "meeting_range",
          },
      }
      events.append(ev)

  # Emit abstracts events for each year we have a window
  for year, info in sorted(sci_map.items(), key=lambda kv: kv[0]):
      open_ymd = info["open"]
      close_ymd = info["close"]

      ev_open = {
          "series": "ASA",
          "year": year,
          "type": "abstract_open",
          "date": open_ymd,
          "location": "—",
          "link": info["url"],
          "priority": 10,
          "title": {
              "en": f"ASA {year} — Scientific abstracts open",
              "pt": f"ASA {year} — Abertura de resumos científicos",
          },
          "evidence": {
              "url": info["url"],
              "snippet": info["snippet"],
              "field": "scientific_abstracts_window_open",
          },
      }

      ev_deadline = {
          "series": "ASA",
          "year": year,
          "type": "abstract_deadline",
          "date": close_ymd,
          "location": "—",
          "link": info["url"],
          "priority": 10,
          "title": {
              "en": f"ASA {year} — Scientific abstracts deadline",
              "pt": f"ASA {year} — Prazo final resumos científicos",
          },
          "evidence": {
              "url": info["url"],
              "snippet": info["snippet"],
              "field": "scientific_abstracts_window_close",
          },
      }

      events.extend([ev_open, ev_deadline])

  return events, warnings
