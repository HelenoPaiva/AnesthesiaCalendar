# scripts/scrapers/cba.py

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple
from urllib.request import Request, urlopen


# Portuguese month names used on the SBA site
MONTHS_PT = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "marco": 3,  # fallback without cedilha, in case of HTML quirks
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
    Year-agnostic CBA scraper.

    Strategy (v2026-01-19b):
      - Fetch SBA page (usually https://www.sbahq.org/).
      - In the *text*, find a line like:

          "Congresso Brasileiro de Anestesiologia
           26 a 29 de novembro de 2026 Fortaleza - CE Presencial"

      - Parse date range "dd a dd de <mês> de 20xx".
      - Extract location between the year and "Presencial".
      - Try to find a nearby href to cba20xx.com.br, otherwise fall back to SBA URL.

    Produces a single "congress" event for CBA {year}.
    """
    warnings: List[str] = []

    urls = cfg.get("urls") or []
    if not urls:
        return [], ["[CBA] No URLs configured in sources.json. (v2026-01-19b)"]

    base_url = urls[0]

    try:
        html = _fetch(base_url)
    except Exception as e:  # pragma: no cover - network
        return [], [f"[CBA] Failed to fetch {base_url}: {e} (v2026-01-19b)"]

    # Keep a copy of raw HTML (for href search) and build a flattened text
    text = re.sub(r"\s+", " ", html, flags=re.DOTALL)

    # ------------------------------------------------------------------
    # 1) Locate the CBA agenda line in *text* (not the banner alt text).
    #
    # We specifically look for:
    #   "Congresso Brasileiro de Anestesiologia <...> Presencial"
    # where the <...> portion should contain the Portuguese range
    #   "dd a dd de <mês> de 20xx" and the location.
    # ------------------------------------------------------------------
    block_match = re.search(
        r"Congresso Brasileiro de Anestesiologia\s+(.{0,200}?Presencial)",
        text,
        flags=re.IGNORECASE,
    )

    if not block_match:
        warnings.append(
            "[CBA] Could not locate CBA agenda line containing 'Congresso Brasileiro de Anestesiologia ... Presencial'. (v2026-01-19b)"
        )
        return [], warnings

    tail = block_match.group(1)
    snippet = f"Congresso Brasileiro de Anestesiologia {tail}".strip()
    warnings.append(f"[CBA DEBUG] snippet='{snippet[:200]}' (v2026-01-19b)")

    # ------------------------------------------------------------------
    # 2) Parse the date range: "dd a dd de <mês> de 20xx"
    # ------------------------------------------------------------------
    m_date = re.search(
        r"(\d{1,2})\s*a\s*(\d{1,2})\s*de\s*([A-Za-zçéãõ]+)\s*de\s*(20\d{2})",
        snippet,
        flags=re.IGNORECASE,
    )

    if not m_date:
        warnings.append(
            "[CBA] Could not parse CBA date range in snippet. (v2026-01-19b)"
        )
        return [], warnings

    d1 = int(m_date.group(1))
    d2 = int(m_date.group(2))
    month_name = m_date.group(3).lower()
    year = int(m_date.group(4))

    month_num = MONTHS_PT.get(month_name)
    if not month_num:
        warnings.append(
            f"[CBA] Unknown month name in CBA date range: '{month_name}' (v2026-01-19b)"
        )
        return [], warnings

    start_date = _ymd(year, month_num, d1)
    end_date = _ymd(year, month_num, d2)

    # ------------------------------------------------------------------
    # 3) Extract location: from "<year> <location> Presencial"
    #    e.g. "2026 Fortaleza - CE Presencial"
    # ------------------------------------------------------------------
    m_loc = re.search(
        r"\b20\d{2}\s+(.+?)\s+Presencial",
        snippet,
        flags=re.IGNORECASE,
    )
    location = m_loc.group(1).strip() if m_loc else "Brasil"

    # ------------------------------------------------------------------
    # 4) Try to find a nearby href in the raw HTML that points to the CBA site.
    # ------------------------------------------------------------------
    link = base_url
    href_match = re.search(
        r"Congresso Brasileiro de Anestesiologia.*?href=\"([^\"]+)\"",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if href_match:
        raw_href = href_match.group(1).strip()
        # Normalise to absolute URL
        if raw_href.startswith("//"):
            link = "https:" + raw_href
        elif raw_href.startswith("http://") or raw_href.startswith("https://"):
            link = raw_href
        elif raw_href.startswith("/"):
            # Assume SBA as host if it's a relative link
            link = "https://www.sbahq.org" + raw_href
        else:
            # e.g. "www.cba2026.com.br"
            if raw_href.startswith("www."):
                link = "https://" + raw_href
            else:
                link = raw_href

    warnings.append(
        f"[CBA DEBUG] parsed_range={start_date}..{end_date} location='{location}' link='{link}' (v2026-01-19b)"
    )
    warnings.append("[CBA DEBUG] scraper version v2026-01-19b")

    events: List[Dict[str, Any]] = [
        {
            "series": "CBA",
            "year": year,
            "type": "congress",
            "start_date": start_date,
            "end_date": end_date,
            "location": location,
            "link": link,
            "priority": 10,
            "title": {
                "en": f"CBA {year} — Brazilian Congress of Anesthesiology",
                "pt": f"CBA {year} — Congresso Brasileiro de Anestesiologia",
            },
            "evidence": {
                "url": base_url,
                "snippet": snippet,
                "field": "agenda_highlight_line",
            },
            "source": "scraped",
        }
    ]

    return events, warnings
