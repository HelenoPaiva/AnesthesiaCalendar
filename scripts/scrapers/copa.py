# scripts/scrapers/copa.py
#
# COPA SAESP scraper (single URL: temas-livres)
# Version: v2026-01-19i
#
# Strategy:
#   - Take cfg["urls"][0], e.g.:
#       https://copa2026.saesp.org.br/temas-livres/
#   - From that page, parse:
#       Congress dates (PT range):
#         "23 a 26 de abril de 2026"
#       Abstract deadline (PT single date):
#         "Submeta seu trabalho até 30 de janeiro de 2026"
#
#   Output:
#     - 1 congress event (type="congress")
#     - 0 or 1 abstract_deadline event (type="abstract_deadline")

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


MONTHS_PT = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "março": 3,
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


def _fetch(url: str) -> str:
    """HTTP GET with a reasonable User-Agent."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; AnesthesiaCalendarBot/1.0; "
            "+https://helenopaiva.github.io/AnesthesiaCalendar/)"
        )
    }
    req = Request(url, headers=headers)
    with urlopen(req, timeout=20) as resp:  # nosec - sandboxed in Actions
        raw = resp.read()
    return raw.decode("utf-8", errors="ignore")


def _try_fetch(url: str) -> str | None:
    try:
        return _fetch(url)
    except (HTTPError, URLError, Exception):
        return None


def _ymd(y: int, m: int, d: int) -> str:
    return f"{y:04d}-{m:02d}-{d:02d}"


def _normalize_pt_month(name: str) -> str:
    s = name.lower()
    s = (
        s.replace("ç", "c")
        .replace("ã", "a")
        .replace("á", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("ú", "u")
    )
    return s


def _parse_pt_range(text: str, warnings: List[str]) -> Tuple[str | None, str | None, int | None]:
    """
    Parse PT range like:
        '23 a 26 de abril de 2026'
    Returns (start_iso, end_iso, year) or (None, None, None).
    """
    m = re.search(
        r"(\d{1,2})\s*a\s*(\d{1,2})\s+de\s+([A-Za-zçãéíóúÁÉÍÓÚâêôàèìòù]+)\s+de\s+(20\d{2})",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        warnings.append(
            f"[COPA] Could not parse PT congress range like '23 a 26 de abril de 2026' from: '{text[:120]}' (v2026-01-19i)"
        )
        return None, None, None

    d1 = int(m.group(1))
    d2 = int(m.group(2))
    month_name_raw = m.group(3)
    year = int(m.group(4))

    month_name = _normalize_pt_month(month_name_raw)
    mnum = MONTHS_PT.get(month_name)
    if not mnum:
        warnings.append(
            f"[COPA] Unknown PT month in congress range: '{month_name_raw}' (norm='{month_name}') (v2026-01-19i)"
        )
        return None, None, None

    return _ymd(year, mnum, d1), _ymd(year, mnum, d2), year


def _parse_pt_single_date(text: str, warnings: List[str]) -> str | None:
    """
    Parse single PT date like:
        '30 de janeiro de 2026'
    Returns ISO 'YYYY-MM-DD' or None.
    """
    m = re.search(
        r"(\d{1,2})\s+de\s+([A-Za-zçãéíóúÁÉÍÓÚâêôàèìòù]+)\s+de\s+(20\d{2})",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        warnings.append(
            f"[COPA] Could not parse single PT date from: '{text[:120]}' (v2026-01-19i)"
        )
        return None

    d = int(m.group(1))
    month_raw = m.group(2)
    year = int(m.group(3))

    month_norm = _normalize_pt_month(month_raw)
    mnum = MONTHS_PT.get(month_norm)
    if not mnum:
        warnings.append(
            f"[COPA] Unknown PT month in single date: '{month_raw}' (norm='{month_norm}') (v2026-01-19i)"
        )
        return None

    return _ymd(year, mnum, d)


def scrape_copa(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    COPA SAESP scraper, driven by temas-livres URL only.

    Expected cfg format (from data/sources.json):

      {
        "series": "COPA",
        "priority": 8,
        "urls": [
          "https://copa2026.saesp.org.br/temas-livres/"
        ]
      }

    Steps:
      - Fetch that URL.
      - Find congress range "23 a 26 de abril de 2026".
      - Find abstract deadline "Submeta seu trabalho até 30 de janeiro de 2026".
    """
    warnings: List[str] = []
    urls = cfg.get("urls") or []
    if not urls:
        warnings.append("[COPA] No source URLs configured in data/sources.json. (v2026-01-19i)")
        return [], warnings

    target_url = urls[0]
    html = _try_fetch(target_url)
    if not html:
        warnings.append(f"[COPA] Failed to fetch {target_url}. (v2026-01-19i)")
        return [], warnings

    # Flatten whitespace so we can regex across tags.
    text = re.sub(r"\s+", " ", html, flags=re.DOTALL)

    # Try to extract congress range near an icon-list item, but ultimately
    # just look for '23 a 26 de abril de 2026'-style patterns.
    congress_found = False
    abstract_found = False
    events: List[Dict[str, Any]] = []

    # 1) Congress range: look for "dd a dd de <month> de 20xx"
    m_range = re.search(
        r"(\d{1,2}\s*a\s*\d{1,2}\s+de\s+[A-Za-zçãéíóúÁÉÍÓÚâêôàèìòù]+\s+de\s+20\d{2})",
        text,
        flags=re.IGNORECASE,
    )
    congress_range_str = m_range.group(1) if m_range else None

    if congress_range_str:
        start_iso, end_iso, year = _parse_pt_range(congress_range_str, warnings)
        if start_iso and end_iso and year:
            events.append(
                {
                    "series": "COPA",
                    "year": year,
                    "type": "congress",
                    "start_date": start_iso,
                    "end_date": end_iso,
                    "location": "Transamerica Expo Center, São Paulo, Brazil",
                    "link": target_url,
                    "priority": 8,
                    "title": {
                        "en": f"COPA {year} — Paulista Congress of Anesthesiology",
                        "pt": f"COPA {year} — Congresso Paulista de Anestesiologia",
                    },
                    "evidence": {
                        "url": target_url,
                        "snippet": congress_range_str,
                        "field": "copa_congress_range_pt",
                    },
                    "source": "scraped",
                }
            )
            congress_found = True
    else:
        warnings.append(
            f"[COPA] Could not find congress range like '23 a 26 de abril de 20XX' on {target_url}. (v2026-01-19i)"
        )

    # 2) Abstract deadline: "Submeta seu trabalho até 30 de janeiro de 2026"
    m_abs = re.search(
        r"Submeta seu trabalho\s+até\s+(\d{1,2}\s+de\s+[A-Za-zçãéíóúÁÉÍÓÚâêôàèìòù]+\s+de\s+20\d{2})",
        text,
        flags=re.IGNORECASE,
    )
    if m_abs:
        date_str = m_abs.group(1)
        date_iso = _parse_pt_single_date(date_str, warnings)
        if date_iso:
            # If we didn't get a congress year, infer from the date.
            # (year is last 4 digits in date_iso)
            year_from_date = int(date_iso[:4])
            events.append(
                {
                    "series": "COPA",
                    "year": year_from_date,
                    "type": "abstract_deadline",
                    "date": date_iso,
                    "location": "Transamerica Expo Center, São Paulo, Brazil",
                    "link": target_url,
                    "priority": 8,
                    "title": {
                        "en": f"COPA {year_from_date} — Abstract submission deadline",
                        "pt": f"COPA {year_from_date} — Prazo final para submissão de trabalhos",
                    },
                    "evidence": {
                        "url": target_url,
                        "snippet": date_str,
                        "field": "copa_abstract_deadline_pt",
                    },
                    "source": "scraped",
                }
            )
            abstract_found = True
    else:
        warnings.append(
            f"[COPA] Could not find 'Submeta seu trabalho até ...' abstract deadline on {target_url}. (v2026-01-19i)"
        )

    # Final debug marker
    warnings.append(
        f"[COPA DEBUG] url={target_url} congress_found={congress_found} abstract_found={abstract_found} (v2026-01-19i)"
    )

    return events, warnings
