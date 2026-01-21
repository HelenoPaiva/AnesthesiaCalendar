# scripts/scrapers/cba.py

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple
from urllib.request import Request, urlopen


# Portuguese month names used on the SBA / CBA site
MONTHS_PT = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "marco": 3,  # fallback without cedilha
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
    Year-agnostic CBA scraper (v2026-01-19c).

    Expected HTML structure (as in https://www.sbahq.org/agenda/congresso-brasileiro-de-anestesiologia/):

        <h1 class="page-title">Congresso Brasileiro de Anestesiologia</h1>
        <div id="programa">
          <div class="detalhes mb-5">
            <div class="data"><i class="icon data"></i>26 a 29 de novembro de 2026</div>
            <div class="local"><i class="icon local"></i>Fortaleza - CE</div>
            <div class="local"><i class="icon2 presencial"></i>Presencial</div>
            <div class="envent-action">
              <div class="inscreva-se inscreva-se1 mt-2">
                <a href="https://www.cba2026.com.br/" class="btn btn-primary"> Inscreva-se</a>
              </div>
              <div class="inscreva-se mt-2">
                <a target="_blank" href="https://www.cba2026.com.br/" class="btn btn-outline-primary">Site</a>
              </div>
            </div>
          </div>
        </div>

    Strategy:
      - Use cfg["urls"][0] (should ideally be the agenda URL).
      - Find the block starting at the "page-title" for CBA.
      - Within that block:
          - Extract date range "dd a dd de <mês> de 20xx".
          - Extract location from the first "local" div.
          - Extract a CBA site link from Inscreva-se/Site buttons.
      - Return a single congress event for CBA {year}.
    """
    warnings: List[str] = []

    urls = cfg.get("urls") or []
    if not urls:
        return [], ["[CBA] No URLs configured in sources.json. (v2026-01-19c)"]

    base_url = urls[0]

    try:
        html = _fetch(base_url)
    except Exception as e:  # pragma: no cover - network
        return [], [f"[CBA] Failed to fetch {base_url}: {e} (v2026-01-19c)"]

    # ------------------------------------------------------------------
    # 1) Narrow down to the CBA agenda block
    # ------------------------------------------------------------------
    lower_html = html.lower()
    anchor = 'page-title">congresso brasileiro de anestesiologia'
    idx = lower_html.find(anchor)
    if idx == -1:
        warnings.append(
            "[CBA] Could not locate 'Congresso Brasileiro de Anestesiologia' page-title block. (v2026-01-19c)"
        )
        return [], warnings

    # Take a reasonably large window after the anchor
    block = html[idx : idx + 4000]
    block_flat = re.sub(r"\s+", " ", block, flags=re.DOTALL)

    warnings.append(
        f"[CBA DEBUG] block_sample='{block_flat[:200]}' (v2026-01-19c)"
    )

    # ------------------------------------------------------------------
    # 2) Extract the date range: e.g. "26 a 29 de novembro de 2026"
    # ------------------------------------------------------------------
    m_date = re.search(
        r"(\d{1,2})\s*a\s*(\d{1,2})\s*de\s*([A-Za-zçéãõ]+)\s*de\s*(20\d{2})",
        block_flat,
        flags=re.IGNORECASE,
    )

    if not m_date:
        warnings.append(
            "[CBA] Could not parse CBA date range in agenda block. (v2026-01-19c)"
        )
        return [], warnings

    d1 = int(m_date.group(1))
    d2 = int(m_date.group(2))
    month_name = m_date.group(3).lower()
    year = int(m_date.group(4))

    month_num = MONTHS_PT.get(month_name)
    if not month_num:
        warnings.append(
            f"[CBA] Unknown month name in CBA date range: '{month_name}' (v2026-01-19c)"
        )
        return [], warnings

    start_date = _ymd(year, month_num, d1)
    end_date = _ymd(year, month_num, d2)

    # ------------------------------------------------------------------
    # 3) Extract location: <div class="local"><i class="icon local"></i>Fortaleza - CE</div>
    # ------------------------------------------------------------------
    m_loc = re.search(
        r'<div\s+class="local">\s*<i[^>]*class="icon\s+local"[^>]*></i>\s*([^<]+)</div>',
        block,
        flags=re.IGNORECASE,
    )
    location = m_loc.group(1).strip() if m_loc else "Brasil"

    # ------------------------------------------------------------------
    # 4) Extract CBA site link from Inscreva-se / Site buttons
    # ------------------------------------------------------------------
    link = base_url
    m_link = re.search(
        r'href="([^"]+)"[^>]*>(?:\s*Inscreva-se|\s*Site)',
        block,
        flags=re.IGNORECASE,
    )
    if m_link:
        raw_href = m_link.group(1).strip()
        if raw_href.startswith("//"):
            link = "https:" + raw_href
        elif raw_href.startswith("http://") or raw_href.startswith("https://"):
            link = raw_href
        elif raw_href.startswith("/"):
            # assume same host as base_url
            # crude host extraction
            host_match = re.match(r"(https?://[^/]+)", base_url)
            host = host_match.group(1) if host_match else "https://www.sbahq.org"
            link = host + raw_href
        else:
            if raw_href.startswith("www."):
                link = "https://" + raw_href
            else:
                link = raw_href

    warnings.append(
        f"[CBA DEBUG] parsed_range={start_date}..{end_date} location='{location}' link='{link}' (v2026-01-19c)"
    )
    warnings.append("[CBA DEBUG] scraper version v2026-01-19c")

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
                "snippet": block_flat[:300],
                "field": "agenda_block",
            },
            "source": "scraped",
        }
    ]

    return events, warnings
