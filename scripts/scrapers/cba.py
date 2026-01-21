# scripts/scrapers/cba.py

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple
from urllib.request import Request, urlopen


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
    with urlopen(req, timeout=20) as resp:  # nosec - sandboxed in Actions
        raw = resp.read()
    return raw.decode("utf-8", errors="ignore")


def _ymd(y: int, m: int, d: int) -> str:
    return f"{y:04d}-{m:02d}-{d:02d}"


def scrape_cba(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Scrape CBA (Congresso Brasileiro de Anestesiologia) from the SBA
    'Congressos e eventos' page.

    Year-agnostic:
      - Finds the first 'Congresso Brasileiro de Anestesiologia' block.
      - Parses PT-BR date like '26 a 29 de novembro de 2026'.
      - Parses location like 'Fortaleza - CE'.
      - Tries to extract the official CBA site (e.g. https://www.cba2026.com.br).

    Produces a single 'congress' event for the current upcoming CBA.
    """
    version_tag = "v2026-01-19a"
    warnings: List[str] = []

    urls = cfg.get("urls") or []
    if not urls:
        return [], [f"[CBA] No URLs configured in sources.json. ({version_tag})"]

    base_url = urls[0]

    try:
        html = _fetch(base_url)
    except Exception as e:  # pragma: no cover - network
        return [], [f"[CBA] Failed to fetch {base_url}: {e} ({version_tag})"]

    # Flatten whitespace for easier regex across tags/newlines
    text = re.sub(r"\s+", " ", html, flags=re.DOTALL)
    lower = text.lower()

    anchor = "congresso brasileiro de anestesiologia"
    idx = lower.find(anchor)
    if idx == -1:
        warnings.append(
            f"[CBA] Could not locate 'Congresso Brasileiro de Anestesiologia' block on SBA. ({version_tag})"
        )
        warnings.append(f"[CBA DEBUG] html_length={len(text)} ({version_tag})")
        return [], warnings

    # Take a window after the anchor where date + location + site live.
    block = text[idx : idx + 800]

    # 1) Date range: "26 a 29 de novembro de 2026"
    m_date = re.search(
        r"(\d{1,2})\s*a\s*(\d{1,2})\s*de\s*([A-Za-zçãé]+)\s*de\s*(20\d{2})",
        block,
        flags=re.IGNORECASE,
    )
    if not m_date:
        warnings.append(
            f"[CBA] Could not parse CBA date range near anchor. ({version_tag})"
        )
        warnings.append(f"[CBA DEBUG] block_snippet={block[:200]!r} ({version_tag})")
        return [], warnings

    d1 = int(m_date.group(1))
    d2 = int(m_date.group(2))
    month_name_raw = m_date.group(3).strip()
    year = int(m_date.group(4))

    month_name = month_name_raw.lower()
    month = MONTHS_PT.get(month_name)
    if not month:
        warnings.append(
            f"[CBA] Unknown PT month name in date range: '{month_name_raw}' ({version_tag})"
        )
        return [], warnings

    start_date = _ymd(year, month, d1)
    end_date = _ymd(year, month, d2)

    # 2) Location: "Fortaleza - CE"
    m_loc = re.search(r"([A-Za-zÀ-ÿ\s]+-\s*[A-Z]{2})", block)
    location = m_loc.group(1).strip() if m_loc else "—"

    # 3) CBA site link: try to extract something like https://www.cba2026.com.br
    m_site = re.search(
        r"https?://[^\s\"'>]*cba20\d{2}\.com\.br[^\s\"'>]*", block, flags=re.IGNORECASE
    )
    if m_site:
        cba_link = m_site.group(0)
    else:
        # fallback: SBA agenda page if we can't see the specific site
        cba_link = base_url

    events: List[Dict[str, Any]] = []

    events.append(
        {
            "series": "CBA",
            "year": year,
            "type": "congress",
            "start_date": start_date,
            "end_date": end_date,
            "location": location,
            "link": cba_link,
            "priority": 10,
            "title": {
                "en": f"CBA {year} — Brazilian Congress of Anesthesiology",
                "pt": f"CBA {year} — Congresso Brasileiro de Anestesiologia",
            },
            "evidence": {
                "url": base_url,
                "snippet": m_date.group(0) + " | " + location,
                "field": "sba_agenda_block",
            },
            "source": "scraped",
        }
    )

    warnings.append(
        f"[CBA DEBUG] anchor_found=True date='{m_date.group(0)}' location='{location}' link='{cba_link}' ({version_tag})"
    )
    warnings.append(f"[CBA DEBUG] scraper version {version_tag}")

    return events, warnings
