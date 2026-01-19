# scripts/scrapers/copa.py

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
    """
    HTTP GET with a reasonable User-Agent, same pattern as the other scrapers.
    """
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


def scrape_copa(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Scrape COPA SAESP congress info.

    Design goals:
    - Year-agnostic in the *code* (no year hard-coded here).
    - Relies on the page showing a date range in the form:
          'April 23–26, 2026'
      i.e.  Month DD–DD, YYYY  (EN month name, en-dash or hyphen).
    - Location is taken from the presence of "Transamerica Expo Center"
      in the page text, and mapped to a human-readable city string.

    Output:
      * Exactly one "congress" event per configured URL that yields a match.
        (In practice you will configure a single URL for the current edition,
         e.g. https://copa2026.saesp.org.br/en/)

    Does NOT currently scrape individual deadlines; only the congress dates.
    """
    warnings: List[str] = []
    urls = cfg.get("urls") or []
    if not urls:
        return [], ["[COPA] No URLs configured in sources.json. (v2026-01-19a)"]

    events: List[Dict[str, Any]] = []

    # Regex for a *single* congress date range:
    #   Month  DD–DD, YYYY
    #   Example: "April 23–26, 2026"
    range_pattern = re.compile(
        r"([A-Za-z]+)\s+(\d{1,2})\s*[-–]\s*(\d{1,2}),?\s+(20\d{2})",
        re.IGNORECASE,
    )

    for base_url in urls:
        try:
            html = _fetch(base_url)
        except Exception as e:  # pragma: no cover - network
            warnings.append(f"[COPA] Failed to fetch {base_url}: {e} (v2026-01-19a)")
            continue

        # Flatten whitespace but keep other characters (like the en-dash).
        text = re.sub(r"\s+", " ", html, flags=re.DOTALL)

        # Try to focus on a block near "COPA SAESP" if present; otherwise use full page.
        lower = text.lower()
        anchor_idx = lower.find("copa saesp")
        if anchor_idx != -1:
            # Take a window around the anchor to avoid matching random dates elsewhere.
            start = max(0, anchor_idx - 500)
            end = min(len(text), anchor_idx + 2000)
            block = text[start:end]
        else:
            block = text

        m = range_pattern.search(block)
        if not m:
            warnings.append(
                f"[COPA] Could not find a 'Month DD–DD, YYYY' congress range on {base_url}. (v2026-01-19a)"
            )
            continue

        month_name = m.group(1).lower()
        d1 = int(m.group(2))
        d2 = int(m.group(3))
        year = int(m.group(4))

        mnum = MONTHS_EN.get(month_name)
        if not mnum:
            warnings.append(
                f"[COPA] Unknown month name in congress range '{m.group(0)}' on {base_url}. (v2026-01-19a)"
            )
            continue

        start_date = _ymd(year, mnum, d1)
        end_date = _ymd(year, mnum, d2)

        # Location: if Transamerica Expo Center appears, use that.
        # Otherwise, fall back to a generic São Paulo string.
        loc: str
        if "transamerica expo center" in lower:
            loc = "Transamerica Expo Center, São Paulo, Brazil"
        else:
            loc = "São Paulo, Brazil"

        # Human-readable titles
        title_en = f"COPA SAESP {year} — Paulista Congress of Anesthesiology"
        title_pt = f"COPA SAESP {year} — Congresso Paulista de Anestesiologia"

        events.append(
            {
                "series": "COPA",
                "year": year,
                "type": "congress",
                "start_date": start_date,
                "end_date": end_date,
                "location": loc,
                "link": base_url,
                "priority": 8,
                "title": {
                    "en": title_en,
                    "pt": title_pt,
                },
                "evidence": {
                    "url": base_url,
                    "snippet": m.group(0),
                    "field": "congress_date_range",
                },
                "source": "scraped",
            }
        )

        warnings.append(
            f"[COPA DEBUG] url={base_url} congress_found=True "
            f"range='{m.group(0)}' (v2026-01-19a)"
        )

    if not events:
        warnings.append("[COPA] No events produced from configured URLs. (v2026-01-19a)")

    # Debug marker so we know this version ran at all
    warnings.append("[COPA DEBUG] scraper version v2026-01-19a")

    return events, warnings
