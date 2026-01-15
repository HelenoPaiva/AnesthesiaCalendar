from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from scripts.scrapers.http import fetch_text


MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def _norm_month(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.strip().lower())


def _ymd(month: str, day: str, year: str) -> str:
    m_key = _norm_month(month)
    if m_key not in MONTHS:
        raise ValueError(f"Unknown month: {month}")
    m = MONTHS[m_key]
    d = int(day)
    y = int(year)
    return f"{y:04d}-{m:02d}-{d:02d}"


def _iter_sources(cfg: Dict[str, Any]) -> List[Tuple[int, str]]:
    """
    Supports:
      - cfg["sources"] = [{url, trust?}, ...]
      - cfg["urls"]    = [url, ...]
    Returns list of (trust, url), highest-trust first, deduped.
    """
    pairs: List[Tuple[int, str]] = []

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
            pairs.append((trust, url))

    if not pairs:
        for u in cfg.get("urls", []) or []:
            url = str(u).strip()
            if url:
                pairs.append((10, url))

    pairs.sort(key=lambda p: (-p[0], p[1]))
    seen = set()
    out: List[Tuple[int, str]] = []
    for trust, url in pairs:
        if url in seen:
            continue
        seen.add(url)
        out.append((trust, url))
    return out


def _find_meeting_ranges(text: str) -> List[Tuple[int, str, str, str]]:
    """
    Find congress-like ranges such as:
      "October 16-20, 2026"
      "Oct 8 – 12, 2027"

    BUT only keep ranges whose *nearby context* mentions
    'ANESTHESIOLOGY' or 'annual meeting', to avoid picking up
    unrelated dates (courses, other events).

    Returns: list of (year, start_ymd, end_ymd, snippet_with_context).
    """
    pattern = r"\b([A-Za-z]{3,9})\s+(\d{1,2})\s*[-–—]\s*(\d{1,2}),\s*(20\d{2})\b"
    results: List[Tuple[int, str, str, str]] = []
    n = len(text)

    for m in re.finditer(pattern, text):
        month, d1, d2, year = m.group(1), m.group(2), m.group(3), m.group(4)

        # Look at a window around the match for context
        start = max(0, m.start() - 80)
        end = min(n, m.end() + 80)
        ctx = text[start:end]

        if not re.search(r"ANESTHESIOLOGY|annual meeting", ctx, flags=re.IGNORECASE):
            # likely not the main ASA annual meeting; skip
            continue

        try:
            s_ymd = _ymd(month, d1, year)
            e_ymd = _ymd(month, d2, year)
        except Exception:
            continue

        snippet = text[m.start():m.end()]
        results.append((int(year), s_ymd, e_ymd, snippet))

    return results


def scrape_asa(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    ASA scraper (multi-year, congress only).

    It will:
      - fetch all configured URLs in data/sources.json for series 'ASA'
      - extract date ranges associated with ANESTHESIOLOGY / annual meeting
      - create a congress event for each (year, start, end) it finds

    No year is hard-coded; if the page lists 2026, 2027, 2028, you get
    three congress events.

    Abstract deadlines can be kept in manual_overrides.json for now, until
    we have a stable, parseable source for them.
    """
    warnings: List[str] = []
    events: List[Dict[str, Any]] = []

    srcs = _iter_sources(cfg)
    if not srcs:
        warnings.append("ASA: no URLs configured in data/sources.json.")
        return events, warnings

    meeting_map: Dict[Tuple[int, str, str], Dict[str, Any]] = {}

    for trust, url in srcs:
        try:
            text, _ct = fetch_text(url)
        except Exception as e:
            warnings.append(f"ASA: failed to fetch {url}: {e}")
            continue

        for year, s_ymd, e_ymd, snippet in _find_meeting_ranges(text):
            key = (year, s_ymd, e_ymd)
            prev = meeting_map.get(key)
            if prev is None or trust > prev["trust"]:
                meeting_map[key] = {
                    "year": year,
                    "start": s_ymd,
                    "end": e_ymd,
                    "trust": trust,
                    "url": url,
                    "snippet": snippet,
                }

    if not meeting_map:
        warnings.append("ASA: no ANESTHESIOLOGY meeting ranges detected in any source.")
        return events, warnings

    for (year, s_ymd, e_ymd), info in sorted(meeting_map.items(), key=lambda kv: kv[0]):
        events.append(
            {
                "series": "ASA",
                "year": year,
                "type": "congress",
                "start_date": s_ymd,
                "end_date": e_ymd,
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
        )

    return events, warnings
