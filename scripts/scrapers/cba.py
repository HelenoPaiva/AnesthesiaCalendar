# scripts/scrapers/cba.py

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple
from urllib.request import Request, urlopen


VERSION = "v2026-01-19d"

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
    Year-agnostic CBA scraper (VERSION).

    Target structure (e.g. https://www.sbahq.org/agenda/congresso-brasileiro-de-anestesiologia/):

        <h1 class="page-title">Congresso Brasileiro de Anestesiologia</h1>
        <div id="programa">
          <div class="detalhes mb-5">
            <div class="data"><i class="icon data"></i>26 a 29 de novembro de 2026</div>
            <div class="local"><i class="icon local"></i>Fortaleza - CE</div>
            <div class="local"><i class="icon2 presencial"></i>Presencial</div>
            <div class="envent-action">
              <a href="https://www.cba2026.com.br/" ...>Inscreva-se</a>
              <a href="https://www.cba2026.com.br/" ...>Site</a>
            </div>
          </div>
        </div>
    """
    warnings: List[str] = []

    urls = cfg.get("urls") or []
    if not urls:
        return [], [f"[CBA] No URLs configured in sources.json. ({VERSION})"]

    base_url = urls[0]

    try:
        html = _fetch(base_url)
    except Exception as e:  # pragma: no cover - network
        return [], [f"[CBA] Failed to fetch {base_url}: {e} ({VERSION})"]

    # ------------------------------------------------------------------
    # 1) Locate the <h1> page title for CBA in a tolerant way:
    #    - class contains "page-title"
    #    - inner text contains "Congresso Brasileiro de Anestesiologia"
    # ------------------------------------------------------------------
    title_pattern = re.compile(
        r'(<h1[^>]*class="[^"]*page-title[^"]*"[^>]*>.*?Congresso\s+Brasileiro\s+de\s+Anestesiologia.*?</h1>)(.{0,3000})',
        re.IGNORECASE | re.DOTALL,
    )

    m_title = title_pattern.search(html)
    if not m_title:
        # As a fallback, try to show a small snippet around the plain-text phrase,
        # if it exists at all, to help debug.
        low = html.lower()
        phrase = "congresso brasileiro de anestesiologia"
        idx = low.find(phrase)
        if idx != -1:
            snippet = re.sub(r"\s+", " ", html[max(0, idx - 100) : idx + 200])
            warnings.append(
                f"[CBA DEBUG] fallback_snippet='{snippet[:200]}' ({VERSION})"
            )
        warnings.append(
            f"[CBA] Could not locate <h1 ... page-title> for 'Congresso Brasileiro de Anestesiologia'. ({VERSION})"
        )
        return [], warnings

    title_html = m_title.group(1)
    tail_html = m_title.group(2)
    block_html = title_html + tail_html
    block_flat = re.sub(r"\s+", " ", block_html, flags=re.DOTALL)

    warnings.append(
        f"[CBA DEBUG] block_sample='{block_flat[:200]}' ({VERSION})"
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
            f"[CBA] Could not parse CBA date range in agenda block. ({VERSION})"
        )
        return [], warnings

    d1 = int(m_date.group(1))
    d2 = int(m_date.group(2))
    month_name = m_date.group(3).lower()
    year = int(m_date.group(4))

    month_num = MONTHS_PT.get(month_name)
    if not month_num:
        warnings.append(
            f"[CBA] Unknown month name in CBA date range: '{month_name}'. ({VERSION})"
        )
        return [], warnings

    start_date = _ymd(year, month_num, d1)
    end_date = _ymd(year, month_num, d2)

    # ------------------------------------------------------------------
    # 3) Extract location.
    #    Prefer strict pattern with icon local; if that fails, fallback to any 'local' div.
    # ------------------------------------------------------------------
    m_loc_strict = re.search(
        r'<div\s+class="local">\s*<i[^>]*class="icon\s+local"[^>]*></i>\s*([^<]+)</div>',
        block_html,
        flags=re.IGNORECASE,
    )
    location = None
    if m_loc_strict:
        location = m_loc_strict.group(1).strip()
    else:
        m_loc_any = re.search(
            r'<div\s+class="local">([^<]+)</div>',
            block_html,
            flags=re.IGNORECASE,
        )
        if m_loc_any:
            location = m_loc_any.group(1).strip()

    if not location:
        location = "Brasil"

    # ------------------------------------------------------------------
    # 4) Extract CBA site link from Inscreva-se / Site buttons.
    # ------------------------------------------------------------------
    link = base_url
    m_link = re.search(
        r'href="([^"]+)"[^>]*>\s*(?:Inscreva-se|Site)\s*</a>',
        block_html,
        flags=re.IGNORECASE,
    )
    if m_link:
        raw_href = m_link.group(1).strip()
        if raw_href.startswith("//"):
            link = "https:" + raw_href
        elif raw_href.startswith("http://") or raw_href.startswith("https://"):
            link = raw_href
        elif raw_href.startswith("/"):
            host_match = re.match(r"(https?://[^/]+)", base_url)
            host = host_match.group(1) if host_match else "https://www.sbahq.org"
            link = host + raw_href
        else:
            if raw_href.startswith("www."):
                link = "https://" + raw_href
            else:
                link = raw_href

    warnings.append(
        f"[CBA DEBUG] parsed_range={start_date}..{end_date} location='{location}' link='{link}' ({VERSION})"
    )
    warnings.append(f"[CBA DEBUG] scraper version {VERSION}")

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
