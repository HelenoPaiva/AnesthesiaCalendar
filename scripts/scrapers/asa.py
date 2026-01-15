from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple, Optional

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
    m = MONTHS[_norm_month(month)]
    d = int(day)
    y = int(year)
    return f"{y:04d}-{m:02d}-{d:02d}"


def _find_meeting_range(text: str) -> Optional[Tuple[str, str]]:
    """
    Looks for: "October 16-20, 2026" OR "October 16–20, 2026"
    Returns (start_ymd, end_ymd)
    """
    # dash can be "-" or "–" or "—"
    m = re.search(
        r"\b([A-Za-z]+)\s+(\d{1,2})\s*[-–—]\s*(\d{1,2}),\s*(\d{4})\b",
        text
    )
    if not m:
        return None
    month, d1, d2, year = m.group(1), m.group(2), m.group(3), m.group(4)
    return _ymd(month, d1, year), _ymd(month, d2, year)


def _find_general_open_close(text: str) -> Optional[Tuple[str, str]]:
    """
    From the MGB page:
    "General session submissions for ASA 2026 in San Diego are open from August 26 until November 13, 2025."
    Returns (open_ymd, close_ymd)
    """
    m = re.search(
        r"General session submissions for ASA\s*2026.*?open from\s+([A-Za-z]+)\s+(\d{1,2})\s+until\s+([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )
    if not m:
        return None

    m1, d1, m2, d2, y2 = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
    # Start year is not written; infer from end year (works for Aug->Nov 2025)
    y1 = y2
    return _ymd(m1, d1, y1), _ymd(m2, d2, y2)


def _find_named_window(text: str, label: str) -> Optional[Tuple[str, str]]:
    """
    Extracts windows like:
      "PBLD Dec 2, 2025- Feb 23, 2026"
      "Scientific Abstracts Jan6-Mar 21, 2026"
      "Medically Challenging Cases Feb 3-April 28, 2026"

    Returns (open_ymd, close_ymd)
    """
    # allow "Jan6" with no space; allow optional year on start
    pattern = rf"{re.escape(label)}\s+" \
              r"([A-Za-z]+)\s*([0-9]{1,2})(?:,\s*([0-9]{4}))?\s*[-–—]\s*" \
              r"([A-Za-z]+)\s*([0-9]{1,2}),\s*([0-9]{4})"
    m = re.search(pattern, text, flags=re.IGNORECASE)
    if not m:
        return None

    sm, sd, sy_opt, em, ed, ey = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5), m.group(6)

    # If start year missing, infer:
    # - if start month/day logically before end month/day, same year as end year
    # - else previous year (rare for these)
    if sy_opt:
        sy = sy_opt
    else:
        sy = ey

    return _ymd(sm, sd, sy), _ymd(em, ed, ey)


def scrape_asa(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    urls = cfg.get("urls", []) or []
    warnings: List[str] = []
    events: List[Dict[str, Any]] = []

    if not urls:
        return [], ["No source URLs configured in data/sources.json."]

    # Try URLs until one works
    text = None
    used_url = None
    for url in urls:
        try:
            t, _ct = fetch_text(url)
            text = t
            used_url = url
            break
        except Exception as e:
            warnings.append(f"Fetch failed for {url}: {e}")

    if not text or not used_url:
        return [], warnings or ["Failed to fetch any ASA source URL."]

    # Meeting date range (ASA 2026)
    meeting = _find_meeting_range(text)
    if meeting:
        start_ymd, end_ymd = meeting
        events.append({
            "series": "ASA",
            "year": 2026,
            "type": "congress",
            "start_date": start_ymd,
            "end_date": end_ymd,
            "location": "San Diego, CA, USA",
            "link": used_url,
            "priority": 10
        })
    else:
        warnings.append("Could not find meeting date range (e.g., 'October 16-20, 2026').")

    # General Session submissions open/close (custom titles)
    gen = _find_general_open_close(text)
    if gen:
        open_ymd, close_ymd = gen

        events.append({
            "series": "ASA",
            "year": 2026,
            "type": "other_deadline",
            "date": open_ymd,
            "location": "—",
            "link": used_url,
            "priority": 8,
            "title": {
                "en": "ASA 2026 — General session submissions open",
                "pt": "ASA 2026 — Abertura de submissões (sessões gerais)"
            }
        })
        events.append({
            "series": "ASA",
            "year": 2026,
            "type": "other_deadline",
            "date": close_ymd,
            "location": "—",
            "link": used_url,
            "priority": 8,
            "title": {
                "en": "ASA 2026 — General session submissions deadline",
                "pt": "ASA 2026 — Prazo final (sessões gerais)"
            }
        })
    else:
        warnings.append("Could not find General session submissions open/close window.")

    # PBLD window
    pbld = _find_named_window(text, "PBLD")
    if pbld:
        open_ymd, close_ymd = pbld
        events.append({
            "series": "ASA",
            "year": 2026,
            "type": "other_deadline",
            "date": open_ymd,
            "location": "—",
            "link": used_url,
            "priority": 7,
            "title": {
                "en": "ASA 2026 — PBLD submissions open",
                "pt": "ASA 2026 — Abertura submissões PBLD"
            }
        })
        events.append({
            "series": "ASA",
            "year": 2026,
            "type": "other_deadline",
            "date": close_ymd,
            "location": "—",
            "link": used_url,
            "priority": 7,
            "title": {
                "en": "ASA 2026 — PBLD submissions deadline",
                "pt": "ASA 2026 — Prazo final submissões PBLD"
            }
        })
    else:
        warnings.append("Could not find PBLD date window.")

    # Scientific Abstracts window → map to abstract_open + abstract_deadline
    sci = _find_named_window(text, "Scientific Abstracts")
    if sci:
        open_ymd, close_ymd = sci
        events.append({
            "series": "ASA",
            "year": 2026,
            "type": "abstract_open",
            "date": open_ymd,
            "location": "—",
            "link": used_url,
            "priority": 10,
            "title": {
                "en": "ASA 2026 — Scientific abstracts open",
                "pt": "ASA 2026 — Abertura de resumos científicos"
            }
        })
        events.append({
            "series": "ASA",
            "year": 2026,
            "type": "abstract_deadline",
            "date": close_ymd,
            "location": "—",
            "link": used_url,
            "priority": 10,
            "title": {
                "en": "ASA 2026 — Scientific abstracts deadline",
                "pt": "ASA 2026 — Prazo final resumos científicos"
            }
        })
    else:
        warnings.append("Could not find Scientific Abstracts date window.")

    # Medically Challenging Cases window
    mcc = _find_named_window(text, "Medically Challenging Cases")
    if mcc:
        open_ymd, close_ymd = mcc
        events.append({
            "series": "ASA",
            "year": 2026,
            "type": "other_deadline",
            "date": open_ymd,
            "location": "—",
            "link": used_url,
            "priority": 6,
            "title": {
                "en": "ASA 2026 — Medically challenging cases open",
                "pt": "ASA 2026 — Abertura casos desafiadores"
            }
        })
        events.append({
            "series": "ASA",
            "year": 2026,
            "type": "other_deadline",
            "date": close_ymd,
            "location": "—",
            "link": used_url,
            "priority": 6,
            "title": {
                "en": "ASA 2026 — Medically challenging cases deadline",
                "pt": "ASA 2026 — Prazo final casos desafiadores"
            }
        })
    else:
        warnings.append("Could not find Medically Challenging Cases date window.")

    return events, warnings
