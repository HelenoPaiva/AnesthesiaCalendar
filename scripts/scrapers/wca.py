# scripts/scrapers/wca.py

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple
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


def _ymd(y: int, m: int, d: int) -> str:
    return f"{y:04d}-{m:02d}-{d:02d}"


def scrape_wca(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Scrape WCA 2026 key dates from wcacongress.org.

    Produces:
      - congress (start_date, end_date)
      - abstract_deadline
      - early_bird_deadline
      - registration_deadline
    """
    warnings: List[str] = []
    urls = cfg.get("urls") or []
    if not urls:
        return [], ["[WCA] No URLs configured in sources.json."]

    base_url = urls[0]

    try:
        html = _fetch(base_url)
    except Exception as e:  # pragma: no cover - network
        return [], [f"[WCA] Failed to fetch {base_url}: {e}"]

    # Flatten whitespace
    text = re.sub(r"\s+", " ", html, flags=re.DOTALL)

    # ------------------------------------------------------------------
    # Locate the "Key Dates" block, which looks like:
    #
    #   Key Dates
    #   30 September 2025 – Abstract Submission Deadline
    #   21 January 2026 – Early Bird Registration Deadline
    #   31 March 2026 – Regular Registration Deadline
    #   15-19 April 2026 – Congress
    #   Subscribe to the WCA mailing list
    # ------------------------------------------------------------------
    m_block = re.search(
        r"Key Dates(.*?)(Subscribe to the WCA mailing list|#WCA2026)",
        text,
        flags=re.IGNORECASE,
    )
    if not m_block:
        warnings.append("[WCA] Could not locate 'Key Dates' block on wcacongress.org.")
        return [], warnings

    block = m_block.group(1)
    events: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # 1) Congress dates: "15-19 April 2026 – Congress"
    # ------------------------------------------------------------------
    m_cong = re.search(
        r"(\d{1,2})\s*[-–]\s*(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})\s*[–\-]\s*Congress",
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
            warnings.append(f"[WCA] Unknown month in congress date: '{month_name}'")
        else:
            congress_year = year
            start_date = _ymd(year, mnum, d1)
            end_date = _ymd(year, mnum, d2)

            events.append(
                {
                    "series": "WCA",
                    "year": year,
                    "type": "congress",
                    "start_date": start_date,
                    "end_date": end_date,
                    "location": "Marrakech, Morocco",
                    "link": base_url,
                    "priority": 9,
                    "title": {
                        "en": "WCA 2026 — World Congress of Anaesthesiologists",
                        "pt": "WCA 2026 — Congresso Mundial de Anestesiologia",
                    },
                    "source": "scraped",
                }
            )
    else:
        warnings.append("[WCA] Could not find '15-19 April 2026 – Congress' in Key Dates block.")

    # ------------------------------------------------------------------
    # 2) Individual deadlines: lines like
    #    '30 September 2025 – Abstract Submission Deadline'
    #
    # We only match single-day entries, not the range we already used.
    # ------------------------------------------------------------------
    line_pattern = re.compile(
        r"(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})\s*[–\-]\s*([^0-9]+?)(?=(\d{1,2}\s+[A-Za-z]+\s+20\d{2}\s*[–\-]|15-19\s+April\s+20\d{2}\s*[–\-]\s*Congress|$))",
        re.IGNORECASE,
    )

    for m in line_pattern.finditer(block):
        day = int(m.group(1))
        month_name = m.group(2).lower()
        year = int(m.group(3))
        label = m.group(4).strip()

        month = MONTHS_EN.get(month_name)
        if not month:
            warnings.append(f"[WCA] Unknown month in key date: '{month_name}'")
            continue

        date_ymd = _ymd(year, month, day)
        label_lower = label.lower()

        if "abstract" in label_lower:
            etype = "abstract_deadline"
            title_en = "WCA 2026 — Abstract submission deadline"
            title_pt = "WCA 2026 — Prazo final de submissão de resumos"
        elif "early bird" in label_lower:
            etype = "early_bird_deadline"
            title_en = "WCA 2026 — Early-bird registration deadline"
            title_pt = "WCA 2026 — Prazo de inscrição early-bird"
        elif "regular registration" in label_lower:
            etype = "registration_deadline"
            title_en = "WCA 2026 — Regular registration deadline"
            title_pt = "WCA 2026 — Prazo de inscrição regular"
        else:
            # Unknown label — skip rather than guessing.
            continue

        year_for_event = congress_year or year

        events.append(
            {
                "series": "WCA",
                "year": year_for_event,
                "type": etype,
                "date": date_ymd,
                "location": "Marrakech, Morocco",
                "link": base_url,
                "priority": 8,
                "title": {"en": title_en, "pt": title_pt},
                "source": "scraped",
            }
        )

    if not events and not warnings:
        warnings.append("[WCA] No events produced from wcacongress.org (regex likely needs update).")

    return events, warnings