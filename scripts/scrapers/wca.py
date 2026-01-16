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
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; AnesthesiaCalendarBot/1.0; "
            "+https://helenopaiva.github.io/AnesthesiaCalendar/)"
        )
    }
    req = Request(url, headers=headers)
    with urlopen(req, timeout=20) as resp:  # nosec
        raw = resp.read()
    return raw.decode("utf-8", errors="ignore")


def _ymd(y: int, m: int, d: int) -> str:
    return f"{y:04d}-{m:02d}-{d:02d}"


def scrape_wca(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    urls = cfg.get("urls") or []
    if not urls:
        return [], ["[WCA] No URLs configured in sources.json."]

    base_url = urls[0]
    try:
        html = _fetch(base_url)
    except Exception as e:  # pragma: no cover
        return [], [f"[WCA] Failed to fetch {base_url}: {e}"]

    text = re.sub(r"\s+", " ", html, flags=re.DOTALL)

    events: List[Dict[str, Any]] = []

    # --- Congress dates from "15-19 April 2026 – Congress" ------------------
    m_cong = re.search(
        r"(\d{1,2})-(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})\s*[\u2013\-]\s*Congress",
        text,
        flags=re.IGNORECASE,
    )
    if m_cong:
        d1 = int(m_cong.group(1))
        d2 = int(m_cong.group(2))
        month_name = m_cong.group(3).lower()
        year = int(m_cong.group(4))

        mnum = MONTHS_EN.get(month_name)
        if mnum:
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
                    "priority": 10,
                    "title": {
                        "en": "WCA 2026 — World Congress of Anaesthesiologists",
                        "pt": "WCA 2026 — Congresso Mundial de Anestesiologia",
                    },
                    "source": "scraped",
                }
            )
        else:
            warnings.append(f"[WCA] Unknown month in congress date: {month_name}")
    else:
        warnings.append("[WCA] Could not find '15-19 April 2026 – Congress' pattern on wcacongress.org.")

    # --- Key dates block ----------------------------------------------------
    key_block_match = re.search(
        r"Key Dates(.*?)(?:Subscribe to the WCA mailing list|#WCA2026)",
        text,
        flags=re.IGNORECASE,
    )
    if not key_block_match:
        warnings.append("[WCA] Could not locate 'Key Dates' block on wcacongress.org.")
        return events, warnings

    key_block = key_block_match.group(1)

    entry_pattern = re.compile(
        r"(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})\s*[\u2013\-]\s*([^0-9]+?)(?=(\d{1,2}\s+[A-Za-z]+\s+20\d{2}\s*[\u2013\-]|$))",
        re.IGNORECASE,
    )

    for m in entry_pattern.finditer(key_block):
        day = int(m.group(1))
        month_name = m.group(2).lower()
        year = int(m.group(3))
        label = m.group(4).strip()

        month = MONTHS_EN.get(month_name)
        if not month:
            warnings.append(f"[WCA] Unknown month in key date: {month_name}")
            continue

        date_ymd = _ymd(year, month, day)
        lower = label.lower()

        if "abstract" in lower:
            etype = "abstract_deadline"
            title_en = "WCA 2026 — Abstract submission deadline"
            title_pt = "WCA 2026 — Prazo final de submissão de resumos"
        elif "early bird" in lower:
            etype = "early_bird_deadline"
            title_en = "WCA 2026 — Early-bird registration deadline"
            title_pt = "WCA 2026 — Prazo de inscrição early-bird"
        elif "regular registration" in lower:
            etype = "registration_deadline"
            title_en = "WCA 2026 — Regular registration deadline"
            title_pt = "WCA 2026 — Prazo de inscrição regular"
        elif "congress" in lower:
            # This is the same line used for congress; we already created that.
            continue
        else:
            # Unknown label – skip rather than guessing.
            continue

        events.append(
            {
                "series": "WCA",
                "year": 2026,
                "type": etype,
                "date": date_ymd,
                "location": "Marrakech, Morocco",
                "link": base_url,
                "priority": 9,
                "title": {"en": title_en, "pt": title_pt},
                "source": "scraped",
            }
        )

    if not events:
        warnings.append("[WCA] No events produced from wcacongress.org (regex likely needs update).")

    return events, warnings
