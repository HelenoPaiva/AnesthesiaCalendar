# scripts/scrapers/copa.py

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Tuple
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin


SCRAPER_VERSION = "v2026-01-19c"

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
    True only for pages we can actually fetch.
    Treat 402/403/404/410 as non-existent/unusable so we don't probe them.
    """
    try:
        _fetch(url)
        return True
    except HTTPError as e:
        if e.code in (402, 403, 404, 410):
            return False
        return False
    except URLError:
        return False
    except Exception:
        return False


def _ymd(y: int, m: int, d: int) -> str:
    return f"{y:04d}-{m:02d}-{d:02d}"


def _flatten(html: str) -> str:
    return re.sub(r"\s+", " ", html, flags=re.DOTALL).strip()


def _parse_en_range(text: str) -> Tuple[int, int, int, int] | None:
    """
    Parse: Month DD–DD, YYYY  (English)
    Example: April 24-27, 2025
    """
    m = re.search(
        r"\b([A-Za-z]+)\s+(\d{1,2})\s*[-–]\s*(\d{1,2}),?\s+(20\d{2})\b",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    month_name = m.group(1).lower()
    d1 = int(m.group(2))
    d2 = int(m.group(3))
    y = int(m.group(4))
    mnum = MONTHS_EN.get(month_name)
    if not mnum:
        return None
    return y, mnum, d1, d2


def _parse_pt_range(text: str) -> Tuple[int, int, int, int] | None:
    """
    Parse Portuguese range:
      '23 a 26 de abril de 2026'
      '23-26 de abril de 2026'
      '23 – 26 de abril de 2026'
    """
    m = re.search(
        r"\b(\d{1,2})\s*(?:a|à|[-–])\s*(\d{1,2})\s*de\s*([A-Za-zçÇãÃõÕéÉíÍóÓúÚ]+)\s*de\s*(20\d{2})\b",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    d1 = int(m.group(1))
    d2 = int(m.group(2))
    month_name = m.group(3).lower()
    y = int(m.group(4))
    # normalize common accents
    month_name_norm = (
        month_name.replace("ç", "c")
        .replace("ã", "a")
        .replace("á", "a")
        .replace("à", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
    )
    mnum = MONTHS_PT.get(month_name) or MONTHS_PT.get(month_name_norm)
    if not mnum:
        return None
    return y, mnum, d1, d2


def _parse_pt_deadline(text: str) -> Tuple[int, int, int] | None:
    """
    Parse Portuguese deadline:
      '... até 30 de janeiro de 2026'
    """
    m = re.search(
        r"\bat[eé]\s*(\d{1,2})\s*de\s*([A-Za-zçÇãÃõÕéÉíÍóÓúÚ]+)\s*de\s*(20\d{2})\b",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    d = int(m.group(1))
    month_name = m.group(2).lower()
    y = int(m.group(3))
    month_name_norm = (
        month_name.replace("ç", "c")
        .replace("ã", "a")
        .replace("á", "a")
        .replace("à", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
    )
    mnum = MONTHS_PT.get(month_name) or MONTHS_PT.get(month_name_norm)
    if not mnum:
        return None
    return y, mnum, d


def _best_future_congress(candidates: List[Tuple[int, int, int, int]]) -> Tuple[int, int, int, int] | None:
    """
    Prefer the earliest congress that is in the future (by start date).
    If none are in the future, return the latest one.
    """
    if not candidates:
        return None

    today = datetime.utcnow().date()
    future = []
    for y, m, d1, d2 in candidates:
        try:
            start = datetime(y, m, d1).date()
        except Exception:
            continue
        if start >= today:
            future.append((y, m, d1, d2))

    if future:
        future.sort(key=lambda t: (t[0], t[1], t[2], t[3]))
        return future[0]

    candidates.sort(key=lambda t: (t[0], t[1], t[2], t[3]), reverse=True)
    return candidates[0]


def _scrape_one_edition(base_url: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Scrape a single COPA edition site.
    Strategy:
      - fetch the configured URL
      - also fetch /temas-livres/ on the same host (Portuguese key info lives there)
      - parse congress range (prefer PT)
      - parse abstracts deadline (PT)
    """
    warnings: List[str] = []
    events: List[Dict[str, Any]] = []

    pages_to_try = [base_url]

    # Try to build the Portuguese page on the same host
    temas_url = urljoin(base_url.rstrip("/") + "/", "../temas-livres/")
    # urljoin above can behave oddly depending on trailing slashes; force a sane path:
    # If base_url is https://copa2026.saesp.org.br/en/
    # we want https://copa2026.saesp.org.br/temas-livres/
    m_host = re.match(r"^(https?://[^/]+)", base_url.strip())
    if m_host:
        temas_url = m_host.group(1).rstrip("/") + "/temas-livres/"
        pages_to_try.append(temas_url)

    fetched_blocks: List[Tuple[str, str]] = []
    for u in pages_to_try:
        try:
            html = _fetch(u)
        except Exception as e:
            warnings.append(f"[COPA] Failed to fetch {u}: {e} ({SCRAPER_VERSION})")
            continue
        fetched_blocks.append((u, _flatten(html)))

    if not fetched_blocks:
        warnings.append(f"[COPA] No pages could be fetched for edition base {base_url}. ({SCRAPER_VERSION})")
        return events, warnings

    # Collect congress candidates from all pages
    congress_candidates: List[Tuple[int, int, int, int]] = []
    congress_snippets: List[Tuple[str, str]] = []

    for u, text in fetched_blocks:
        # Prefer PT range if present
        pt = _parse_pt_range(text)
        if pt:
            congress_candidates.append(pt)
            # Keep a small evidence snippet around the first match
            m = re.search(
                r"(\d{1,2}\s*(?:a|à|[-–])\s*\d{1,2}\s*de\s*[A-Za-zçÇãÃõÕéÉíÍóÓúÚ]+\s*de\s*20\d{2})",
                text,
                flags=re.IGNORECASE,
            )
            if m:
                congress_snippets.append((u, m.group(1)))

        en = _parse_en_range(text)
        if en:
            congress_candidates.append(en)
            m = re.search(
                r"([A-Za-z]+\s+\d{1,2}\s*[-–]\s*\d{1,2},?\s+20\d{2})",
                text,
                flags=re.IGNORECASE,
            )
            if m:
                congress_snippets.append((u, m.group(1)))

    picked = _best_future_congress(congress_candidates)
    if not picked:
        warnings.append(f"[COPA] Could not find congress date range on {base_url}. ({SCRAPER_VERSION})")
        warnings.append(f"[COPA DEBUG] pages_tried={[u for (u, _) in fetched_blocks]} ({SCRAPER_VERSION})")
        return events, warnings

    year, month, d1, d2 = picked
    start_date = _ymd(year, month, d1)
    end_date = _ymd(year, month, d2)

    # Location heuristic
    full_text_all = " ".join([t for (_, t) in fetched_blocks]).lower()
    if "transamerica" in full_text_all:
        location = "Transamerica Expo Center, São Paulo, Brazil"
    else:
        location = "São Paulo, Brazil"

    # Congress event
    events.append(
        {
            "series": "COPA",
            "year": year,
            "type": "congress",
            "start_date": start_date,
            "end_date": end_date,
            "location": location,
            "link": base_url,
            "priority": 7,
            "title": {
                "en": f"COPA SAESP {year} — Paulista Congress of Anesthesiology",
                "pt": f"COPA SAESP {year} — Congresso Paulista de Anestesiologia",
            },
            "evidence": {
                "url": congress_snippets[0][0] if congress_snippets else base_url,
                "snippet": congress_snippets[0][1] if congress_snippets else f"{start_date}–{end_date}",
                "field": "congress_date_range",
            },
            "source": "scraped",
        }
    )

    # Abstract deadline: only from PT deadline pattern (the snippet you gave)
    deadline_found = None
    deadline_evidence = None
    for u, text in fetched_blocks:
        dl = _parse_pt_deadline(text)
        if dl:
            y, m, d = dl
            deadline_found = _ymd(y, m, d)
            # Capture a compact evidence snippet
            m_ev = re.search(
                r"(submeta\s+seu\s+trabalho[^<]{0,120}?\bat[eé]\s*\d{1,2}\s*de\s*[A-Za-zçÇãÃõÕéÉíÍóÓúÚ]+\s*de\s*20\d{2})",
                text,
                flags=re.IGNORECASE,
            )
            if m_ev:
                deadline_evidence = (u, m_ev.group(1))
            else:
                # fallback: any "... até DD de mês de YYYY"
                m_ev2 = re.search(
                    r"(\bat[eé]\s*\d{1,2}\s*de\s*[A-Za-zçÇãÃõÕéÉíÍóÓúÚ]+\s*de\s*20\d{2})",
                    text,
                    flags=re.IGNORECASE,
                )
                if m_ev2:
                    deadline_evidence = (u, m_ev2.group(1))
            break

    if deadline_found:
        events.append(
            {
                "series": "COPA",
                "year": year,
                "type": "abstract_deadline",
                "date": deadline_found,
                "location": location,
                "link": temas_url if m_host else base_url,
                "priority": 6,
                "title": {
                    "en": f"COPA SAESP {year} — Abstract submission deadline",
                    "pt": f"COPA SAESP {year} — Prazo final de submissão de trabalhos",
                },
                "evidence": {
                    "url": deadline_evidence[0] if deadline_evidence else (temas_url if m_host else base_url),
                    "snippet": deadline_evidence[1] if deadline_evidence else deadline_found,
                    "field": "abstract_deadline_snippet",
                },
                "source": "scraped",
            }
        )
    else:
        warnings.append(f"[COPA] Could not find abstracts deadline snippet on edition pages. ({SCRAPER_VERSION})")

    warnings.append(
        f"[COPA DEBUG] base={base_url} pages={len(fetched_blocks)} "
        f"congress_found=True abstract_deadline={'yes' if deadline_found else 'no'} "
        f"picked={start_date}..{end_date} ({SCRAPER_VERSION})"
    )

    return events, warnings


def _scrape_from_template(url_with_year: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Probe copa20xx.saesp.org.br editions based on a provided year URL.
    Skip 402/403/404/410 editions.
    """
    warnings: List[str] = []
    events: List[Dict[str, Any]] = []

    m = re.search(r"(https?://[^/]*?)(20\d{2})(\.[^/]+)(/.*)?$", url_with_year.strip())
    if not m:
        ev, w = _scrape_one_edition(url_with_year)
        events.extend(ev)
        warnings.extend(w)
        warnings.append(f"[COPA DEBUG] template_probe_skipped url={url_with_year} ({SCRAPER_VERSION})")
        return events, warnings

    host_prefix = m.group(1)  # e.g. https://copa
    year_str = m.group(2)     # e.g. 2026
    host_suffix = m.group(3)  # e.g. .saesp.org.br
    path = m.group(4) or "/"  # e.g. /en/

    try:
        base_year = int(year_str)
    except ValueError:
        base_year = datetime.utcnow().year

    now_year = datetime.utcnow().year
    start_year = min(base_year, now_year) - 1
    end_year = max(base_year, now_year) + 4

    attempted = 0
    fetched = 0

    for y in range(start_year, end_year + 1):
        candidate = f"{host_prefix}{y}{host_suffix}{path}"
        attempted += 1
        if not _url_exists(candidate):
            continue
        fetched += 1
        ev, w = _scrape_one_edition(candidate)
        events.extend(ev)
        warnings.extend(w)

    warnings.append(
        f"[COPA DEBUG] template_probe_base={url_with_year} years={start_year}-{end_year} "
        f"attempted={attempted} fetched={fetched} ({SCRAPER_VERSION})"
    )

    return events, warnings


def scrape_copa(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Entry point.

    - If the configured URL contains a year (20xx), probe adjacent editions.
    - Otherwise, scrape the URL directly.
    """
    warnings: List[str] = []
    urls = cfg.get("urls") or []
    if not urls:
        return [], [f"[COPA] No URLs configured in sources.json. ({SCRAPER_VERSION})"]

    all_events: List[Dict[str, Any]] = []

    for raw in urls:
        u = (raw or "").strip()
        if not u:
            continue

        if re.search(r"20\d{2}", u):
            ev, w = _scrape_from_template(u)
        else:
            ev, w = _scrape_one_edition(u)

        all_events.extend(ev)
        warnings.extend(w)

    if not all_events:
        warnings.append(f"[COPA] No events produced from configured URLs. ({SCRAPER_VERSION})")

    warnings.append(f"[COPA DEBUG] scraper version {SCRAPER_VERSION}")

    return all_events, warnings
