# scripts/scrapers/copa.py
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Tuple
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


# Portuguese month names
MONTHS_PT = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3, "março": 3,
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
    with urlopen(req, timeout=20) as resp:  # nosec - GitHub Actions sandbox
        raw = resp.read()
    return raw.decode("utf-8", errors="ignore")


def _ymd(y: int, m: int, d: int) -> str:
    return f"{y:04d}-{m:02d}-{d:02d}"


def _parse_pt_range(date_str: str) -> Tuple[int | None, int | None, int | None, int | None]:
    """
    Parse '23 a 26 de abril de 2026' style ranges.

    Returns (year, month, day_start, day_end) or (None, None, None, None).
    """
    m = re.search(
        r"(\d{1,2})\s*(?:a|à|–|-)\s*(\d{1,2})\s+de\s+([A-Za-zçãéíóúãõ]+)\s+de\s+(20\d{2})",
        date_str,
        flags=re.IGNORECASE,
    )
    if not m:
        return None, None, None, None

    d1 = int(m.group(1))
    d2 = int(m.group(2))
    month_name = m.group(3).lower()
    year = int(m.group(4))

    month = MONTHS_PT.get(month_name)
    if not month:
        return None, None, None, None

    return year, month, d1, d2


def _parse_pt_date(date_str: str) -> Tuple[int | None, int | None, int | None]:
    """
    Parse '30 de janeiro de 2026' style dates.

    Returns (year, month, day) or (None, None, None).
    """
    m = re.search(
        r"(\d{1,2})\s+de\s+([A-Za-zçãéíóúãõ]+)\s+de\s+(20\d{2})",
        date_str,
        flags=re.IGNORECASE,
    )
    if not m:
        return None, None, None

    d = int(m.group(1))
    month_name = m.group(2).lower()
    year = int(m.group(3))

    month = MONTHS_PT.get(month_name)
    if not month:
        return None, None, None

    return year, month, d


def scrape_copa(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Scraper for COPA (Congresso Paulista de Anestesiologia).

    IMPORTANT:
      - Only uses the visible PT-BR text on the 'temas-livres' page.
      - Ignores SEO/meta tags completely (they are wrong for 2026).
      - Rejects any dates whose year is < current UTC year.
    """
    warnings: List[str] = []
    urls = cfg.get("urls") or []
    if not urls:
        return [], ["[COPA] No URLs configured in sources.json. (v2026-01-19j)"]

    target_url = urls[0]

    try:
        html = _fetch(target_url)
    except (HTTPError, URLError) as e:
        return [], [f"[COPA] Failed to fetch {target_url}: {e} (v2026-01-19j)"]
    except Exception as e:  # pragma: no cover - network
        return [], [f"[COPA] Failed to fetch {target_url}: {e} (v2026-01-19j)"]

    # Flatten whitespace so patterns can span tags/newlines
    text = re.sub(r"\s+", " ", html, flags=re.DOTALL)

    now_year = datetime.utcnow().year
    events: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # 1) Congress date range — from visible PT text:
    #    "23 a 26 de abril de 2026"
    # ------------------------------------------------------------------
    range_re = re.compile(
        r"(\d{1,2}\s*(?:a|à|–|-)\s*\d{1,2}\s+de\s+[A-Za-zçãéíóúãõ]+\s+de\s+20\d{2})",
        re.IGNORECASE,
    )
    congress_found = False
    congress_year: int | None = None

    range_candidates: List[Tuple[str, int, int, int, int]] = []

    for m in range_re.finditer(text):
        raw = m.group(1)
        y, month, d1, d2 = _parse_pt_range(raw)
        if not y or not month or not d1 or not d2:
            continue
        # Auto-refuse any past year (e.g., 2025) as requested
        if y < now_year:
            continue
        range_candidates.append((raw, y, month, d1, d2))

    if range_candidates:
        # Choose the earliest start date among candidate future ranges
        def _sort_key(item: Tuple[str, int, int, int, int]) -> str:
            _, y, m, d1, _ = item
            return _ymd(y, m, d1)

        range_candidates.sort(key=_sort_key)
        raw, y, month, d1, d2 = range_candidates[0]
        start_date = _ymd(y, month, d1)
        end_date = _ymd(y, month, d2)

        events.append(
            {
                "series": "COPA",
                "year": y,
                "type": "congress",
                "start_date": start_date,
                "end_date": end_date,
                "location": "Transamerica Expo Center, São Paulo, Brazil",
                "link": target_url,
                "priority": 8,
                "title": {
                    "en": f"COPA {y} — Paulista Congress of Anesthesiology",
                    "pt": f"COPA {y} — Congresso Paulista de Anestesiologia",
                },
                "evidence": {
                    "url": target_url,
                    "snippet": raw,
                    "field": "congress_range_pt",
                },
                "source": "scraped",
            }
        )
        congress_found = True
        congress_year = y
    else:
        warnings.append(
            f"[COPA] Could not locate congress date range like '23 a 26 de abril de 20XX' on {target_url}. (v2026-01-19j)"
        )

    # ------------------------------------------------------------------
    # 2) Abstract deadline — from banner:
    #    "Atenção! Submeta seu trabalho até 30 de janeiro de 2026"
    # ------------------------------------------------------------------
    abstract_found = False
    abs_re = re.compile(
        r"Submeta\s+seu\s+trabalho\s+até\s+(\d{1,2}\s+de\s+[A-Za-zçãéíóúãõ]+\s+de\s+20\d{2})",
        re.IGNORECASE,
    )
    m_abs = abs_re.search(text)

    if m_abs:
        raw = m_abs.group(0)
        date_str = m_abs.group(1)
        y, month, d = _parse_pt_date(date_str)
        if y and month and d:
            if y >= now_year:
                date_iso = _ymd(y, month, d)
                year_for_label = congress_year or y
                events.append(
                    {
                        "series": "COPA",
                        "year": year_for_label,
                        "type": "abstract_deadline",
                        "date": date_iso,
                        "location": "Transamerica Expo Center, São Paulo, Brazil",
                        "link": target_url,
                        "priority": 8,
                        "title": {
                            "en": f"COPA {year_for_label} — Abstract submission deadline",
                            "pt": f"COPA {year_for_label} — Prazo para submissão de temas livres",
                        },
                        "evidence": {
                            "url": target_url,
                            "snippet": raw,
                            "field": "abstract_deadline_pt",
                        },
                        "source": "scraped",
                    }
                )
                abstract_found = True
    else:
        warnings.append(
            f"[COPA] Could not locate 'Submeta seu trabalho até ...' abstract deadline on {target_url}. (v2026-01-19j)"
        )

    # ------------------------------------------------------------------
    # Debug markers for ledger
    # ------------------------------------------------------------------
    warnings.append(
        f"[COPA DEBUG] url={target_url} congress_found={congress_found} abstract_found={abstract_found} (v2026-01-19j)"
    )
    warnings.append("[COPA DEBUG] scraper version v2026-01-19j")

    if not events:
        warnings.append(
            "[COPA] No events produced from temas-livres page (check HTML structure). (v2026-01-19j)"
        )

    return events, warnings
