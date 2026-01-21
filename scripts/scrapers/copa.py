# scripts/scrapers/copa.py
#
# COPA SAESP scraper (year-agnostic, robust, minimal dependencies)
# Version: v2026-01-19f
#
# Strategy:
#   - For a range of years around "now", probe:
#       https://copa{YEAR}.saesp.org.br/temas-livres/
#   - On each page, look for:
#       "23 a 26 de abril de 2026"  -> congress date range (pt-BR)
#       "Submeta seu trabalho até 30 de janeiro de 2026" -> abstract deadline
#   - No hard dependency on the "tabela-copa" block; registration
#     deadlines can be added later, but we don't break if the table changes.
#
#   Produces, for each year where content is found:
#       - congress (type="congress")
#       - abstract_deadline (type="abstract_deadline")

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


# Portuguese month names
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
    """Fetch but return None on HTTP 4xx/5xx and network errors."""
    try:
        return _fetch(url)
    except HTTPError as e:
        # 404, 410, 402 etc => treat as missing
        if 400 <= e.code < 600:
            return None
        return None
    except URLError:
        return None
    except Exception:
        return None


def _ymd(y: int, m: int, d: int) -> str:
    return f"{y:04d}-{m:02d}-{d:02d}"


def _parse_pt_range(text: str, warnings: List[str]) -> Tuple[str | None, str | None, int | None]:
    """
    Parse congress range of the form:
        '23 a 26 de abril de 2026'
    Returns (start_iso, end_iso, year) or (None, None, None).
    """
    m = re.search(
        r"(\d{1,2})\s*a\s*(\d{1,2})\s+de\s+([A-Za-zçãéíóúÁÉÍÓÚâêôàèìòù]+)\s+de\s+(20\d{2})",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        warnings.append("[COPA] Could not parse congress date range like '23 a 26 de abril de 2026'.")
        return None, None, None

    d1 = int(m.group(1))
    d2 = int(m.group(2))
    month_name = m.group(3).lower()
    year = int(m.group(4))

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

    mnum = MONTHS_PT.get(month_name_norm, None)
    if not mnum:
        warnings.append(f"[COPA] Unknown PT month in congress range: '{month_name}'")
        return None, None, None

    start_iso = _ymd(year, mnum, d1)
    end_iso = _ymd(year, mnum, d2)
    return start_iso, end_iso, year


def _parse_pt_single_date(text: str, warnings: List[str]) -> str | None:
    """
    Parse a single PT date in the form:
        '30 de janeiro de 2026'
    Returns ISO 'YYYY-MM-DD' or None.
    """
    m = re.search(
        r"(\d{1,2})\s+de\s+([A-Za-zçãéíóúÁÉÍÓÚâêôàèìòù]+)\s+de\s+(20\d{2})",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        warnings.append(f"[COPA] Could not parse single PT date from: '{text[:120]}'")
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

    mnum = MONTHS_PT.get(month_name_norm, None)
    if not mnum:
        warnings.append(f"[COPA] Unknown PT month in single date: '{month_name}'")
        return None

    return _ymd(year, mnum, d)


def _scrape_copa_year(year: int, warnings: List[str]) -> List[Dict[str, Any]]:
    """
    Scrape a single COPA year from:
        https://copa{year}.saesp.org.br/temas-livres/
    Returns a list of events for that year (0+).
    """
    base_root = f"https://copa{year}.saesp.org.br"
    temas_url = f"{base_root}/temas-livres/"

    html = _try_fetch(temas_url)
    if not html:
        warnings.append(f"[COPA] temas-livres not reachable for {year}: {temas_url} (v2026-01-19f)")
        return []

    # Flatten whitespace for easier regex matching
    text = re.sub(r"\s+", " ", html, flags=re.DOTALL)

    events: List[Dict[str, Any]] = []
    congress_found = False
    abstract_found = False

    # ---- Congress range ----
    # We search near a "23 a 26 de abril de 2026"-like pattern.
    m_range = re.search(
        r"(\d{1,2}\s*a\s*\d{1,2}\s+de\s+[A-Za-zçãéíóúÁÉÍÓÚâêôàèìòù]+\s+de\s+20\d{2})",
        text,
        flags=re.IGNORECASE,
    )
    if m_range:
        range_str = m_range.group(1)
        start_iso, end_iso, y_detected = _parse_pt_range(range_str, warnings)
        if start_iso and end_iso:
            # Prefer detected year, but if it somehow mismatches, keep year argument
            used_year = y_detected or year
            events.append(
                {
                    "series": "COPA",
                    "year": used_year,
                    "type": "congress",
                    "start_date": start_iso,
                    "end_date": end_iso,
                    "location": "São Paulo, Brazil",
                    "link": temas_url,
                    "priority": 8,
                    "title": {
                        "en": f"COPA {used_year} — Paulista Congress of Anesthesiology",
                        "pt": f"COPA {used_year} — Congresso Paulista de Anestesiologia",
                    },
                    "evidence": {
                        "url": temas_url,
                        "snippet": range_str,
                        "field": "copa_congress_range_pt",
                    },
                    "source": "scraped",
                }
            )
            congress_found = True
    else:
        warnings.append(
            f"[COPA] Could not find congress PT range 'dd a dd de mês de yyyy' on {temas_url}. (v2026-01-19f)"
        )

    # ---- Abstract submission deadline ----
    # Pattern like: "Submeta seu trabalho até 30 de janeiro de 2026"
    m_abs = re.search(
        r"Submeta seu trabalho\s+até\s+(\d{1,2}\s+de\s+[A-Za-zçãéíóúÁÉÍÓÚâêôàèìòù]+\s+de\s+20\d{2})",
        text,
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
                    "location": "São Paulo, Brazil",
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
            f"[COPA] Could not find 'Submeta seu trabalho até ...' abstract deadline on {temas_url}. (v2026-01-19f)"
        )

    warnings.append(
        f"[COPA DEBUG] year={year} congress_found={congress_found} abstract_found={abstract_found} url={temas_url} (v2026-01-19f)"
    )

    return events


def scrape_copa(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Year-agnostic COPA scraper.

    - Ignores cfg.urls content structure beyond discovering a base year.
    - Instead, probes temas-livres pages:
        https://copaYYYY.saesp.org.br/temas-livres/
      for YYYY near the current UTC year.
    """
    warnings: List[str] = []
    urls = cfg.get("urls") or []

    if not urls:
        warnings.append("[COPA] No source URLs configured in data/sources.json. (v2026-01-19f)")
        return [], warnings

    # Try to infer a hint year from the first configured URL (if present),
    # otherwise just use current UTC year.
    now_year = datetime.utcnow().year
    hint_year = None

    m_y = re.search(r"copa(20\d{2})", urls[0])
    if m_y:
        try:
            hint_year = int(m_y.group(1))
        except ValueError:
            hint_year = None

    center_year = hint_year or now_year

    # Probe a small window of years around center_year
    start_year = max(2024, center_year - 1)
    end_year = center_year + 4

    all_events: List[Dict[str, Any]] = []

    for y in range(start_year, end_year + 1):
        events_y = _scrape_copa_year(y, warnings)
        all_events.extend(events_y)

    if not all_events:
        warnings.append(
            f"[COPA] No events produced for years {start_year}-{end_year} "
            f"(site structure may have changed). (v2026-01-19f)"
        )

    warnings.append(
        f"[COPA DEBUG] window={start_year}-{end_year} total_events={len(all_events)} (v2026-01-19f)"
    )

    return all_events, warnings
