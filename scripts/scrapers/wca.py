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

VERSION = "v2026-01-18e"


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


def scrape_wca(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Scrape WCA key dates from wcacongress.org (Programme page).

    Extremely tolerant approach:

      1) Strip all HTML tags -> plain text.
      2) On the full text:
         - Congress: first "dd .. dd Month YYYY" range.
         - Deadlines: "dd Month YYYY – label".
      3) If parsing still fails, include candidate snippets in warnings.
    """
    warnings: List[str] = []
    urls = cfg.get("urls") or []
    if not urls:
        return [], [f"[WCA] No URLs configured in sources.json. ({VERSION})"]

    base_url = urls[0]
    location = cfg.get("location", "Marrakech, Morocco")

    try:
        html = _fetch(base_url)
    except Exception as e:  # pragma: no cover - network
        return [], [f"[WCA] Failed to fetch {base_url}: {e} ({VERSION})"]

    # 1) Strip all tags
    text_no_tags = re.sub(r"<[^>]+>", " ", html)

    # 2) Collapse whitespace
    text = re.sub(r"\s+", " ", text_no_tags, flags=re.DOTALL).strip()

    events: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Congress: tolerate any non-digit / punctuation between day numbers
    # Example targets:
    #   "15-19 April 2026 – Congress"
    #   "15 – 19 April 2026 – Congress"
    # We DO NOT require the word "Congress" anymore.
    # ------------------------------------------------------------------
    cong_pattern = re.compile(
        r"(\d{1,2})\s*[^0-9A-Za-z]{1,3}\s*(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})",
        re.IGNORECASE,
    )

    m_cong = cong_pattern.search(text)
    congress_year: int | None = None

    if m_cong:
        d1 = int(m_cong.group(1))
        d2 = int(m_cong.group(2))
        month_name = m_cong.group(3).lower()
        year = int(m_cong.group(4))

        mnum = MONTHS_EN.get(month_name)
        if mnum is None:
            warnings.append(
                f"[WCA] Unknown month in congress date: '{month_name}' ({VERSION})"
            )
        else:
            congress_year = year
            start_date = _ymd(year, mnum, d1)
            end_date = _ymd(year, mnum, d2)

            events.append(
                {
                    "series": "WCA",
                    "year": year,
                    "type": "congress",
                    "start_date": start_date,
                    "end_date": end_date,
                    "location": location,
                    "link": base_url,
                    "priority": 9,
                    "title": {
                        "en": f"WCA {year} — World Congress of Anaesthesiologists",
                        "pt": f"WCA {year} — Congresso Mundial de Anestesiologia",
                    },
                    "evidence": {
                        "url": base_url,
                        "snippet": m_cong.group(0),
                        "field": "congress_range_tolerant",
                    },
                    "source": "scraped",
                }
            )
    else:
        warnings.append(
            f"[WCA] Could not find any 'dd .. dd Month YYYY' congress range. ({VERSION})"
        )

    # ------------------------------------------------------------------
    # Deadlines: "dd Month YYYY – label"
    # Very tolerant: we only assume that the next date or end-of-text
    # marks the end of the label.
    # ------------------------------------------------------------------
    deadline_pattern = re.compile(
        r"(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})\s*[–\-]\s*([^0-9]+?)(?=("
        r"\d{1,2}\s+[A-Za-z]+\s+20\d{2}\s*[–\-]|"
        r"\d{1,2}\s*[^0-9A-Za-z]{1,3}\s*\d{1,2}\s+[A-Za-z]+\s+20\d{2}|$"
        r"))",
        re.IGNORECASE,
    )

    def _map_label(label: str) -> Tuple[str | None, str | None, str | None]:
        l = re.sub(r"\s+", " ", label).strip().lower()

        if "abstract" in l and ("deadline" in l or "submission" in l):
            return (
                "abstract_deadline",
                "Abstract submission deadline",
                "Prazo final de submissão de resumos",
            )

        if ("early bird" in l or "early-bird" in l) and "registration" in l:
            return (
                "early_bird_deadline",
                "Early-bird registration deadline",
                "Prazo de inscrição early-bird",
            )

        if "regular" in l and "registration" in l:
            return (
                "registration_deadline",
                "Regular registration deadline",
                "Prazo de inscrição regular",
            )

        if "registration" in l and "deadline" in l:
            return (
                "registration_deadline",
                "Registration deadline",
                "Prazo de inscrição",
            )

        return None, None, None

    deadline_matches = list(deadline_pattern.finditer(text))

    for m in deadline_matches:
        day = int(m.group(1))
        month_name = m.group(2).lower()
        year = int(m.group(3))
        label_raw = m.group(4).strip()

        month = MONTHS_EN.get(month_name)
        if not month:
            warnings.append(
                f"[WCA] Unknown month in key date: '{month_name}' ({VERSION})"
            )
            continue

        date_ymd = _ymd(year, month, day)
        etype, title_en_tail, title_pt_tail = _map_label(label_raw)
        if not etype:
            # Unknown label — we don't guess.
            continue

        year_for_event = congress_year or year

        events.append(
            {
                "series": "WCA",
                "year": year_for_event,
                "type": etype,
                "date": date_ymd,
                "location": location,
                "link": base_url,
                "priority": 8,
                "title": {
                    "en": f"WCA {year_for_event} — {title_en_tail}",
                    "pt": f"WCA {year_for_event} — {title_pt_tail}",
                },
                "evidence": {
                    "url": base_url,
                    "snippet": m.group(0),
                    "field": "deadline_line_tolerant",
                },
                "source": "scraped",
            }
        )

    # ------------------------------------------------------------------
    # Debug information if still nothing matched
    # ------------------------------------------------------------------
    if not events:
        # Show a few candidate date snippets so we can see what the bot sees.
        range_candidates = re.findall(
            r"\d{1,2}[^0-9]{1,3}\d{1,2}\s+[A-Za-z]+\s+20\d{2}", text
        )[:3]
        single_candidates = re.findall(
            r"\d{1,2}\s+[A-Za-z]+\s+20\d{2}", text
        )[:5]

        warnings.append(
            f"[WCA] No events produced from page. Candidate ranges: {range_candidates} ({VERSION})"
        )
        warnings.append(
            f"[WCA] Candidate single dates: {single_candidates} ({VERSION})"
        )

    warnings.append(f"[WCA DEBUG] scraper version {VERSION}")
    warnings.append(
        f"[WCA DEBUG] deadline_matches={len(deadline_matches)} "
        f"congress_found={bool(m_cong)}"
    )

    return events, warnings
