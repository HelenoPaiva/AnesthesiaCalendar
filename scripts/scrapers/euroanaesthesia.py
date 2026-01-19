# scripts/scrapers/euroanaesthesia.py

from __future__ import annotations

import re
import html as html_lib
from typing import Any, Dict, List, Tuple
from urllib.request import Request, urlopen


SCRAPER_VERSION = "v2026-01-19b"

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
    Parse: '6-8 June 2026' / '6–8 June 2026'
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
    Map Euroanaesthesia labels into event types + title tails.
    Compatible with dashboard DEADLINE_TYPES in app.js.
    """
    l = _clean_text(label).lower()

    # Abstract
    if "abstract" in l:
        if "open" in l:
            return (
                "abstract_open",
                "Abstract submission opens",
                "Abertura de submissão de resumos",
            )
        if "close" in l or "deadline" in l:
            return (
                "abstract_deadline",
                "Abstract submission deadline",
                "Prazo final de submissão de resumos",
            )

    # Early registration
    if "early" in l and "registration" in l:
        if "open" in l:
            return (
                "other_deadline",
                "Early registration opens",
                "Abertura de inscrição early",
            )
        if "close" in l or "deadline" in l:
            return (
                "early_bird_deadline",
                "Early registration deadline",
                "Prazo de inscrição early-bird",
            )

    # Late registration
    if "late" in l and "registration" in l:
        if "open" in l:
            return (
                "other_deadline",
                "Late registration opens",
                "Abertura de inscrição tardia",
            )
        if "close" in l or "deadline" in l:
            return (
                "registration_deadline",
                "Late registration deadline",
                "Prazo de inscrição tardia",
            )

    # Generic registration closes (desk/virtual/etc.)
    if "registration" in l and ("close" in l or "deadline" in l):
        return (
            "registration_deadline",
            "Registration deadline",
            "Prazo final de inscrição",
        )

    if "presenter registration" in l and ("close" in l or "deadline" in l):
        return (
            "registration_deadline",
            "Presenter registration deadline",
            "Prazo de inscrição do apresentador",
        )

    # Congress dates
    if "congress dates" in l or l.strip() == "congress":
        return "congress", None, None

    return None, None, None


def _extract_label_date_pairs(html: str) -> List[Tuple[str, str]]:
    """
    Extract (label, date_text) pairs from Euroanaesthesia 'Important dates' blocks.

    Handles:
      A) <p><strong>Label</strong></p> <p><a ...>DATE</a>...</p>
      B) <p><strong>DATE</strong> – Label text</p>
    """
    text = re.sub(r"\s+", " ", html, flags=re.DOTALL)

    pairs: List[Tuple[str, str]] = []

    # --- Pattern A: label in <p><strong>, date in next <p><a> ---
    pattern_a = re.compile(
        r"<p>\s*<strong>(?P<label>[^<]+)</strong>\s*</p>\s*"
        r"<p>\s*<a[^>]*>(?P<date>[^<]+)</a",
        flags=re.IGNORECASE,
    )

    for m in pattern_a.finditer(text):
        label = _clean_text(m.group("label"))
        date = _clean_text(m.group("date"))
        if label and date:
            pairs.append((label, date))

    # --- Pattern B: date in <strong>, label in same <p> after dash ---
    pattern_b = re.compile(
        r"<p[^>]*>\s*<strong>(?P<date>[^<]+)</strong>\s*"
        r"(?:[-–]\s*)?(?P<label>[^<]+)</p>",
        flags=re.IGNORECASE,
    )

    for m in pattern_b.finditer(text):
        date = _clean_text(m.group("date"))
        label = _clean_text(m.group("label"))
        if label and date:
            pairs.append((label, date))

    # De-duplicate (label, date) pairs
    seen = set()
    unique_pairs: List[Tuple[str, str]] = []
    for label, date in pairs:
        key = (label.lower(), date)
        if key in seen:
            continue
        seen.add(key)
        unique_pairs.append((label, date))

    return unique_pairs


def _scrape_one_url(url: str, cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    try:
        raw_html = _fetch(url)
    except Exception as e:  # pragma: no cover - network
        return [], [f"[EUROANAESTHESIA] Failed to fetch {url}: {e} ({SCRAPER_VERSION})"]

    # Restrict to "Important dates" / timeline area if present
    text = re.sub(r"\s+", " ", raw_html, flags=re.DOTALL)
    lower = text.lower()

    idx_timeline = lower.find("timeline__container")
    idx_heading = lower.find("important dates")

    start_idx = -1
    if idx_timeline != -1:
        start_idx = idx_timeline
    elif idx_heading != -1:
        start_idx = idx_heading

    if start_idx != -1:
        block = text[start_idx : start_idx + 25000]
    else:
        block = text
        warnings.append(
            f"[EUROANAESTHESIA] Could not find 'Important dates' anchor; scanning full page: {url} ({SCRAPER_VERSION})"
        )

    pairs = _extract_label_date_pairs(block)
    warnings.append(
        f"[EUROANAESTHESIA DEBUG] url={url} pairs_found={len(pairs)} ({SCRAPER_VERSION})"
    )

    location_default = cfg.get("location") or "Rotterdam, The Netherlands"
    series = "EUROANAESTHESIA"

    events: List[Dict[str, Any]] = []
    deadline_events = 0
    congress_found = False

    sample_strings: List[str] = []

    for label, date_text in pairs:
        if len(sample_strings) < 4:
            sample_strings.append(f"{label} => {date_text}")

        etype, title_en_tail, title_pt_tail = _map_label_to_type(label)
        if not etype:
            continue

        # Congress (date range expected)
        if etype == "congress":
            start_iso, end_iso, year = _parse_range_date(date_text)
            if not start_iso or not end_iso or not year:
                # fallback: sometimes date+label might be in weird order
                start_iso, end_iso, year = _parse_range_date(label + " " + date_text)

            if not start_iso or not end_iso or not year:
                warnings.append(
                    f"[EUROANAESTHESIA] Congress date range not parsed from '{date_text}' on {url} ({SCRAPER_VERSION})"
                )
                continue

            congress_found = True

            events.append(
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

        # Deadlines (single date)
        iso, year = _parse_single_date(date_text)
        if not iso or not year:
            # Try combining label+date as fallback
            iso, year = _parse_single_date(label + " " + date_text)

        if not iso or not year:
            warnings.append(
                f"[EUROANAESTHESIA] Could not parse date '{date_text}' for '{label}' on {url} ({SCRAPER_VERSION})"
            )
            continue

        deadline_events += 1

        events.append(
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

    if sample_strings:
        warnings.append(
            f"[EUROANAESTHESIA DEBUG] url={url} samples={sample_strings} ({SCRAPER_VERSION})"
        )

    warnings.append(
        f"[EUROANAESTHESIA DEBUG] url={url} deadline_events={deadline_events} congress_found={congress_found} ({SCRAPER_VERSION})"
    )

    if not events:
        warnings.append(
            f"[EUROANAESTHESIA] No events produced from Important dates block on {url} ({SCRAPER_VERSION})"
        )

    return events, warnings


def scrape_euroanaesthesia(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Scrape Euroanaesthesia "Important dates" for each URL in sources.json.

    - No automatic year probing: it uses exactly the URLs you list.
      (e.g. https://euroanaesthesia.org/2026/, https://euroanaesthesia.org/2027/)
    - Robust to both 2025-style and 2026-style timeline markup.
    """
    warnings: List[str] = []
    urls = cfg.get("urls") or []
    if not urls:
        return [], [f"[EUROANAESTHESIA] No URLs configured in sources.json. ({SCRAPER_VERSION})"]

    all_events: List[Dict[str, Any]] = []

    for url in urls:
        ev, w = _scrape_one_url(url, cfg)
        all_events.extend(ev)
        warnings.extend(w)

    # Marker so we always know what code ran
    warnings.append(f"[EUROANAESTHESIA DEBUG] scraper version {SCRAPER_VERSION}")

    return all_events, warnings
