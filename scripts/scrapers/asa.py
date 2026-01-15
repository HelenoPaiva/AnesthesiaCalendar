from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple, Optional

from scripts.scrapers.http import fetch_text


# ------------------------------
# Helpers
# ------------------------------

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


def _find_meeting_range(text: str) -> Optional[Tuple[str, str, str]]:
    """
    Tries to find a date range like:
      "October 16-20, 2026"
      "Oct 16 – 20, 2026"
    Returns (start_ymd, end_ymd, matched_snippet) or None.
    """
    # allow short or long month, various dashes
    pattern = r"\b([A-Za-z]{3,9})\s+(\d{1,2})\s*[-–—]\s*(\d{1,2}),\s*(20\d{2})\b"
    m = re.search(pattern, text)
    if not m:
        return None
    month, d1, d2, year = m.group(1), m.group(2), m.group(3), m.group(4)
    s = _ymd(month, d1, year)
    e = _ymd(month, d2, year)
    return s, e, m.group(0)


def _find_scientific_abstracts_window(text: str) -> Optional[Tuple[str, str, str]]:
    """
    Looks for something like:
      "Scientific Abstracts Jan 6-Mar 31, 2026"
      "Scientific abstracts January 6 – March 31, 2026"
    Returns (open_ymd, close_ymd, matched_snippet) or None.
    """
    pattern = (
        r"Scientific\s+Abstracts.*?"
        r"([A-Za-z]{3,9})\s*([0-9]{1,2})(?:,\s*([0-9]{4}))?\s*"
        r"[-–—]\s*"
        r"([A-Za-z]{3,9})\s*([0-9]{1,2}),\s*(20\d{2})"
    )
    m = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return None

    sm, sd, sy_opt, em, ed, ey = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5), m.group(6)
    # if start year omitted, assume same as end year
    sy = sy_opt if sy_opt else ey

    open_ymd = _ymd(sm, sd, sy)
    close_ymd = _ymd(em, ed, ey)
    return open_ymd, close_ymd, m.group(0).strip()


def _iter_urls_from_cfg(cfg: Dict[str, Any]) -> List[str]:
    """
    Accepts either:
      - cfg["sources"] = [{url, role?, trust?}, ...]
      - cfg["urls"] = [url, ...]
    and returns a deduplicated list of URLs (most “trusted” first if trust exists).
    """
    urls: List[Tuple[int, str]] = []

    # New structure with per-source trust
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
            urls.append((trust, url))

    # Legacy simple list
    if not urls:
        for u in cfg.get("urls", []) or []:
            u_str = str(u).strip()
            if not u_str:
                continue
            urls.append((10, u_str))

    # sort by trust desc, then url (for stability), then uniq
    urls.sort(key=lambda pair: (-pair[0], pair[1]))
    seen = set()
    ordered: List[str] = []
    for _t, url in urls:
        if url in seen:
            continue
        seen.add(url)
        ordered.append(url)
    return ordered


# ------------------------------
# Static baseline
# ------------------------------

def _baseline_events() -> List[Dict[str, Any]]:
    """
    Always-returned ASA 2026 baseline. Live scraping can adjust these if it succeeds.
    """
    base: List[Dict[str, Any]] = []

    # Main congress
    base.append(
        {
            "series": "ASA",
            "year": 2026,
            "type": "congress",
            "start_date": "2026-10-16",
            "end_date": "2026-10-20",
            "location": "San Diego, CA, USA",
            "link": "https://www.asahq.org/meetings/anesthesiology-annual-meeting",
            "priority": 10,
            "title": {
                "en": "ANESTHESIOLOGY 2026 — ASA Annual Meeting",
                "pt": "ANESTHESIOLOGY 2026 — Congresso anual da ASA",
            },
        }
    )

    # Scientific abstracts open
    base.append(
        {
            "series": "ASA",
            "year": 2026,
            "type": "abstract_open",
            "date": "2026-01-06",
            "location": "—",
            "link": "https://www.asahq.org/annualmeeting/education/submissions",
            "priority": 10,
            "title": {
                "en": "ASA 2026 — Scientific abstracts open",
                "pt": "ASA 2026 — Abertura de resumos científicos",
            },
        }
    )

    # Scientific abstracts deadline
    base.append(
        {
            "series": "ASA",
            "year": 2026,
            "type": "abstract_deadline",
            "date": "2026-03-31",
            "location": "—",
            "link": "https://www.asahq.org/annualmeeting/education/submissions",
            "priority": 10,
            "title": {
                "en": "ASA 2026 — Scientific abstracts deadline",
                "pt": "ASA 2026 — Prazo final resumos científicos",
            },
        }
    )

    return base


def _find_event(events: List[Dict[str, Any]], etype: str) -> Optional[Dict[str, Any]]:
    for ev in events:
        if ev.get("series") == "ASA" and ev.get("year") == 2026 and ev.get("type") == etype:
            return ev
    return None


# ------------------------------
# Public scraper
# ------------------------------

def scrape_asa(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    ASA scraper with static baseline + best-effort live scraping.

    - Always returns the static ASA 2026 events.
    - Then tries to fetch configured URLs (data/sources.json).
    - If it can parse a meeting date range or scientific abstract window,
      it updates the baseline events and attaches an `evidence` field.
    - If parsing fails or fetching fails, you still have baseline events and
      get a warning in data/ledger.json.
    """
    events = _baseline_events()
    warnings: List[str] = [
        "ASA scraper: using static baseline for ANESTHESIOLOGY 2026; attempting live updates from configured sources."
    ]

    urls = _iter_urls_from_cfg(cfg)
    if not urls:
        warnings.append("ASA: no URLs configured in data/sources.json (sources/urls).")
        return events, warnings

    for url in urls:
        try:
            text, _ct = fetch_text(url)
        except Exception as e:
            warnings.append(f"ASA: failed to fetch {url}: {e}")
            continue

        # 1) meeting range
        try:
            mr = _find_meeting_range(text)
        except Exception as e:
            warnings.append(f"ASA: error while parsing meeting range from {url}: {e}")
            mr = None

        if mr:
            s_ymd, e_ymd, snippet = mr
            ev_cong = _find_event(events, "congress")
            if ev_cong:
                # Only update if different (to avoid spurious noise)
                if ev_cong.get("start_date") != s_ymd or ev_cong.get("end_date") != e_ymd:
                    old = (ev_cong.get("start_date"), ev_cong.get("end_date"))
                    ev_cong["start_date"] = s_ymd
                    ev_cong["end_date"] = e_ymd
                    warnings.append(
                        f"ASA: meeting range updated from {old} to {(s_ymd, e_ymd)} based on {url}"
                    )
                # Attach/overwrite evidence
                ev_cong["evidence"] = {
                    "url": url,
                    "snippet": snippet[:220],
                    "field": "meeting_range",
                }

        # 2) scientific abstracts window
        try:
            sw = _find_scientific_abstracts_window(text)
        except Exception as e:
            warnings.append(f"ASA: error while parsing scientific abstracts window from {url}: {e}")
            sw = None

        if sw:
            open_ymd, close_ymd, snippet = sw

            ev_open = _find_event(events, "abstract_open")
            ev_deadline = _find_event(events, "abstract_deadline")

            if ev_open:
                if ev_open.get("date") != open_ymd:
                    old = ev_open.get("date")
                    ev_open["date"] = open_ymd
                    warnings.append(
                        f"ASA: abstract_open updated from {old} to {open_ymd} based on {url}"
                    )
                ev_open["evidence"] = {
                    "url": url,
                    "snippet": snippet[:220],
                    "field": "scientific_abstracts_window_open",
                }

            if ev_deadline:
                if ev_deadline.get("date") != close_ymd:
                    old = ev_deadline.get("date")
                    ev_deadline["date"] = close_ymd
                    warnings.append(
                        f"ASA: abstract_deadline updated from {old} to {close_ymd} based on {url}"
                    )
                ev_deadline["evidence"] = {
                    "url": url,
                    "snippet": snippet[:220],
                    "field": "scientific_abstracts_window_close",
                }

    return events, warnings
