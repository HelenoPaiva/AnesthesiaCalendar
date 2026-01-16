# scripts/scrapers/euroanaesthesia.py

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple
from urllib.request import Request, urlopen


# Month names in English
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
    """HTTP GET with a decent User-Agent, return decoded HTML."""
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


def _parse_dd_mon_yyyy(date_str: str, warnings: List[str]) -> Tuple[int, int, int] | Tuple[None, None, None]:
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


def _extract_block(text: str, warnings: List[str]) -> str:
    """
    Extract the 'Important dates' block from the page text, if possible.
    Fallback to the whole text if the boundaries are not found.
    """
    m = re.search(
        r"Important dates(.*?)(Euroanaesthesia\s+\d{4}\s+will be held|Euroanaesthesia is recognised)",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        warnings.append("[EUROANAESTHESIA] Could not isolate 'Important dates' block; using full page text.")
        return text
    return m.group(1)


def scrape_euroanaesthesia(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Scrape Euroanaesthesia key dates from euroanaesthesia.org/2026/.

    Produces:
      - congress (start_date, end_date)
      - abstract_open
      - abstract_deadline
      - early_bird_deadline
      - registration_deadline (late registration closes)
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

    # Flatten whitespace to make regex easier
    text = re.sub(r"\s+", " ", html, flags=re.DOTALL)
    block = _extract_block(text, warnings)

    events: List[Dict[str, Any]] = []

    # ----------------------------------------------------------------------
    # 1) Congress dates: "Congress Dates 6-8 June 2026"
    # ----------------------------------------------------------------------
    m_cong = re.search(
        r"Congress Dates\s+(\d{1,2})\s*[-–]\s*(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})",
        block,
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
        warnings.append("[EUROANAESTHESIA] Could not find congress date pattern 'Congress Dates 6-8 June 2026'.")

    # If we didn't get a congress year, we still try to parse deadlines,
    # but we fall back to using the date's own year as 'year'.
    # (Better to show correct dates than nothing.)
    def add_deadline(label: str, etype: str, title_en: str, title_pt: str) -> None:
        nonlocal congress_year, events

        # label is literal text that appears before the date, e.g. "Abstract submission closes"
        pattern = rf"{label}\s+(\d{{1,2}}\s+[A-Za-z]+\s+20\d{{2}})"
        m = re.search(pattern, block, flags=re.IGNORECASE)
        if not m:
            warnings.append(f"[EUROANAESTHESIA] Did not find date for label '{label}'.")
            return

        date_str = m.group(1)
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
    # 2) Key deadlines inside "Important dates"
    #    Based exactly on the text from euroanaesthesia.org/2026/
    # ----------------------------------------------------------------------

    # Abstract submission opens (November 2025)
    add_deadline(
        label="Abstract submission opens",
        etype="abstract_open",
        title_en="Euroanaesthesia 2026 — Abstract submission opens",
        title_pt="Euroanaesthesia 2026 — Abertura para submissão de resumos",
    )

    # Abstract submission closes (December 2025)
    add_deadline(
        label="Abstract submission closes",
        etype="abstract_deadline",
        title_en="Euroanaesthesia 2026 — Abstract submission deadline",
        title_pt="Euroanaesthesia 2026 — Prazo final para submissão de resumos",
    )

    # Early registration closes (February 2026)
    add_deadline(
        label="Early registration closes (Physical congress)",
        etype="early_bird_deadline",
        title_en="Euroanaesthesia 2026 — Early registration deadline",
        title_pt="Euroanaesthesia 2026 — Prazo para inscrição early-bird",
    )

    # Late registration closes (June 2026)
    add_deadline(
        label="Late registration closes (Physical congress)",
        etype="registration_deadline",
        title_en="Euroanaesthesia 2026 — Late registration deadline",
        title_pt="Euroanaesthesia 2026 — Prazo para inscrição tardia",
    )

    if not events and not warnings:
        warnings.append("[EUROANAESTHESIA] No events produced from Euroanaesthesia page (regex may need update).")

    return events, warnings
