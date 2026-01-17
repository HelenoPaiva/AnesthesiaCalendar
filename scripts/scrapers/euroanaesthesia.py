# scripts/scrapers/euroanaesthesia.py

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


MONTHS_EN = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
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


def _exists(url: str) -> bool:
    try:
        _fetch(url)
        return True
    except HTTPError as e:
        if e.code in (404, 410):
            return False
        # other HTTP errors might be transient; treat as "exists" but failing
        return True
    except URLError:
        return True
    except Exception:
        return True


def _ymd(y: int, m: int, d: int) -> str:
    return f"{y:04d}-{m:02d}-{d:02d}"


def _parse_dd_mon_yyyy(date_str: str, warnings: List[str]) -> Tuple[int | None, int | None, int | None]:
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
    # keyword first
    m = re.search(
        rf"{keyword}[^0-9]{{0,140}}(\d{{1,2}}\s+[A-Za-z]+\s+20\d{{2}})",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        return m.group(1)
    # date first
    m = re.search(
        rf"(\d{{1,2}}\s+[A-Za-z]+\s+20\d{{2}})[^0-9]{{0,140}}{keyword}",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        return m.group(1)
    return None


def _scrape_one_year(url: str, year: int) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    try:
        html = _fetch(url)
    except Exception as e:
        return [], [f"[EUROANAESTHESIA] Failed to fetch {url}: {e}"]

    text = re.sub(r"\s+", " ", html, flags=re.DOTALL)

    events: List[Dict[str, Any]] = []

    # Congress date range near "Euroanaesthesia {year}"
    m_cong = re.search(
        rf"Euroanaesthesia\s*{year}[^0-9]{{0,220}}?(\d{{1,2}})\s*[-–]\s*(\d{{1,2}})\s+([A-Za-z]+)\s+({year})",
        text,
        flags=re.IGNORECASE,
    )
    if m_cong:
        d1 = int(m_cong.group(1))
        d2 = int(m_cong.group(2))
        month_name = m_cong.group(3).lower()
        mnum = MONTHS_EN.get(month_name)
        if mnum:
            events.append(
                {
                    "series": "EUROANAESTHESIA",
                    "year": year,
                    "type": "congress",
                    "start_date": _ymd(year, mnum, d1),
                    "end_date": _ymd(year, mnum, d2),
                    "location": "Rotterdam, The Netherlands",  # may change in future years
                    "link": url,
                    "priority": 8,
                    "title": {
                        "en": f"Euroanaesthesia {year} — ESAIC Annual Congress",
                        "pt": f"Euroanaesthesia {year} — Congresso anual da ESAIC",
                    },
                    "source": "scraped",
                }
            )
        else:
            warnings.append(f"[EUROANAESTHESIA] Unknown month in congress range on {url}.")
    else:
        warnings.append(f"[EUROANAESTHESIA] Congress date range not found for {year} on {url}.")

    def add_deadline(keyword: str, etype: str, tail_en: str, tail_pt: str) -> None:
        ds = _find_date_near_keyword(text, keyword, warnings)
        if not ds:
            return
        y, mnum, d = _parse_dd_mon_yyyy(ds, warnings)
        if y and mnum and d:
            events.append(
                {
                    "series": "EUROANAESTHESIA",
                    "year": year,
                    "type": etype,
                    "date": _ymd(y, mnum, d),
                    "location": "Rotterdam, The Netherlands",
                    "link": url,
                    "priority": 8,
                    "title": {"en": f"Euroanaesthesia {year} — {tail_en}", "pt": f"Euroanaesthesia {year} — {tail_pt}"},
                    "source": "scraped",
                }
            )

    add_deadline("abstract submission opens", "abstract_open", "Abstract submission opens", "Abertura para submissão de resumos")
    add_deadline("abstract submission closes", "abstract_deadline", "Abstract submission deadline", "Prazo final para submissão de resumos")
    add_deadline("early registration closes", "early_bird_deadline", "Early registration deadline", "Prazo para inscrição early-bird")
    add_deadline("late registration closes", "registration_deadline", "Late registration deadline", "Prazo para inscrição tardia")

    return events, warnings


def scrape_euroanaesthesia(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Year-agnostic Euroanaesthesia scraper.

    It discovers available year pages:
      base/2026/, base/2027/, ... until it hits 404/410.
    """
    warnings: List[str] = []
    urls = cfg.get("urls") or []
    if not urls:
        return [], ["[EUROANAESTHESIA] No URLs configured in sources.json."]

    base = urls[0].rstrip("/") + "/"
    # Ensure base is the root, not /2026/
    base = re.sub(r"/20\d{2}/?$", "/", base)

    now_year = datetime.utcnow().year
    start_year = max(2020, now_year - 1)  # allow early publication
    max_years_ahead = 6  # conservative: scrape up to ~6 editions ahead

    all_events: List[Dict[str, Any]] = []
    all_warnings: List[str] = []

    # Probe sequentially so we stop at first definitive 404/410 gap
    consecutive_missing = 0
    for y in range(start_year, start_year + max_years_ahead + 1):
        url = f"{base}{y}/"
        if not _exists(url):
            consecutive_missing += 1
            if consecutive_missing >= 2:
                break
            continue
        consecutive_missing = 0
        ev, w = _scrape_one_year(url, y)
        all_events.extend(ev)
        all_warnings.extend(w)

    if not all_events:
        all_warnings.append("[EUROANAESTHESIA] No events produced (site structure may have changed).")

    return all_events, all_warnings