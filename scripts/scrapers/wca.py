# scripts/scrapers/wca.py

from __future__ import annotations

import re
from html.parser import HTMLParser
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


def _norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _parse_single_date(date_text: str) -> str | None:
    """
    Parse '30 September 2025' into YYYY-MM-DD.
    """
    s = _norm_space(date_text)
    m = re.match(r"^(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})$", s)
    if not m:
        return None
    d = int(m.group(1))
    mon = m.group(2).lower()
    y = int(m.group(3))
    mnum = MONTHS_EN.get(mon)
    if not mnum:
        return None
    return _ymd(y, mnum, d)


def _parse_range_date(date_text: str) -> Tuple[str | None, str | None, int | None]:
    """
    Parse '15-19 April 2026' (or '15–19 April 2026') into (start_ymd, end_ymd, year).
    """
    s = _norm_space(date_text)
    # Accept hyphen or en dash between day numbers
    m = re.match(r"^(\d{1,2})\s*[-–]\s*(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})$", s)
    if not m:
        return None, None, None
    d1 = int(m.group(1))
    d2 = int(m.group(2))
    mon = m.group(3).lower()
    y = int(m.group(4))
    mnum = MONTHS_EN.get(mon)
    if not mnum:
        return None, None, None
    return _ymd(y, mnum, d1), _ymd(y, mnum, d2), y


def _map_label_to_type(label: str) -> Tuple[str | None, str | None, str | None]:
    """
    Map WCA key-date label -> (etype, title_en_tail, title_pt_tail)
    Returns (None, None, None) when unknown.
    """
    l = _norm_space(label).lower()

    # Make matching resilient to minor wording changes
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

    # If they rename to something like "Standard Registration Deadline"
    if ("standard" in l or "general" in l) and "registration" in l and "deadline" in l:
        return (
            "registration_deadline",
            "Registration deadline",
            "Prazo de inscrição",
        )

    return None, None, None


class _KeyDatesExtractor(HTMLParser):
    """
    Robustly extract Key Dates entries from WordPress block HTML.

    Strategy:
    - Find heading tag (h1-h6) whose text == "Key Dates" (case-insensitive).
    - Once found, capture subsequent <p> text within the SAME nearest ancestor <div>.
      (This matches the outerHTML you provided: a div column containing h4 + p lines.)
    - Each <p> has a <strong>DATE</strong> followed by '– Label'.
    """

    def __init__(self) -> None:
        super().__init__()
        self.stack: List[str] = []
        self._capture_active = False
        self._capture_div_depth: int | None = None

        self._in_heading = False
        self._heading_text_parts: List[str] = []

        self._in_p = False
        self._p_text_parts: List[str] = []

        self._in_strong = False
        self._strong_text_parts: List[str] = []

        self.items: List[Dict[str, str]] = []
        self.found_heading = False

    def handle_starttag(self, tag: str, attrs) -> None:
        self.stack.append(tag)

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._in_heading = True
            self._heading_text_parts = []

        if self._capture_active and tag == "p":
            self._in_p = True
            self._p_text_parts = []
            self._strong_text_parts = []
            self._in_strong = False

        if self._capture_active and self._in_p and tag == "strong":
            self._in_strong = True
            self._strong_text_parts = []

    def handle_endtag(self, tag: str) -> None:
        # Close heading: decide if it is the Key Dates anchor
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self._in_heading:
            self._in_heading = False
            heading_text = _norm_space("".join(self._heading_text_parts))
            if heading_text.lower() == "key dates":
                self.found_heading = True
                # Capture within nearest ancestor div
                # Find nearest 'div' in current stack (excluding the heading tag which is ending)
                # stack currently still includes the heading tag; after pop it won't, but we can search now.
                try:
                    # find nearest div from the end
                    idx_from_end = len(self.stack) - 1 - self.stack[::-1].index("div")
                    self._capture_div_depth = idx_from_end + 1  # depth length at that div
                except ValueError:
                    # No ancestor div; fallback: capture within parent element depth
                    self._capture_div_depth = max(len(self.stack) - 1, 1)

                self._capture_active = True

        # Close <strong>
        if self._capture_active and self._in_p and tag == "strong" and self._in_strong:
            self._in_strong = False

        # Close <p>: store item if it has a strong date and some text
        if self._capture_active and tag == "p" and self._in_p:
            self._in_p = False
            full_p = _norm_space("".join(self._p_text_parts))
            strong = _norm_space("".join(self._strong_text_parts))

            if strong and full_p:
                # label = remove the strong date from the start, then strip separators
                label = full_p
                if label.startswith(strong):
                    label = label[len(strong) :].strip()
                # Strip common separators (en dash, hyphen, em dash)
                label = re.sub(r"^[-–—]\s*", "", label).strip()

                self.items.append({"date_text": strong, "label": label})

        # Pop stack and check if we left capture container
        if self.stack:
            self.stack.pop()

        if self._capture_active and self._capture_div_depth is not None:
            # When the stack becomes shorter than the capture div depth,
            # we've left the container that held Key Dates.
            if len(self.stack) < self._capture_div_depth:
                self._capture_active = False

    def handle_data(self, data: str) -> None:
        if self._in_heading:
            self._heading_text_parts.append(data)

        if self._capture_active and self._in_p:
            self._p_text_parts.append(data)
            if self._in_strong:
                self._strong_text_parts.append(data)


def scrape_wca(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Scrape WCA key dates from wcacongress.org.

    Robust approach:
      - Parse HTML and locate a heading whose text is "Key Dates".
      - Read <p> lines within the same container div.
      - Parse <strong>DATE</strong> – Label pattern.
      - Extract congress range and deadlines.
    """
    warnings: List[str] = []
    urls = cfg.get("urls") or []
    if not urls:
        return [], ["[WCA] No URLs configured in sources.json."]

    base_url = urls[0]

    try:
        html = _fetch(base_url)
    except Exception as e:  # pragma: no cover - network
        return [], [f"[WCA] Failed to fetch {base_url}: {e}"]

    parser = _KeyDatesExtractor()
    parser.feed(html)

    if not parser.found_heading or not parser.items:
        warnings.append("[WCA] Could not locate 'Key Dates' entries on wcacongress.org.")
        return [], warnings

    # Identify congress range line (label contains 'Congress')
    congress_year: int | None = None
    congress_start: str | None = None
    congress_end: str | None = None

    for it in parser.items:
        if "congress" in it["label"].lower():
            start_ymd, end_ymd, y = _parse_range_date(it["date_text"])
            if start_ymd and end_ymd and y:
                congress_year = y
                congress_start = start_ymd
                congress_end = end_ymd
            break

    events: List[Dict[str, Any]] = []

    # Create congress event if found
    if congress_year and congress_start and congress_end:
        events.append(
            {
                "series": "WCA",
                "year": congress_year,
                "type": "congress",
                "start_date": congress_start,
                "end_date": congress_end,
                "location": "—",  # Do not hardcode city; page block does not provide one
                "link": base_url,
                "priority": 9,
                "title": {
                    "en": f"WCA {congress_year} — World Congress of Anaesthesiologists",
                    "pt": f"WCA {congress_year} — Congresso Mundial de Anestesiologia",
                },
                "evidence": {
                    "url": base_url,
                    "snippet": f"{it['date_text']} — {it['label']}",
                    "field": "key_dates_block",
                },
                "source": "scraped",
            }
        )
    else:
        warnings.append("[WCA] Found 'Key Dates' but could not parse congress date range.")

    # Parse deadline lines
    for it in parser.items:
        date_text = it["date_text"]
        label = it["label"]

        # Skip the congress line (already handled)
        if "congress" in label.lower():
            continue

        iso = _parse_single_date(date_text)
        if not iso:
            # Sometimes WordPress editors change format; warn but keep going
            warnings.append(f"[WCA] Unparsed date format: '{date_text}'")
            continue

        etype, title_en_tail, title_pt_tail = _map_label_to_type(label)
        if not etype:
            # Unknown label; ignore (future-proof against new items we don't want)
            continue

        # Tie deadlines to the congress year if found; otherwise use parsed year from the ISO date
        year_for_event = congress_year or int(iso[:4])

        events.append(
            {
                "series": "WCA",
                "year": year_for_event,
                "type": etype,
                "date": iso,
                "location": "—",
                "link": base_url,
                "priority": 8,
                "title": {
                    "en": f"WCA {year_for_event} — {title_en_tail}",
                    "pt": f"WCA {year_for_event} — {title_pt_tail}",
                },
                "evidence": {
                    "url": base_url,
                    "snippet": f"{date_text} — {label}",
                    "field": "key_dates_block",
                },
                "source": "scraped",
            }
        )

    if not events:
        warnings.append("[WCA] No events produced (Key Dates found but nothing parsed/mapped).")

    return events, warnings
