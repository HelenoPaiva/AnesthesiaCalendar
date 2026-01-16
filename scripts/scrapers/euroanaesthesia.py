# scripts/scrapers/euroanaesthesia.py

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple
from urllib.request import Request, urlopen


MONTHS_EN_SHORT = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

MONTHS_PT = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "marco": 3,
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
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; AnesthesiaCalendarBot/1.0; "
            "+https://helenopaiva.github.io/AnesthesiaCalendar/)"
        )
    }
    req = Request(url, headers=headers)
    with urlopen(req, timeout=20) as resp:  # nosec
        raw = resp.read()
    return raw.decode("utf-8", errors="ignore")


def _ymd(y: int, m: int, d: int) -> str:
    return f"{y:04d}-{m:02d}-{d:02d}"


def _from_esaic_home(url: str, warnings: List[str]) -> List[Dict[str, Any]]:
    """
    Parse ESAIC homepage snippet: :contentReference[oaicite:7]{index=7}

      'Join us for Euroanaesthesia 2026 · 6-8 June 2026 | Rotterdam, The Netherlands'
    """
    html = _fetch(url)
    text = re.sub(r"\s+", " ", html, flags=re.DOTALL)

    m = re.search(
        r"Euroanaesthesia\s*2026[^0-9]+(\d{1,2})\s*[–\-]\s*(\d{1,2})\s+([A-Za-z]{3,})\s+(20\d{2})",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        warnings.append("[EUROANAESTHESIA] Could not parse '6-8 June 2026' on ESAIC homepage.")
        return []

    d1 = int(m.group(1))
    d2 = int(m.group(2))
    month_name = m.group(3)[:3].lower()
    year = int(m.group(4))

    month = MONTHS_EN_SHORT.get(month_name)
    if not month:
        warnings.append(f"[EUROANAESTHESIA] Unknown EN month abbrev: {month_name}")
        return []

    start_date = _ymd(year, month, d1)
    end_date = _ymd(year, month, d2)

    return [
        {
            "series": "EUROANAESTHESIA",
            "year": year,
            "type": "congress",
            "start_date": start_date,
            "end_date": end_date,
            "location": "Rotterdam, The Netherlands",
            "link": "https://euroanaesthesia.org/2026/",
            "priority": 8,
            "title": {
                "en": "Euroanaesthesia 2026 — ESAIC Annual Congress",
                "pt": "Euroanaesthesia 2026 — Congresso anual da ESAIC",
            },
            "source": "scraped",
        }
    ]


def _from_sba_events(url: str, warnings: List[str]) -> List[Dict[str, Any]]:
    """
    SBA 'Congressos e eventos' snippet: :contentReference[oaicite:8]{index=8}

      'Euroanaesthesia 2026
       6 a 8 de junho
       Rotterdam - Holanda'
    """
    html = _fetch(url)
    text = re.sub(r"\s+", " ", html, flags=re.DOTALL).lower()

    block_match = re.search(r"euroanaesthesia\s*2026[^<]{0,160}", text)
    if not block_match:
        warnings.append("[EUROANAESTHESIA] Could not find 'Euroanaesthesia 2026' block on SBA page.")
        return []

    block = block_match.group(0)

    m = re.search(
        r"(\d{1,2})\s*a\s*(\d{1,2})\s*de\s*([a-zç]+)",
        block,
    )
    if not m:
        warnings.append("[EUROANAESTHESIA] Could not parse PT date range '6 a 8 de junho' on SBA page.")
        return []

    d1 = int(m.group(1))
    d2 = int(m.group(2))
    month_name = m.group(3).replace("ç", "c")
    month = MONTHS_PT.get(month_name)
    if not month:
        warnings.append(f"[EUROANAESTHESIA] Unknown PT month name: {month_name}")
        return []

    year = 2026  # inferred from context
    start_date = _ymd(year, month, d1)
    end_date = _ymd(year, month, d2)

    return [
        {
            "series": "EUROANAESTHESIA",
            "year": year,
            "type": "congress",
            "start_date": start_date,
            "end_date": end_date,
            "location": "Rotterdam, The Netherlands",
            "link": "https://euroanaesthesia.org/2026/",
            "priority": 7,
            "title": {
                "en": "Euroanaesthesia 2026 — ESAIC Annual Congress",
                "pt": "Euroanaesthesia 2026 — Congresso anual da ESAIC",
            },
            "source": "scraped",
        }
    ]


def scrape_euroanaesthesia(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    urls = cfg.get("urls") or []
    if not urls:
        return [], ["[EUROANAESTHESIA] No URLs configured in sources.json."]

    esaic_url = next((u for u in urls if "esaic.org" in u), None)
    sba_url = next((u for u in urls if "sbahq.org" in u), None)

    events: List[Dict[str, Any]] = []

    if esaic_url:
        try:
            events = _from_esaic_home(esaic_url, warnings)
        except Exception as e:  # pragma: no cover
            warnings.append(f"[EUROANAESTHESIA] Error scraping ESAIC homepage: {e}")

    if not events and sba_url:
        try:
            events = _from_sba_events(sba_url, warnings)
        except Exception as e:  # pragma: no cover
            warnings.append(f"[EUROANAESTHESIA] Error scraping SBA 'Congressos e eventos': {e}")

    if not events and not warnings:
        warnings.append("[EUROANAESTHESIA] No events found from any configured URL.")

    return events, warnings
