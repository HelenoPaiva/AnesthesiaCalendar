# scripts/scrapers/copa.py

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple
from urllib.request import Request, urlopen


SCRAPER_VERSION = "v2026-01-19e"

# PT-BR month names -> month numbers
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
    with urlopen(req, timeout=20) as resp:  # nosec - GitHub Actions sandbox
        raw = resp.read()
    return raw.decode("utf-8", errors="ignore")


def _ymd(y: int, m: int, d: int) -> str:
    return f"{y:04d}-{m:02d}-{d:02d}"


def _parse_pt_range(text: str) -> Tuple[str | None, str | None, int | None]:
    """
    Parse a PT-BR date range like:
      '23 a 26 de abril de 2026'
    Returns (start_iso, end_iso, year)
    """
    m = re.search(
        r"(\d{1,2})\s*a\s*(\d{1,2})\s*de\s*([A-Za-zçãé]+)\s*de\s*(20\d{2})",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        return None, None, None

    d1 = int(m.group(1))
    d2 = int(m.group(2))
    month_name_raw = m.group(3).strip()
    year = int(m.group(4))

    month_name = month_name_raw.lower()
    month = MONTHS_PT.get(month_name)
    if not month:
        return None, None, None

    start_iso = _ymd(year, month, d1)
    end_iso = _ymd(year, month, d2)
    return start_iso, end_iso, year


def _parse_pt_single_date(text: str) -> str | None:
    """
    Parse a single PT-BR date like:
      '30 de janeiro de 2026'
    Returns 'YYYY-MM-DD' or None.
    """
    m = re.search(
        r"(\d{1,2})\s+de\s+([A-Za-zçãé]+)\s+de\s*(20\d{2})",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        return None

    d = int(m.group(1))
    month_name_raw = m.group(2).strip()
    year = int(m.group(3))

    month = MONTHS_PT.get(month_name_raw.lower())
    if not month:
        return None

    return _ymd(year, month, d)


def _parse_br_ddmmyy(date_str: str) -> str | None:
    """
    Parse BR-style 'dd/mm/yy' like '08/02/26' into 'YYYY-MM-DD'.
    We assume yy in 2000-2099.
    """
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2})", date_str.strip())
    if not m:
        return None
    d = int(m.group(1))
    mnum = int(m.group(2))
    yy = int(m.group(3))
    year = 2000 + yy
    return _ymd(year, mnum, d)


def _scrape_copa_temas_livres(url: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Scrape COPA from the PT-BR 'temas-livres' page.

    Example snippets:

      - Congress range:
        <span class="elementor-icon-list-text">23 a 26 de abril de 2026</span>

      - Abstract deadline:
        <span class="elementor-button-text">Atenção! Submeta seu trabalho até 30 de janeiro de 2026</span>

      - Registration table header (tabela-copa):
        <th>Até 08/02/26</th>
        <th>Até 12/04/26</th>

    We deliberately use only this PT-BR page to avoid duplicates from the EN site.
    """
    warnings: List[str] = []
    events: List[Dict[str, Any]] = []

    try:
        html = _fetch(url)
    except Exception as e:  # pragma: no cover - network
        return [], [f"[COPA] Failed to fetch {url}: {e} ({SCRAPER_VERSION})"]

    # Flatten whitespace
    text = re.sub(r"\s+", " ", html, flags=re.DOTALL)

    # ---------------------- Congress dates ----------------------
    # Look for '23 a 26 de abril de 2026' style pattern
    start_iso, end_iso, year = _parse_pt_range(text)
    congress_found = start_iso is not None and end_iso is not None and year is not None

    if congress_found:
        events.append(
            {
                "series": "COPA",
                "year": year,
                "type": "congress",
                "start_date": start_iso,
                "end_date": end_iso,
                # COPA is organized by SAESP; venue city is São Paulo.
                "location": "São Paulo - SP",
                "link": url,
                "priority": 9,
                "title": {
                    "en": f"COPA {year} — Paulista Congress of Anesthesiology",
                    "pt": f"COPA {year} — Congresso Paulista de Anestesiologia",
                },
                "evidence": {
                    "url": url,
                    "snippet": f"{start_iso}..{end_iso}",
                    "field": "congress_range",
                },
                "source": "scraped",
            }
        )
    else:
        warnings.append(f"[COPA] Could not find congress date range on {url}. ({SCRAPER_VERSION})")

    # ---------------------- Abstract deadline ----------------------
    # Based on: "Atenção! Submeta seu trabalho até 30 de janeiro de 2026"
    m_abs_block = re.search(
        r"(Aten[cç][aã]o!.*?Submeta seu trabalho.*?até\s+[^<]+)",
        text,
        flags=re.IGNORECASE,
    )
    abstract_date_iso = None
    if m_abs_block:
        block = m_abs_block.group(1)
        abstract_date_iso = _parse_pt_single_date(block)
        if abstract_date_iso and year:
            events.append(
                {
                    "series": "COPA",
                    "year": year,
                    "type": "abstract_deadline",
                    "date": abstract_date_iso,
                    "location": "São Paulo - SP",
                    "link": url,
                    "priority": 9,
                    "title": {
                        "en": f"COPA {year} — Abstract submission deadline",
                        "pt": f"COPA {year} — Prazo final para submissão de trabalhos",
                    },
                    "evidence": {
                        "url": url,
                        "snippet": block,
                        "field": "abstract_deadline_block",
                    },
                    "source": "scraped",
                }
            )
        else:
            warnings.append(
                f"[COPA] Found abstract block but could not parse date/year on {url}. ({SCRAPER_VERSION})"
            )
    else:
        warnings.append(
            f"[COPA] Could not find 'Submeta seu trabalho' abstract deadline block on {url}. ({SCRAPER_VERSION})"
        )

    # ---------------------- Registration deadlines ----------------------
    # Table header from 'tabela-copa':
    #
    #   <th>Até 08/02/26</th>
    #   <th>Até 12/04/26</th>
    #   <th>No local</th>
    #
    # We'll treat the first as "early_bird_deadline" and the second as "registration_deadline".
    header_block_match = re.search(r"<table[^>]*class=\"tabela-copa\".*?</table>", text, flags=re.IGNORECASE)
    if header_block_match:
        header_block = header_block_match.group(0)
        # Find "Até dd/mm/yy"
        dates_br = re.findall(r"Até\s+(\d{1,2}/\d{1,2}/\d{2})", header_block)
        reg_dates_iso: List[str] = []
        for brd in dates_br:
            iso = _parse_br_ddmmyy(brd)
            if iso:
                reg_dates_iso.append(iso)

        # Deduplicate and sort just in case
        reg_dates_iso = sorted(set(reg_dates_iso))

        if reg_dates_iso and year:
            # First date -> early bird
            first = reg_dates_iso[0]
            events.append(
                {
                    "series": "COPA",
                    "year": year,
                    "type": "early_bird_deadline",
                    "date": first,
                    "location": "São Paulo - SP",
                    "link": url,
                    "priority": 8,
                    "title": {
                        "en": f"COPA {year} — Early registration deadline",
                        "pt": f"COPA {year} — Prazo de inscrição antecipada",
                    },
                    "evidence": {
                        "url": url,
                        "snippet": header_block[:200],
                        "field": "tabela_copa_header",
                    },
                    "source": "scraped",
                }
            )

            if len(reg_dates_iso) > 1:
                # Second date -> normal/late registration
                second = reg_dates_iso[1]
                events.append(
                    {
                        "series": "COPA",
                        "year": year,
                        "type": "registration_deadline",
                        "date": second,
                        "location": "São Paulo - SP",
                        "link": url,
                        "priority": 8,
                        "title": {
                            "en": f"COPA {year} — Registration deadline",
                            "pt": f"COPA {year} — Prazo para inscrição",
                        },
                        "evidence": {
                            "url": url,
                            "snippet": header_block[:200],
                            "field": "tabela_copa_header",
                        },
                        "source": "scraped",
                    }
                )
        else:
            warnings.append(
                f"[COPA] Could not parse registration dates from tabela-copa on {url}. ({SCRAPER_VERSION})"
            )
    else:
        warnings.append(
            f"[COPA] Could not find tabela-copa block on {url}. ({SCRAPER_VERSION})"
        )

    return events, warnings


def scrape_copa(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Entry point for COPA scraper.

    Strategy:
      - Prefer a PT-BR 'temas-livres' URL if present in sources.json.
      - Otherwise, fall back to the first configured URL.
      - Scrape only ONE page to avoid duplicate abstract deadlines
        (we do not hit the EN site to keep things single-source-of-truth).
    """
    warnings: List[str] = []

    urls = cfg.get("urls") or []
    if not urls:
        return [], [f"[COPA] No URLs configured in sources.json. ({SCRAPER_VERSION})"]

    # Prefer temas-livres page if present
    target_url = None
    for u in urls:
        if "temas-livres" in u:
            target_url = u
            break
    if not target_url:
        target_url = urls[0]

    events, w = _scrape_copa_temas_livres(target_url)
    warnings.extend(w)

    # Final debug marker so we know scraper ran
    warnings.append(
        f"[COPA DEBUG] target_url={target_url} events={len(events)} ({SCRAPER_VERSION})"
    )
    warnings.append(f"[COPA DEBUG] scraper version {SCRAPER_VERSION}")

    return events, warnings
