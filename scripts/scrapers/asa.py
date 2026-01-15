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


# ---------- meeting ranges ----------

def _find_meeting_ranges(text: str) -> List[Tuple[int, str, str, str]]:
    """
    Find congress-like ranges such as:
      "October 16-20, 2026"
      "Oct 8 – 12, 2027"

    BUT only keep ranges whose nearby context mentions
    'ANESTHESIOLOGY' or 'annual meeting', to avoid unrelated dates.

    Returns: list of (year, start_ymd, end_ymd, snippet_with_dates_only).
    """
    pattern = r"\b([A-Za-z]{3,9})\s+(\d{1,2})\s*[-–—]\s*(\d{1,2}),\s*(20\d{2})\b"
    results: List[Tuple[int, str, str, str]] = []
    n = len(text)

    for m in re.finditer(pattern, text):
        month, d1, d2, year = m.group(1), m.group(2), m.group(3), m.group(4)

        # context window around the match
        start = max(0, m.start() - 80)
        end = min(n, m.end() + 80)
        ctx = text[start:end]

        if not re.search(r"ANESTHESIOLOGY|annual meeting", ctx, flags=re.IGNORECASE):
            continue

        try:
            s_ymd = _ymd(month, d1, year)
            e_ymd = _ymd(month, d2, year)
        except Exception:
            continue

        snippet = text[m.start():m.end()]
        results.append((int(year), s_ymd, e_ymd, snippet))

    return results


# ---------- submission windows ----------

def _find_window_for_label(text: str, label_pattern: str) -> Optional[Tuple[int, str, str, str]]:
    """
    Look for windows like:

      "Scientific Abstracts: January 6 – March 31, 2026"
      "Problem-Based Learning Discussion Sessions: December 2, 2025 – February 3, 2026"
      "General Session Submissions: August 26 - November 13, 2025"

    The general pattern is:

      <LABEL>: <Month> <d>[, yyyy]? – <Month> <d>, yyyy

    Returns (asa_year, open_ymd, close_ymd, snippet) or None.
    For ASA, we treat asa_year as the year of the closing date (ey).
    """
    pattern = (
        rf"{label_pattern}\s*:\s*"
        r"([A-Za-z]{3,9})\s*([0-9]{1,2})(?:,\s*(20\d{2}))?\s*"
        r"[–\-]\s*"
        r"([A-Za-z]{3,9})\s*([0-9]{1,2}),\s*(20\d{2})"
    )

    m = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return None

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
        return None

    asa_year = int(ey)  # we call the ASA year the closing year
    snippet = m.group(0).strip()
    return asa_year, open_ymd, close_ymd, snippet


LABELS = [
    # key, regex, is_scientific_abstracts
    ("scientific_abstracts", r"Scientific\s+Abstracts", True),
    ("general_session", r"General\s+Session\s+Submissions", False),
    ("pbl", r"Problem[-\s]+Based\s+Learning\s+Discussion\s+Sessions", False),
    ("exhibits", r"Scientific\s+and\s+Educational\s+Exhibits", False),
    ("mcc_qi", r"Medically\s+Challenging\s+Cases\s+and\s+Quality\s+Improvement\s+Projects", False),
]

LABEL_TEXT_EN = {
    "general_session": "General session submissions",
    "pbl": "PBLD submissions",
    "exhibits": "Scientific & educational exhibits",
    "mcc_qi": "Medically challenging cases / QI projects",
}

LABEL_TEXT_PT = {
    "general_session": "Submissões sessões gerais",
    "pbl": "Submissões PBLD",
    "exhibits": "Exposições científicas e educacionais",
    "mcc_qi": "Casos desafiadores / projetos de melhoria",
}


def scrape_asa(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    ASA scraper (multi-year, fully automatic).

    - Reads all configured ASA URLs.
    - Extracts ANESTHESIOLOGY congress date ranges.
    - Extracts submission windows from the 'education/submissions' page:
        * General Session Submissions
        * PBLD
        * Scientific Abstracts
        * Scientific & Educational Exhibits
        * Medically Challenging Cases & QI
    - Builds:
        * congress events for each year
        * abstract_open / abstract_deadline for Scientific Abstracts
        * other_deadline events for the other four categories
    """
    warnings: List[str] = []
    events: List[Dict[str, Any]] = []

    srcs = _iter_sources(cfg)
    if not srcs:
        warnings.append("ASA: no URLs configured in data/sources.json.")
        return events, warnings

    meeting_map: Dict[Tuple[int, str, str], Dict[str, Any]] = {}
    windows: Dict[Tuple[str, int], Dict[str, Any]] = {}

    for trust, url in srcs:
        try:
            text, _ct = fetch_text(url)
        except Exception as e:
            warnings.append(f"ASA: failed to fetch {url}: {e}")
            continue

        # Congress dates
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

        # Submissions windows for each label (on the submissions page)
        for key, label_re, _is_sci in LABELS:
            win = _find_window_for_label(text, label_re)
            if not win:
                continue
            asa_year, open_ymd, close_ymd, snippet = win
            win_key = (key, asa_year)
            prev = windows.get(win_key)
            if prev is None or trust > prev["trust"]:
                windows[win_key] = {
                    "year": asa_year,
                    "open": open_ymd,
                    "close": close_ymd,
                    "trust": trust,
                    "url": url,
                    "snippet": snippet,
                    "label_key": key,
                }

    if not meeting_map and not windows:
        warnings.append("ASA: no meetings or submission windows detected in any source.")
        return events, warnings

    # Build congress events
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

    # Build submission-window events
    for (label_key, year), info in sorted(windows.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        open_ymd = info["open"]
        close_ymd = info["close"]
        url = info["url"]
        snippet = info["snippet"]

        if label_key == "scientific_abstracts":
            # Scientific abstracts get dedicated types
            events.append(
                {
                    "series": "ASA",
                    "year": year,
                    "type": "abstract_open",
                    "date": open_ymd,
                    "location": "—",
                    "link": url,
                    "priority": 10,
                    "title": {
                        "en": f"ASA {year} — Scientific abstracts open",
                        "pt": f"ASA {year} — Abertura de resumos científicos",
                    },
                    "evidence": {
                        "url": url,
                        "snippet": snippet,
                        "field": "scientific_abstracts_window_open",
                    },
                }
            )
            events.append(
                {
                    "series": "ASA",
                    "year": year,
                    "type": "abstract_deadline",
                    "date": close_ymd,
                    "location": "—",
                    "link": url,
                    "priority": 10,
                    "title": {
                        "en": f"ASA {year} — Scientific abstracts deadline",
                        "pt": f"ASA {year} — Prazo final resumos científicos",
                    },
                    "evidence": {
                        "url": url,
                        "snippet": snippet,
                        "field": "scientific_abstracts_window_close",
                    },
                }
            )
        else:
            # Other categories → generic other_deadline, year is mostly internal
            en_label = LABEL_TEXT_EN.get(label_key, label_key)
            pt_label = LABEL_TEXT_PT.get(label_key, label_key)

            events.append(
                {
                    "series": "ASA",
                    "year": year,
                    "type": "other_deadline",
                    "date": open_ymd,
                    "location": "—",
                    "link": url,
                    "priority": 9,
                    "title": {
                        "en": f"{en_label} — open",
                        "pt": f"{pt_label} — abertura",
                    },
                    "evidence": {
                        "url": url,
                        "snippet": snippet,
                        "field": f"{label_key}_window_open",
                    },
                }
            )
            events.append(
                {
                    "series": "ASA",
                    "year": year,
                    "type": "other_deadline",
                    "date": close_ymd,
                    "location": "—",
                    "link": url,
                    "priority": 9,
                    "title": {
                        "en": f"{en_label} — deadline",
                        "pt": f"{pt_label} — prazo final",
                    },
                    "evidence": {
                        "url": url,
                        "snippet": snippet,
                        "field": f"{label_key}_window_close",
                    },
                }
            )

    return events, warnings
