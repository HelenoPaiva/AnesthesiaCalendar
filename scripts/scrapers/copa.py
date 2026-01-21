# scripts/scrapers/copa.py
#
# COPA SAESP scraper (year-specific, driven by sources.json)
# Version: v2026-01-19h
#
# Strategy:
#   - Read the first URL from cfg["urls"], e.g.
#       https://copa2026.saesp.org.br/en/
#   - Extract the year from "copaYYYY".
#   - From the *English* site (base_url), scrape congress range:
#       "April 23–26, 2026"   (month day–day, year)
#   - From the *Portuguese* temas-livres page:
#       https://copaYYYY.saesp.org.br/temas-livres/
#     scrape abstract deadline:
#       "Submeta seu trabalho até 30 de janeiro de 2026"
#
#   Output:
#     - 1 congress event (type="congress")
#     - 0 or 1 abstract_deadline event (type="abstract_deadline")
#
#   This scraper is intentionally year-specific:
#     - It does NOT scan 2025–2030.
#     - When COPA 2027 launches, you just update sources.json to:
#         "https://copa2027.saesp.org.br/en/"

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple
from urllib.error import HTTPError, URLError
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
    """Fetch but return None on HTTP/network errors."""
    try:
        return _fetch(url)
    except HTTPError:
        return None
    except URLError:
        return None
    except Exception:
        return None


def _ymd(y: int, m: int, d: int) -> str:
    return f"{y:04d}-{m:02d}-{d:02d}"


def _parse_en_range(text: str, warnings: List[str]) -> Tuple[str | None, str | None, int | None]:
    """
    Parse congress range in EN format, e.g.:
        'April 23–26, 2026'
        'April 23-26, 2026'

    Returns: (start_iso, end_iso, year) or (None, None, None).
    """
    m = re.search(
        r"([A-Z][a-z]+)\s+(\d{1,2})\s*[–-]\s*(\d{1,2}),\s*(20\d{2})",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        warnings.append(
            f"[COPA] Could not parse EN congress range like 'April 23–26, 2026' from: '{text[:120]}' (v2026-01-19h)"
        )
        return None, None, None

    month_name = m.group(1).lower()
    d1 = int(m.group(2))
    d2 = int(m.group(3))
    year = int(m.group(4))

    mnum = MONTHS_EN.get(month_name)
    if not mnum:
        warnings.append(f"[COPA] Unknown EN month in congress range: '{month_name}' (v2026-01-19h)")
        return None, None, None

    return _ymd(year, mnum, d1), _ymd(year, mnum, d2), year


def _parse_pt_single_date(text: str, warnings: List[str]) -> str | None:
    """
    Parse a single PT date, e.g.:
        '30 de janeiro de 2026'

    Returns ISO 'YYYY-MM-DD' or None.
    """
    m = re.search(
        r"(\d{1,2})\s+de\s+([A-Za-zçãéíóúÁÉÍÓÚâêôàèìòù]+)\s+de\s+(20\d{2})",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        warnings.append(f"[COPA] Could not parse single PT date from: '{text[:120]}' (v2026-01-19h)")
        return None

    d = int(m.group(1))
    month_name = m.group(2).lower()
    year = int(m.group(3))

    month_name_norm = (
        month_name.replace("ç", "c")
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

    mnum = MONTHS_PT.get(month_name_norm)
    if not mnum:
        warnings.append(f"[COPA] Unknown PT month in single date: '{month_name}' (v2026-01-19h)")
        return None

    return _ymd(year, mnum, d)


def scrape_copa(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Year-specific COPA scraper.

    Uses cfg["urls"][0] as the canonical base, e.g.:
        https://copa2026.saesp.org.br/en/

    Steps:
      1) Extract year from 'copaYYYY'.
      2) Fetch base EN page, parse 'April 23–26, 2026' line for congress.
      3) Fetch PT 'temas-livres' page, parse 'Submeta seu trabalho até ...'
         for abstract deadline.
    """
    warnings: List[str] = []
    urls = cfg.get("urls") or []
    if not urls:
        warnings.append("[COPA] No source URLs configured in data/sources.json. (v2026-01-19h)")
        return [], warnings

    base_url = urls[0]
    m_year = re.search(r"copa(20\d{2})", base_url)
    if not m_year:
        warnings.append(
            f"[COPA] Could not extract year from base URL: {base_url} (v2026-01-19h)"
        )
        return [], warnings

    try:
        year = int(m_year.group(1))
    except ValueError:
        warnings.append(
            f"[COPA] Invalid year parsed from base URL: {base_url} (v2026-01-19h)"
        )
        return [], warnings

    # Normalise base root (without /en/ etc.)
    # e.g. https://copa2026.saesp.org.br/en/ -> https://copa2026.saesp.org.br
    base_root = re.sub(r"/en/?$", "", base_url.rstrip("/"))

    # 1) Fetch EN homepage (for 'April 23–26, 2026')
    html_en = _try_fetch(base_url)
    if not html_en:
        warnings.append(f"[COPA] Failed to fetch COPA EN page: {base_url} (v2026-01-19h)")
        return [], warnings

    text_en = re.sub(r"\s+", " ", html_en, flags=re.DOTALL)

    # 2) Find congress range line (EN)
    # We look near 'elementor-icon-list-text' and a month name.
    block_match = re.search(
        r"elementor-icon-list-text[^<]*>[^<]*([A-Z][a-z]+\s+\d{1,2}\s*[–-]\s*\d{1,2},\s*20\d{2})",
        text_en,
        flags=re.IGNORECASE,
    )
    congress_range_str = None
    if block_match:
        congress_range_str = block_match.group(1)
    else:
        # Fallback: try raw 'April 23–26, 2026' pattern anywhere
        m_any = re.search(
            r"([A-Z][a-z]+\s+\d{1,2}\s*[–-]\s*\d{1,2},\s*20\d{2})",
            text_en,
            flags=re.IGNORECASE,
        )
        if m_any:
            congress_range_str = m_any.group(1)

    events: List[Dict[str, Any]] = []
    congress_found = False
    abstract_found = False

    if congress_range_str:
        start_iso, end_iso, year_found = _parse_en_range(congress_range_str, warnings)
        if start_iso and end_iso:
            used_year = year_found or year
            events.append(
                {
                    "series": "COPA",
                    "year": used_year,
                    "type": "congress",
                    "start_date": start_iso,
                    "end_date": end_iso,
                    "location": "Transamerica Expo Center, São Paulo, Brazil",
                    "link": base_url,
                    "priority": 8,
                    "title": {
                        "en": f"COPA {used_year} — Paulista Congress of Anesthesiology",
                        "pt": f"COPA {used_year} — Congresso Paulista de Anestesiologia",
                    },
                    "evidence": {
                        "url": base_url,
                        "snippet": congress_range_str,
                        "field": "copa_congress_range_en",
                    },
                    "source": "scraped",
                }
            )
            congress_found = True
    else:
        warnings.append(
            f"[COPA] Could not find EN congress date like 'April 23–26, 20XX' on {base_url}. (v2026-01-19h)"
        )

    # 3) Fetch PT temas-livres page for abstract deadline
    temas_url = f"{base_root}/temas-livres/"
    html_pt = _try_fetch(temas_url)
    if html_pt:
        text_pt = re.sub(r"\s+", " ", html_pt, flags=re.DOTALL)

        m_abs = re.search(
            r"Submeta seu trabalho\s+até\s+(\d{1,2}\s+de\s+[A-Za-zçãéíóúÁÉÍÓÚâêôàèìòù]+\s+de\s+20\d{2})",
            text_pt,
            flags=re.IGNORECASE,
        )
        if m_abs:
            date_str = m_abs.group(1)
            date_iso = _parse_pt_single_date(date_str, warnings)
            if date_iso:
                events.append(
                    {
                        "series": "COPA",
                        "year": year,
                        "type": "abstract_deadline",
                        "date": date_iso,
                        "location": "Transamerica Expo Center, São Paulo, Brazil",
                        "link": temas_url,
                        "priority": 8,
                        "title": {
                            "en": f"COPA {year} — Abstract submission deadline",
                            "pt": f"COPA {year} — Prazo final para submissão de trabalhos",
                        },
                        "evidence": {
                            "url": temas_url,
                            "snippet": date_str,
                            "field": "copa_abstract_deadline_pt",
                        },
                        "source": "scraped",
                    }
                )
                abstract_found = True
        else:
            warnings.append(
                f"[COPA] Could not find 'Submeta seu trabalho até ...' abstract deadline on {temas_url}. (v2026-01-19h)"
            )
    else:
        warnings.append(
            f"[COPA] Could not fetch temas-livres page: {temas_url}. (v2026-01-19h)"
        )

    # Final DEBUG line so you always know this version ran and what it saw
    warnings.append(
        f"[COPA DEBUG] base={base_url} year={year} congress_found={congress_found} abstract_found={abstract_found} (v2026-01-19h)"
    )

    return events, warnings
