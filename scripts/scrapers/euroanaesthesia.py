# scripts/scrapers/euroanaesthesia.py

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple
from urllib.request import Request, urlopen


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


def _fetch(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; AnesthesiaCalendarBot/1.0; "
            "+https://helenopaiva.github.io/AnesthesiaCalendar/)"
        )
    }
    req = Request(url, headers=headers)
    with urlopen(req, timeout=20) as resp:  # nosec - GitHub Actions sandbox
        raw = resp.read()
    return raw.decode("utf-8", errors="ignore")


def _ymd(y: int, m: int, d: int) -> str:
    return f"{y:04d}-{m:02d}-{d:02d}"


def _parse_dd_mon_yyyy(date_str: str, warnings: List[str]) -> Tuple[int | None, int | None, int | None]:
    """
    Parse '5 December 2025' into (year, month, day).
    Returns (None, None, None) on failure.
    """
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})", date_str.strip())
    if not m:
        warnings.append(f"[EUROANAESTHESIA] Could not parse date string: '{date_str}'")
        return None, None, None

    day = int(m.group(1))
    month_name = m.group(2).lower()
    year = int(m.group(3))

    month = MONTHS_EN.get(month_name)
    if not month:
        warnings.append(f"[EUROANAESTHESIA] Unknown month name: '{month_name}'")
        return None, None, None

    return year, month, day


def _find_date_near_keyword(text: str, keyword: str, warnings: List[str]) -> str | None:
    """
    Find a 'dd Month YYYY' date near a given keyword.
    Handles both 'Keyword ... 5 December 2025' and '5 December 2025 ... Keyword'.
    """
    # Keyword first, date after
    pattern1 = re.compile(
        rf"{keyword}[^0-9]{{0,120}}(\d{{1,2}}\s+[A-Za-z]+\s+20\d{{2}})",
        re.IGNORECASE,
    )
    m = pattern1.search(text)
    if m:
        return m.group(1)

    # Date first, keyword after
    pattern2 = re.compile(
        rf"(\d{{1,2}}\s+[A-Za-z]+\s+20\d{{2}})[^0-9]{{0,120}}{keyword}",
        re.IGNORECASE,
    )
    m = pattern2.search(text)
    if m:
        return m.group(1)

    warnings.append(f"[EUROANAESTHESIA] Did not find date near keyword '{keyword}'.")
    return None


def scrape_euroanaesthesia(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Scrape Euroanaesthesia key dates from euroanaesthesia.org/2026/.

    Produces:
      - congress (start_date, end_date)
      - abstract_open
      - abstract_deadline
      - early_bird_deadline
      - registration_deadline
    """
    warnings: List[str] = []
    urls = cfg.get("urls") or []
    if not urls:
        return [], ["[EUROANAESTHESIA] No URLs configured in sources.json."]

    base_url = urls[0]

    try:
        html = _fetch(base_url)
    except Exception as e:  # pragma: no cover - network
        return [], [f"[EUROANAESTHESIA] Failed to fetch {base_url}: {e}"]

    # Flatten whitespace for regex
    text = re.sub(r"\s+", " ", html, flags=re.DOTALL)

    events: List[Dict[str, Any]] = []

    # ----------------------------------------------------------------------
    # 1) Congress dates
    #
    # Relaxed pattern: look for "Euroanaesthesia 2026" followed by
    # something like "6-8 June 2026" within ~150 chars.
    # ----------------------------------------------------------------------
    m_cong = re.search(
        r"Euroanaesthesia\s*2026[^0-9]{0,150}?(\d{1,2})\s*[-–]\s*(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})",
        text,
        flags=re.IGNORECASE,
    )

    congress_year: int | None = None

    if m_cong:
        d1 = int(m_cong.group(1))
        d2 = int(m_cong.group(2))
        month_name = m_cong.group(3).lower()
        year = int(m_cong.group(4))

        mnum = MONTHS_EN.get(month_name)
        if mnum is None:
            warnings.append(f"[EUROANAESTHESIA] Unknown month in congress date: '{month_name}'")
        else:
            congress_year = year
            start_date = _ymd(year, mnum, d1)
            end_date = _ymd(year, mnum, d2)
            events.append(
                {
                    "series": "EUROANAESTHESIA",
                    "year": year,
                    "type": "congress",
                    "start_date": start_date,
                    "end_date": end_date,
                    "location": "Rotterdam, The Netherlands",
                    "link": base_url,
                    "priority": 8,
                    "title": {
                        "en": f"Euroanaesthesia {year} — ESAIC Annual Congress",
                        "pt": f"Euroanaesthesia {year} — Congresso anual da ESAIC",
                    },
                    "source": "scraped",
                }
            )
    else:
        warnings.append(
            "[EUROANAESTHESIA] Could not find congress date near 'Euroanaesthesia 2026'."
        )

    # ----------------------------------------------------------------------
    # 2) Deadline helper
    # ----------------------------------------------------------------------
    def add_deadline(keyword: str, etype: str, title_en: str, title_pt: str) -> None:
        nonlocal congress_year, events

        date_str = _find_date_near_keyword(text, keyword, warnings)
        if not date_str:
            return

        y, mnum, d = _parse_dd_mon_yyyy(date_str, warnings)
        if y is None or mnum is None or d is None:
            return

        date_ymd = _ymd(y, mnum, d)
        year_for_event = congress_year or y

        events.append(
            {
                "series": "EUROANAESTHESIA",
                "year": year_for_event,
                "type": etype,
                "date": date_ymd,
                "location": "Rotterdam, The Netherlands",
                "link": base_url,
                "priority": 8,
                "title": {"en": title_en, "pt": title_pt},
                "source": "scraped",
            }
        )

    # ----------------------------------------------------------------------
    # 3) Key deadlines (keywords are deliberately loose)
    # ----------------------------------------------------------------------

    # Abstracts
    add_deadline(
        keyword="abstract submission opens",
        etype="abstract_open",
        title_en="Euroanaesthesia 2026 — Abstract submission opens",
        title_pt="Euroanaesthesia 2026 — Abertura para submissão de resumos",
    )

    add_deadline(
        keyword="abstract submission closes",
        etype="abstract_deadline",
        title_en="Euroanaesthesia 2026 — Abstract submission deadline",
        title_pt="Euroanaesthesia 2026 — Prazo final para submissão de resumos",
    )

    # Early registration
    add_deadline(
        keyword="early registration closes",
        etype="early_bird_deadline",
        title_en="Euroanaesthesia 2026 — Early registration deadline",
        title_pt="Euroanaesthesia 2026 — Prazo para inscrição early-bird",
    )

    # Late registration
    add_deadline(
        keyword="late registration closes",
        etype="registration_deadline",
        title_en="Euroanaesthesia 2026 — Late registration deadline",
        title_pt="Euroanaesthesia 2026 — Prazo para inscrição tardia",
    )

    if not events and not warnings:
        warnings.append(
            "[EUROANAESTHESIA] No events produced from Euroanaesthesia page (regex likely needs update)."
        )

    return events, warnings