# scripts/scrapers/copa.py
#
# COPA SAESP – Paulista Congress of Anesthesiology
# Scrapes the official "temas-livres" page for:
#   - Congress date range  (e.g. "23 a 26 de abril de 2026")
#   - Abstract deadline    (e.g. "Submeta seu trabalho até 30 de janeiro de 2026")
#   - Registration dates   (e.g. "Até 08/02/26", "Até 12/04/26")
#
# Design principles:
#   * TRUST ONLY VISIBLE PT-BR TEXT, NEVER SEO/META TAGS (they are wrong).
#   * No automatic year window probing; we only scrape the URLs given
#     in data/sources.json.
#   * Year-agnostic: patterns don't hard-code 2026, so when you switch
#     the URL to copa2027.saesp.org.br/temas-livres/ it should still work
#     if they keep the same structure.

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple
from urllib.request import Request, urlopen

# PT-BR month names -> month number
MONTHS_PT = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "marco": 3,   # just in case accents vanish
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
    """HTTP GET with a realistic User-Agent."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; AnesthesiaCalendarBot/1.0; "
            "+https://helenopaiva.github.io/AnesthesiaCalendar/)"
        )
    }
    req = Request(url, headers=headers)
    with urlopen(req, timeout=20) as resp:  # nosec - runs in GitHub Actions sandbox
        raw = resp.read()
    return raw.decode("utf-8", errors="ignore")


def _ymd(y: int, m: int, d: int) -> str:
    return f"{y:04d}-{m:02d}-{d:02d}"


def _parse_pt_range(text: str) -> Tuple[int | None, int | None, int | None, int | None, str | None]:
    """
    Parse a PT-BR date range like:
      "23 a 26 de abril de 2026"
    Returns (year, month, day_start, day_end, snippet) or (None, ...).
    """
    m = re.search(
        r"(\d{1,2})\s*a\s*(\d{1,2})\s*de\s+([A-Za-zçãéôíúáõ]+)\s+de\s+(20\d{2})",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        return None, None, None, None, None

    d1 = int(m.group(1))
    d2 = int(m.group(2))
    month_name = m.group(3).lower()
    year = int(m.group(4))

    month = MONTHS_PT.get(month_name)
    if not month:
        return year, None, d1, d2, m.group(0)

    return year, month, d1, d2, m.group(0)


def _parse_pt_single(text: str, pattern: str) -> Tuple[int | None, int | None, int | None, str | None]:
    """
    Generic helper to parse PT-BR single dates like:
      "Submeta seu trabalho até 30 de janeiro de 2026"
    'pattern' should have one capture group with the date string.
    """
    m = re.search(pattern, text, flags=re.IGNORECASE)
    if not m:
        return None, None, None, None

    date_str = m.group(1).strip()
    dm = re.match(r"(\d{1,2})\s+de\s+([A-Za-zçãéôíúáõ]+)\s+de\s+(20\d{2})", date_str, flags=re.IGNORECASE)
    if not dm:
        return None, None, None, date_str

    day = int(dm.group(1))
    month_name = dm.group(2).lower()
    year = int(dm.group(3))

    month = MONTHS_PT.get(month_name)
    if not month:
        return year, None, day, date_str

    return year, month, day, date_str


def _scrape_temasinlivres(url: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    events: List[Dict[str, Any]] = []

    try:
        html = _fetch(url)
    except Exception as e:  # pragma: no cover - network
        return [], [f"[COPA] Failed to fetch {url}: {e} (v2026-01-19j)"]

    # Flatten whitespace so regex can span lines and tags
    text = re.sub(r"\s+", " ", html, flags=re.DOTALL)

    # Derive a nicer base link for the congress (root site for that year)
    # e.g. https://copa2026.saesp.org.br/temas-livres/ -> https://copa2026.saesp.org.br/
    m_base = re.match(r"^(https?://[^/]+/)", url)
    base_link = m_base.group(1) if m_base else url

    # ----------------- 1) Congress date range -----------------

    year, month, d1, d2, snippet = _parse_pt_range(text)
    congress_found = False

    if year and month and d1 and d2:
        congress_found = True

        start_date = _ymd(year, month, d1)
        end_date = _ymd(year, month, d2)

        events.append(
            {
                "series": "COPA",
                "year": year,
                "type": "congress",
                "start_date": start_date,
                "end_date": end_date,
                "location": "Transamerica Expo Center, São Paulo, Brazil",
                "link": base_link,
                "priority": 8,
                "title": {
                    "en": f"COPA {year} — Paulista Congress of Anesthesiology",
                    "pt": f"COPA {year} — Congresso Paulista de Anestesiologia",
                },
                "evidence": {
                    "url": url,
                    "snippet": snippet,
                    "field": "congress_range_pt",
                },
                "source": "scraped",
            }
        )
    else:
        warnings.append(
            "[COPA] Could not parse congress date range like '23 a 26 de abril de 20XX' "
            f"on {url}. (v2026-01-19j)"
        )

    # Fallback congress_year for deadlines (if parsing failed we try to rescue year from URL)
    congress_year = year
    if not congress_year:
        m_year = re.search(r"copa(20\d{2})", url)
        if m_year:
            congress_year = int(m_year.group(1))

    # ----------------- 2) Abstract submission deadline -----------------

    # Pattern captures just the date part after "Submeta seu trabalho até "
    abs_year, abs_month, abs_day, abs_raw = _parse_pt_single(
        text,
        r"Submeta seu trabalho até\s+(\d{1,2}\s+de\s+[A-Za-zçãéôíúáõ]+\s+de\s+20\d{2})",
    )

    if abs_year and abs_month and abs_day:
        date_ymd = _ymd(abs_year, abs_month, abs_day)
        y_for_event = congress_year or abs_year

        events.append(
            {
                "series": "COPA",
                "year": y_for_event,
                "type": "abstract_deadline",
                "date": date_ymd,
                "location": "Transamerica Expo Center, São Paulo, Brazil",
                "link": url,
                "priority": 8,
                "title": {
                    "en": f"COPA {y_for_event} — Abstract submission deadline",
                    "pt": f"COPA {y_for_event} — Prazo para submissão de temas livres",
                },
                "evidence": {
                    "url": url,
                    "snippet": abs_raw,
                    "field": "abstract_deadline_pt",
                },
                "source": "scraped",
            }
        )
    else:
        warnings.append(
            f"[COPA] Could not parse abstract deadline phrase "
            f\"'Submeta seu trabalho até ...' on {url}. (v2026-01-19j)\"
        )

    # ----------------- 3) Registration deadlines (table 'Até 08/02/26', etc.) -----------------

    # Grab all distinct "Até dd/mm/yy" occurrences
    regs: List[str] = []
    for m in re.finditer(r"Até\s+(\d{2})/(\d{2})/(\d{2})", text):
        dd = int(m.group(1))
        mm = int(m.group(2))
        yy2 = int(m.group(3))
        yy = 2000 + yy2  # e.g. 26 -> 2026
        iso = _ymd(yy, mm, dd)
        if iso not in regs:
            regs.append(iso)

    regs.sort()

    # Map first to early-bird, second to general registration, others to "other_deadline"
    labels = []
    if regs:
        labels.append(("early_bird_deadline", "Early registration deadline", "Prazo de inscrição antecipada"))
    if len(regs) >= 2:
        labels.append(("registration_deadline", "Registration deadline", "Prazo de inscrição"))
    if len(regs) > 2:
        for _ in regs[2:]:
            labels.append(("other_deadline", "Registration deadline", "Prazo de inscrição"))

    year_for_regs = congress_year or (abs_year if abs_year else None)

    for iso, (etype, tail_en, tail_pt) in zip(regs, labels):
        y_for_event = year_for_regs or int(iso[:4])
        events.append(
            {
                "series": "COPA",
                "year": y_for_event,
                "type": etype,
                "date": iso,
                "location": "Transamerica Expo Center, São Paulo, Brazil",
                "link": url,
                "priority": 7,
                "title": {
                    "en": f"COPA {y_for_event} — {tail_en}",
                    "pt": f"COPA {y_for_event} — {tail_pt}",
                },
                "evidence": {
                    "url": url,
                    "snippet": f"Até {iso[8:10]}/{iso[5:7]}/{str(y_for_event)[2:]}",
                    "field": "registration_table_pt",
                },
                "source": "scraped",
            }
        )

    warnings.append(
        f"[COPA DEBUG] url={url} congress_found={congress_found} "
        f"abstract_found={bool(abs_year and abs_month and abs_day)} "
        f"reg_dates={regs} (v2026-01-19j)"
    )

    return events, warnings


def scrape_copa(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Entry point for the orchestrator.

    cfg in data/sources.json for COPA looks like:
      {
        "series": "COPA",
        "priority": 7,
        "urls": [
          "https://copa2026.saesp.org.br/temas-livres/"
        ]
      }

    We DO NOT auto-probe other years. If you want the 2027 edition,
    just update data/sources.json with the new /temas-livres/ URL.
    """
    urls = cfg.get("urls") or []
    if not urls:
        return [], ["[COPA] No URLs configured in data/sources.json. (v2026-01-19j)"]

    all_events: List[Dict[str, Any]] = []
    all_warnings: List[str] = []

    for url in urls:
        ev, w = _scrape_temasinlivres(url)
        all_events.extend(ev)
        all_warnings.extend(w)

    if not all_events:
        all_warnings.append(
            "[COPA] No events produced from configured COPA URLs "
            "(site structure may have changed). (v2026-01-19j)"
        )

    all_warnings.append("[COPA DEBUG] scraper version v2026-01-19j")
    return all_events, all_warnings
