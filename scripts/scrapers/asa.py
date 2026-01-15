from __future__ import annotations

from typing import Any, Dict, List, Tuple


def scrape_asa(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Static ASA 2026 data (zero network calls, very stable).

    Once ANESTHESIOLOGY 2027+ details are available and we feel like fighting
    with anti-bot / HTML changes, we can reintroduce the HTTP-based scraper.

    Source (for the hard-coded dates):
      - ANESTHESIOLOGY 2026 official page (San Diego, Oct 16–20, 2026)
      - ASA submission info: Scientific Abstracts Jan 6 – Mar 31, 2026
    """

    events: List[Dict[str, Any]] = []
    warnings: List[str] = []

    # Congress main dates
    events.append(
        {
            "series": "ASA",
            "year": 2026,
            "type": "congress",
            "start_date": "2026-10-16",
            "end_date": "2026-10-20",
            "location": "San Diego, CA, USA",
            "link": "https://www.asahq.org/meetings/anesthesiology-annual-meeting",
            "priority": 10,
            "title": {
                "en": "ANESTHESIOLOGY 2026 — ASA Annual Meeting",
                "pt": "ANESTHESIOLOGY 2026 — Congresso anual da ASA",
            },
        }
    )

    # Scientific abstracts window → mapped to abstract_open / abstract_deadline
    events.append(
        {
            "series": "ASA",
            "year": 2026,
            "type": "abstract_open",
            "date": "2026-01-06",
            "location": "—",
            "link": "https://www.asahq.org/annualmeeting/education/submissions",
            "priority": 10,
            "title": {
                "en": "ASA 2026 — Scientific abstracts open",
                "pt": "ASA 2026 — Abertura de resumos científicos",
            },
        }
    )

    events.append(
        {
            "series": "ASA",
            "year": 2026,
            "type": "abstract_deadline",
            "date": "2026-03-31",
            "location": "—",
            "link": "https://www.asahq.org/annualmeeting/education/submissions",
            "priority": 10,
            "title": {
                "en": "ASA 2026 — Scientific abstracts deadline",
                "pt": "ASA 2026 — Prazo final resumos científicos",
            },
        }
    )

    # Optional comment so you remember why it doesn't scrape yet
    warnings.append(
        "ASA scraper is currently static for ANESTHESIOLOGY 2026 "
        "(no network calls). Update this file when 2027+ dates are available."
    )

    return events, warnings
