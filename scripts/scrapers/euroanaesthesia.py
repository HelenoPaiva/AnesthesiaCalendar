# scripts/scrapers/euroanaesthesia.py

from __future__ import annotations

import re
import html as html_lib
from typing import Any, Dict, List, Tuple
from urllib.request import Request, urlopen


SCRAPER_VERSION = "v2026-01-19a"

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
    with urlopen(req, timeout=25) as resp:  # nosec - sandboxed in Actions
        raw = resp.read()
    return raw.decode("utf-8", errors="ignore")


def _ymd(y: int, m: int, d: int) -> str:
    return f"{y:04d}-{m:02d}-{d:02d}"


def _clean_text(s: str) -> str:
    s = html_lib.unescape(s or "")
    s = re.sub(r"\s+", " ", s, flags=re.DOTALL).strip()
    return s


def _parse_single_date(date_text: str) -> Tuple[str | None, int | None]:
    """
    Parse: '15 October 2025' => ('2025-10-15', 2025)
    """
    t = _clean_text(date_text)
    m = re.search(r"\b(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})\b", t)
    if not m:
        return None, None

    day = int(m.group(1))
    month_name = m.group(2).lower()
    year = int(m.group(3))

    month = MONTHS_EN.get(month_name)
    if not month:
        return None, None

    return _ymd(year, month, day), year


def _parse_range_date(date_text: str) -> Tuple[str | None, str | None, int | None]:
    """
    Parse: '6-8 June 2026' or '6–8 June 2026'
      => ('2026-06-06', '2026-06-08', 2026)
    """
    t = _clean_text(date_text)

    m = re.search(
        r"\b(\d{1,2})\s*[-–]\s*(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})\b",
        t,
        flags=re.IGNORECASE,
    )
    if not m:
        return None, None, None

    d1 = int(m.group(1))
    d2 = int(m.group(2))
    month_name = m.group(3).lower()
    year = int(m.group(4))

    month = MONTHS_EN.get(month_name)
    if not month:
        return None, None, None

    return _ymd(year, month, d1), _ymd(year, month, d2), year


def _map_label_to_type(label: str) -> Tuple[str | None, str | None, str | None]:
    """
    Map Euroanaesthesia labels into ACC event types + title tails.
    Keep types compatible with the dashboard (DEADLINE_TYPES in app.js).
    """
    l = _clean_text(label).lower()

    # Abstract window
    if "abstract submission opens" in l:
        return "abstract_open", "Abstract submission opens", "Abertura de submissão de resumos"
    if "abstract submission closes" in l:
        return "abstract_deadline", "Abstract submission deadline", "Prazo final de submissão de resumos"

    # Registration milestones
    if "early" in l and "registration" in l and ("opens" in l or "open" in l):
        # "Early & group registration opens"
        return "other_deadline", "Early registration opens", "Abertura de inscrição early"
    if "early" in l and "registration" in l and ("closes" in l or "close" in l):
        return "early_bird_deadline", "Early registration deadline", "Prazo final de inscrição early"

    if "late registration" in l and ("opens" in l or "open" in l):
        return "other_deadline", "Late registration opens", "Abertura de inscrição tardia"
    if "late registration" in l and ("closes" in l or "close" in l):
        return "registration_deadline", "Late registration deadline", "Prazo final de inscrição tardia"

    if "desk registration" in l and ("opens" in l or "open" in l):
        return "other_deadline", "Desk registration opens", "Abertura de inscrição no local"

    if "registration closes" in l:
        # e.g., "Desk & Virtual registration closes"
        return "registration_deadline", "Registration deadline", "Prazo final de inscrição"

    if "presenter registration closes" in l:
        # e.g., "Abstract presenter registration closes"
        return "registration_deadline", "Presenter registration deadline", "Prazo de inscrição do apresentador"

    # Congress itself
    if "congress dates" in l or l.strip() == "congress":
        return "congress", None, None

    return None, None, None


def scrape_euroanaesthesia(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Scrape Euroanaesthesia 'Important dates' timeline blocks from euroanaesthesia.org/<year>/.

    Strategy (WCA-style):
      - fetch HTML
      - find a stable anchor ('Important dates' and/or timeline__container)
      - extract <p><strong>LABEL</strong><br>...>DATE</a> entries
      - parse dates (single and ranges)
      - map labels to event types
      - emit debug warnings with counts and samples
    """
    warnings: List[str] = []
    urls = cfg.get("urls") or []
    if not urls:
        return [], [f"[EUROANAESTHESIA] No URLs configured in sources.json. ({SCRAPER_VERSION})"]

    # Prefer cfg-provided metadata if present
    location_default = cfg.get("location") or "TBA"
    series = "EUROANAESTHESIA"

    all_events: List[Dict[str, Any]] = []

    for url in urls:
        try:
            raw_html = _fetch(url)
        except Exception as e:  # pragma: no cover - network
            warnings.append(f"[EUROANAESTHESIA] Failed to fetch {url}: {e} ({SCRAPER_VERSION})")
            continue

        # Normalize whitespace (makes regex spans reliable)
        text = re.sub(r"\s+", " ", raw_html, flags=re.DOTALL)

        # Anchor-based window extraction
        lower = text.lower()
        idx1 = lower.find("important dates")
        idx2 = lower.find("timeline__container")

        window_start = -1
        if idx2 != -1:
            window_start = idx2
        elif idx1 != -1:
            window_start = idx1

        block = ""
        if window_start != -1:
            block = text[window_start : window_start + 20000]
        else:
            # Fallback: scan full page (still safe)
            block = text
            warnings.append(f"[EUROANAESTHESIA] Anchor not found; scanning full page: {url} ({SCRAPER_VERSION})")

        # Extract items of the form:
        # <p><strong>LABEL</strong><br> <a ...>DATE_TEXT<span ...></span></a> ...
        item_pattern = re.compile(
            r"<p>\s*<strong>(?P<label>.*?)</strong>\s*<br\s*/?>\s*"
            r"(?:<a[^>]*>)\s*(?P<date>[^<]+?)\s*(?:<span|</a>)",
            flags=re.IGNORECASE,
        )

        matches = list(item_pattern.finditer(block))
        warnings.append(
            f"[EUROANAESTHESIA DEBUG] url={url} items_found={len(matches)} ({SCRAPER_VERSION})"
        )

        sample_pairs: List[str] = []
        deadline_events = 0
        congress_found = False

        for m in matches:
            label_raw = m.group("label")
            date_raw = m.group("date")

            label = _clean_text(label_raw)
            date_text = _clean_text(date_raw)

            if len(sample_pairs) < 4:
                sample_pairs.append(f"{label} => {date_text}")

            etype, title_en_tail, title_pt_tail = _map_label_to_type(label)

            if not etype:
                continue

            # Congress range
            if etype == "congress":
                start_iso, end_iso, year = _parse_range_date(date_text)
                if not start_iso or not end_iso or not year:
                    # Some pages might show congress range in a different part.
                    # Try parsing a range anywhere in the nearby text.
                    start_iso, end_iso, year = _parse_range_date(label + " " + date_text)
                if not start_iso or not end_iso or not year:
                    warnings.append(
                        f"[EUROANAESTHESIA] Congress date range not parsed from '{date_text}' on {url} ({SCRAPER_VERSION})"
                    )
                    continue

                congress_found = True

                all_events.append(
                    {
                        "series": series,
                        "year": year,
                        "type": "congress",
                        "start_date": start_iso,
                        "end_date": end_iso,
                        "location": location_default,
                        "link": url,
                        "priority": 8,
                        "title": {
                            "en": f"Euroanaesthesia {year} — ESAIC Annual Congress",
                            "pt": f"Euroanaesthesia {year} — Congresso anual da ESAIC",
                        },
                        "evidence": {
                            "url": url,
                            "snippet": f"{label} — {date_text}",
                            "field": "important_dates_timeline",
                        },
                        "source": "scraped",
                    }
                )
                continue

            # Single-date deadlines
            iso, year = _parse_single_date(date_text)
            if not iso or not year:
                # Try to parse within a slightly larger string (robustness)
                iso, year = _parse_single_date(label + " " + date_text)
            if not iso or not year:
                warnings.append(
                    f"[EUROANAESTHESIA] Could not parse date '{date_text}' for '{label}' on {url} ({SCRAPER_VERSION})"
                )
                continue

            deadline_events += 1

            all_events.append(
                {
                    "series": series,
                    "year": year,
                    "type": etype,
                    "date": iso,
                    "location": "—",
                    "link": url,
                    "priority": 7,
                    "title": {
                        "en": f"Euroanaesthesia {year} — {title_en_tail}",
                        "pt": f"Euroanaesthesia {year} — {title_pt_tail}",
                    },
                    "evidence": {
                        "url": url,
                        "snippet": f"{label} — {date_text}",
                        "field": "important_dates_timeline",
                    },
                    "source": "scraped",
                }
            )

        if sample_pairs:
            warnings.append(
                f"[EUROANAESTHESIA DEBUG] samples={sample_pairs} ({SCRAPER_VERSION})"
            )

        warnings.append(
            f"[EUROANAESTHESIA DEBUG] url={url} deadline_events={deadline_events} congress_found={congress_found} ({SCRAPER_VERSION})"
        )

        if len(matches) == 0:
            warnings.append(
                f"[EUROANAESTHESIA] No 'Important dates' timeline entries detected on {url} ({SCRAPER_VERSION})"
            )

    # Always add a marker so we know exactly what code ran
    warnings.append(f"[EUROANAESTHESIA DEBUG] scraper version {SCRAPER_VERSION}")

    return all_events, warnings
