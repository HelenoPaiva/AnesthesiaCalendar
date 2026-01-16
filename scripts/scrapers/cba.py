# scripts/scrapers/cba.py

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple
from urllib.request import Request, urlopen


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
    with urlopen(req, timeout=20) as resp:  # nosec - GitHub Actions is sandboxed
        raw = resp.read()
    return raw.decode("utf-8", errors="ignore")


def _ymd(y: int, m: int, d: int) -> str:
    return f"{y:04d}-{m:02d}-{d:02d}"


def _scrape_from_saesp(url: str, warnings: List[str]) -> List[Dict[str, Any]]:
    """
    SAESP 'Eventos apoiados' snippet:

      '26 a 29 de novembro de 2026 - Fortaleza, CE. Clique aqui para mais informações'
      under '71º CBA - Congresso Brasileiro de Anestesiologia' :contentReference[oaicite:2]{index=2}
    """
    html = _fetch(url)
    text = re.sub(r"\s+", " ", html, flags=re.DOTALL).lower()

    # Narrow region around "71º CBA" to avoid matching random date ranges.
    block_match = re.search(r"71º\s*cba[^<]{0,300}", text)
    haystack = block_match.group(0) if block_match else text

    m = re.search(
        r"(\d{1,2})\s*a\s*(\d{1,2})\s*de\s*([a-zç]+)\s*de\s*(20\d{2})",
        haystack,
    )
    if not m:
        warnings.append("[CBA] Could not find '26 a 29 de novembro de 2026' date range on SAESP page.")
        return []

    d1 = int(m.group(1))
    d2 = int(m.group(2))
    month_name = m.group(3).replace("ç", "c")
    year = int(m.group(4))

    month = MONTHS_PT.get(month_name)
    if not month:
        warnings.append(f"[CBA] Unknown PT month name: {month_name}")
        return []

    start_date = _ymd(year, month, d1)
    end_date = _ymd(year, month, d2)

    # Location appears as "Fortaleza, CE"; we normalise.
    loc = "Fortaleza, CE, Brazil"

    return [
        {
            "series": "CBA",
            "year": year,
            "type": "congress",
            "start_date": start_date,
            "end_date": end_date,
            "location": loc,
            "link": url,
            "priority": 10,
            "title": {
                "en": f"CBA {year} — Brazilian Congress of Anaesthesiology",
                "pt": f"CBA {year} — Congresso Brasileiro de Anestesiologia",
            },
            "source": "scraped",
        }
    ]


def _scrape_from_levitatur(url: str, warnings: List[str]) -> List[Dict[str, Any]]:
    """
    Fallback if SAESP changes. Levitatur snippet: :contentReference[oaicite:3]{index=3}

      '11/26 to 11/29/2026
       Centro de Eventos do Ceará (CEC)'

    We interpret 11/26 as month/day (US style) but the month is 11 (November),
    which we already know matches CBA.
    """
    html = _fetch(url)
    text = re.sub(r"\s+", " ", html, flags=re.DOTALL)

    m = re.search(
        r"(\d{1,2})/(\d{1,2})\s*to\s*(\d{1,2})/(\d{1,2})/(\d{4})",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        warnings.append("[CBA] Could not parse date range on Levitatur page.")
        return []

    month = int(m.group(1))
    day1 = int(m.group(2))
    day2 = int(m.group(4))
    year = int(m.group(5))

    start_date = _ymd(year, month, day1)
    end_date = _ymd(year, month, day2)

    loc = "Centro de Eventos do Ceará, Fortaleza, Brazil"

    return [
        {
            "series": "CBA",
            "year": year,
            "type": "congress",
            "start_date": start_date,
            "end_date": end_date,
            "location": loc,
            "link": url,
            "priority": 9,
            "title": {
                "en": f"CBA {year} — Brazilian Congress of Anaesthesiology",
                "pt": f"CBA {year} — Congresso Brasileiro de Anestesiologia",
            },
            "source": "scraped",
        }
    ]


def scrape_cba(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    urls = cfg.get("urls") or []
    if not urls:
        return [], ["[CBA] No URLs configured in sources.json."]

    events: List[Dict[str, Any]] = []

    # Prefer SAESP; use Levitatur only if SAESP fails.
    saesp_url = next((u for u in urls if "saesp.org.br" in u), None)
    levita_url = next((u for u in urls if "levitatur.com.br" in u), None)

    if saesp_url:
        try:
            events = _scrape_from_saesp(saesp_url, warnings)
        except Exception as e:  # pragma: no cover - network
            warnings.append(f"[CBA] Error scraping SAESP eventos-apoiados: {e}")

    if not events and levita_url:
        try:
            events = _scrape_from_levitatur(levita_url, warnings)
        except Exception as e:  # pragma: no cover
            warnings.append(f"[CBA] Error scraping Levitatur CBA page: {e}")

    if not events and not warnings:
        warnings.append("[CBA] No events found from any configured URL.")

    return events, warnings
