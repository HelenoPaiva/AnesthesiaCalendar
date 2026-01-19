# scripts/scrapers/copa.py

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Tuple
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


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
    """
    HTTP GET with a reasonable User-Agent, same pattern as other scrapers.
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


def _url_exists(url: str) -> bool:
    """
    Return True if the URL looks reachable.
    We treat 404/410 as definite "no", everything else as "maybe yes".
    """
    try:
        _fetch(url)
        return True
    except HTTPError as e:
        if e.code in (404, 410):
            return False
        return True
    except URLError:
        return False
    except Exception:
        return False


def _ymd(y: int, m: int, d: int) -> str:
    return f"{y:04d}-{m:02d}-{d:02d}"


def _flatten_whitespace(html: str) -> str:
    return re.sub(r"\s+", " ", html, flags=re.DOTALL)


def _scrape_one_url(url: str, cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Scrape a single COPA site (one edition) for the congress date range.

    We look for a pattern like:

        April 23–26, 2026

    i.e. "Month DD–DD, YYYY" with hyphen or en-dash.
    """
    warnings: List[str] = []
    events: List[Dict[str, Any]] = []

    try:
        html = _fetch(url)
    except Exception as e:  # pragma: no cover - network
        warnings.append(f"[COPA] Failed to fetch {url}: {e} ({SCRAPER_VERSION})")
        return events, warnings

    text = _flatten_whitespace(html)
    lower = text.lower()

    # Focus around "COPA SAESP" if present, otherwise use full page.
    anchor = "copa saesp"
    idx = lower.find(anchor)
    if idx != -1:
        start = max(0, idx - 800)
        end = min(len(text), idx + 3000)
        block = text[start:end]
    else:
        block = text

    # Pattern: Month DD–DD, YYYY
    range_pattern = re.compile(
        r"\b([A-Za-z]+)\s+(\d{1,2})\s*[-–]\s*(\d{1,2}),?\s+(20\d{2})\b",
        re.IGNORECASE,
    )

    m = range_pattern.search(block)
    if not m:
        warnings.append(
            f"[COPA] Could not find a 'Month DD–DD, YYYY' congress range on {url}. ({SCRAPER_VERSION})"
        )
        return events, warnings

    month_name = m.group(1).lower()
    d1 = int(m.group(2))
    d2 = int(m.group(3))
    year = int(m.group(4))

    mnum = MONTHS_EN.get(month_name)
    if not mnum:
        warnings.append(
            f"[COPA] Unknown month name in congress range '{m.group(0)}' on {url}. ({SCRAPER_VERSION})"
        )
        return events, warnings

    start_date = _ymd(year, mnum, d1)
    end_date = _ymd(year, mnum, d2)

    # Location heuristic: check for Transamerica Expo Center, otherwise generic São Paulo.
    if "transamerica expo center" in lower:
        location = "Transamerica Expo Center, São Paulo, Brazil"
    else:
        location = "São Paulo, Brazil"

    title_en = f"COPA SAESP {year} — Paulista Congress of Anesthesiology"
    title_pt = f"COPA SAESP {year} — Congresso Paulista de Anestesiologia"

    events.append(
        {
            "series": "COPA",
            "year": year,
            "type": "congress",
            "start_date": start_date,
            "end_date": end_date,
            "location": location,
            "link": url,
            "priority": 8,
            "title": {
                "en": title_en,
                "pt": title_pt,
            },
            "evidence": {
                "url": url,
                "snippet": m.group(0),
                "field": "congress_date_range",
            },
            "source": "scraped",
        }
    )

    warnings.append(
        f"[COPA DEBUG] url={url} congress_found=True range='{m.group(0)}' ({SCRAPER_VERSION})"
    )

    return events, warnings


def _scrape_from_template(base_url: str, cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Year-agnostic probing for COPA.

    If base_url looks like 'https://copa2026.saesp.org.br/en/',
    we detect the '2026' and treat it as a template:

        prefix = 'https://copa'
        year   = '2026'
        suffix = '.saesp.org.br/en/'

    Then we probe:

        https://copa2025.saesp.org.br/en/
        https://copa2026.saesp.org.br/en/
        https://copa2027.saesp.org.br/en/
        ...

    and scrape every URL that actually exists.
    """
    warnings: List[str] = []
    events: List[Dict[str, Any]] = []

    # Detect a 20xx year segment inside the URL
    m = re.search(r"(.*?)(20\d{2})(.*)", base_url)
    if not m:
        # No year segment → fall back to single-URL scraping
        ev, w = _scrape_one_url(base_url, cfg)
        events.extend(ev)
        warnings.extend(w)
        warnings.append(
            f"[COPA DEBUG] template_probe_skipped (no year segment in url={base_url}) ({SCRAPER_VERSION})"
        )
        return events, warnings

    prefix, year_str, suffix = m.groups()
    try:
        base_year = int(year_str)
    except ValueError:
        base_year = datetime.utcnow().year

    now_year = datetime.utcnow().year

    # We will probe a small window around both base_year and now_year
    start_year = min(base_year, now_year) - 1
    end_year = max(base_year, now_year) + 4  # a few years ahead

    for y in range(start_year, end_year + 1):
        candidate = f"{prefix}{y}{suffix}"
        if not _url_exists(candidate):
            continue
        ev, w = _scrape_one_url(candidate, cfg)
        events.extend(ev)
        warnings.extend(w)

    warnings.append(
        f"[COPA DEBUG] template_probe_base={base_url} years={start_year}-{end_year} ({SCRAPER_VERSION})"
    )

    return events, warnings


def scrape_copa(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Main entrypoint called by the orchestrator.

    Behavior:
      - If a URL *contains* a year (20xx), we treat it as a template and
        probe neighboring years via _scrape_from_template.
      - If a URL does NOT contain a year, we simply scrape that one URL.

    This makes the scraper year-agnostic and able to pick up future
    copa20xx.saesp.org.br sites once they go live, while your frontend
    logic handles which congress is "next" based on dates.
    """
    warnings: List[str] = []
    urls = cfg.get("urls") or []
    if not urls:
        return [], [f"[COPA] No URLs configured in sources.json. ({SCRAPER_VERSION})"]

    all_events: List[Dict[str, Any]] = []

    for raw_url in urls:
        url = raw_url.strip()
        if not url:
            continue

        if re.search(r"20\d{2}", url):
            ev, w = _scrape_from_template(url, cfg)
        else:
            ev, w = _scrape_one_url(url, cfg)

        all_events.extend(ev)
        warnings.extend(w)

    if not all_events:
        warnings.append(f"[COPA] No events produced from configured URLs. ({SCRAPER_VERSION})")

    # Marker so we know this code path ran
    warnings.append(f"[COPA DEBUG] scraper version {SCRAPER_VERSION}")

    return all_events, warnings
