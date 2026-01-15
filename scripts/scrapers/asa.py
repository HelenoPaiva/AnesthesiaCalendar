from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional

from scripts.scrapers.http import fetch_text


MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def _norm_month(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.strip().lower())


def _ymd(month: str, day: str, year: str) -> str:
    m = MONTHS[_norm_month(month)]
    d = int(day)
    y = int(year)
    return f"{y:04d}-{m:02d}-{d:02d}"


@dataclass
class Candidate:
    value: Any
    trust: int
    role: str
    url: str
    snippet: str


def _best_candidate(cands: List[Candidate]) -> Optional[Candidate]:
    if not cands:
        return None
    return sorted(cands, key=lambda c: c.trust, reverse=True)[0]


def _collect_conflicts(cands: List[Candidate], chosen: Candidate) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for c in cands:
        if c.value != chosen.value:
            out.append({
                "value": c.value,
                "trust": c.trust,
                "role": c.role,
                "url": c.url,
                "snippet": c.snippet[:220]
            })
    return out


def _find_meeting_range(text: str) -> Optional[Tuple[Tuple[str, str], str]]:
    """
    Finds ranges like:
      "October 16-20, 2026"
      "October 16–20, 2026"
      "Oct 16–20, 2026"
    Returns ((start_ymd, end_ymd), matched_snippet)
    """
    m = re.search(
        r"\b([A-Za-z]{3,9})\s+(\d{1,2})\s*[-–—]\s*(\d{1,2}),\s*(\d{4})\b",
        text
    )
    if not m:
        return None
    month, d1, d2, year = m.group(1), m.group(2), m.group(3), m.group(4)
    return (_ymd(month, d1, year), _ymd(month, d2, year)), m.group(0)


def _find_scientific_abstracts_window(text: str) -> Optional[Tuple[Tuple[str, str], str]]:
    """
    Finds a window like:
      "Scientific Abstracts Jan 6-Mar 31, 2026"
      "Scientific Abstracts January 6 – March 31, 2026"
    Returns ((open_ymd, close_ymd), matched_snippet)
    """
    # Allow: "Scientific Abstracts Jan6-Mar 31, 2026" and variants with spaces/dashes
    # Capture month/day (start) and month/day/year (end); start year inferred as end year if omitted
    pattern = (
        r"Scientific\s+Abstracts.*?"
        r"([A-Za-z]{3,9})\s*([0-9]{1,2})"
        r"(?:,\s*([0-9]{4}))?"
        r"\s*[-–—]\s*"
        r"([A-Za-z]{3,9})\s*([0-9]{1,2}),\s*([0-9]{4})"
    )
    m = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return None

    sm, sd, sy_opt, em, ed, ey = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5), m.group(6)
    sy = sy_opt if sy_opt else ey

    open_ymd = _ymd(sm, sd, sy)
    close_ymd = _ymd(em, ed, ey)
    return (open_ymd, close_ymd), m.group(0).strip()


def _find_general_open_close(text: str) -> Optional[Tuple[Tuple[str, str], str]]:
    """
    Institutional style:
      "General session submissions for ASA 2026 ... are open from August 26 until November 13, 2025."
    Returns ((open_ymd, close_ymd), matched_snippet)
    """
    m = re.search(
        r"General session submissions for ASA\s*2026.*?open from\s+([A-Za-z]{3,9})\s+(\d{1,2})\s+until\s+([A-Za-z]{3,9})\s+(\d{1,2}),\s*(\d{4})",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )
    if not m:
        return None

    m1, d1, m2, d2, y2 = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
    y1 = y2  # good enough for Aug->Nov 2025
    return (_ymd(m1, d1, y1), _ymd(m2, d2, y2)), m.group(0).strip()


def _find_named_window(text: str, label: str) -> Optional[Tuple[Tuple[str, str], str]]:
    """
    Institutional style:
      "PBLD Dec 2, 2025- Feb 23, 2026"
      "Medically Challenging Cases Feb 3-April 28, 2026"
    Returns ((open_ymd, close_ymd), matched_snippet)
    """
    pattern = (
        rf"{re.escape(label)}\s+"
        r"([A-Za-z]{3,9})\s*([0-9]{1,2})(?:,\s*([0-9]{4}))?"
        r"\s*[-–—]\s*"
        r"([A-Za-z]{3,9})\s*([0-9]{1,2}),\s*([0-9]{4})"
    )
    m = re.search(pattern, text, flags=re.IGNORECASE)
    if not m:
        return None

    sm, sd, sy_opt, em, ed, ey = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5), m.group(6)
    sy = sy_opt if sy_opt else ey
    return (_ymd(sm, sd, sy), _ymd(em, ed, ey)), m.group(0).strip()


def _iter_sources(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Supports:
      - new: cfg["sources"] = [{role, trust, url}, ...]
      - old: cfg["urls"] = [url, ...]  -> will be treated as role="unknown", trust=10
    """
    srcs = cfg.get("sources")
    out: List[Dict[str, Any]] = []

    if isinstance(srcs, list) and srcs:
        for s in srcs:
            if not isinstance(s, dict):
                continue
            url = str(s.get("url", "")).strip()
            if not url:
                continue
            out.append({
                "url": url,
                "role": str(s.get("role", "unknown")).strip() or "unknown",
                "trust": int(s.get("trust", 10)) if str(s.get("trust", "")).isdigit() else 10,
            })
    else:
        urls = cfg.get("urls", []) or []
        for u in urls:
            out.append({"url": str(u), "role": "unknown", "trust": 10})

    # high trust first
    out.sort(key=lambda x: x["trust"], reverse=True)
    return out


def scrape_asa(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    events: List[Dict[str, Any]] = []

    sources = _iter_sources(cfg)
    if not sources:
        return [], ["No source URLs configured for ASA in data/sources.json."]

    meeting_cands: List[Candidate] = []
    sci_cands: List[Candidate] = []
    general_cands: List[Candidate] = []
    pbld_cands: List[Candidate] = []
    mcc_cands: List[Candidate] = []

    for src in sources:
        url = src["url"]
        role = src["role"]
        trust = src["trust"]

        try:
            text, _ct = fetch_text(url)
        except Exception as e:
            warnings.append(f"Fetch failed ({role}, trust={trust}) for {url}: {e}")
            continue

        # Meeting range is “portable”: many sources include it.
        if role in {"official_meeting", "institutional", "wfsa", "tourism", "unknown"}:
            mr = _find_meeting_range(text)
            if mr:
                (start_ymd, end_ymd), snippet = mr
                meeting_cands.append(Candidate((start_ymd, end_ymd), trust, role, url, snippet))

        # Scientific abstracts window: best from official submissions, but can exist in institutional
        if role in {"official_submissions", "institutional", "unknown"}:
            sw = _find_scientific_abstracts_window(text)
            if sw:
                (open_ymd, close_ymd), snippet = sw
                sci_cands.append(Candidate((open_ymd, close_ymd), trust, role, url, snippet))

        # These (general/PBLD/MCC) currently only from institutional in our known sources
        if role in {"institutional", "unknown"}:
            gen = _find_general_open_close(text)
            if gen:
                (open_ymd, close_ymd), snippet = gen
                general_cands.append(Candidate((open_ymd, close_ymd), trust, role, url, snippet))

            pbld = _find_named_window(text, "PBLD")
            if pbld:
                (open_ymd, close_ymd), snippet = pbld
                pbld_cands.append(Candidate((open_ymd, close_ymd), trust, role, url, snippet))

            mcc = _find_named_window(text, "Medically Challenging Cases")
            if mcc:
                (open_ymd, close_ymd), snippet = mcc
                mcc_cands.append(Candidate((open_ymd, close_ymd), trust, role, url, snippet))

    # Choose best per datum + attach conflicts/evidence
    meeting_best = _best_candidate(meeting_cands)
    sci_best = _best_candidate(sci_cands)
    general_best = _best_candidate(general_cands)
    pbld_best = _best_candidate(pbld_cands)
    mcc_best = _best_candidate(mcc_cands)

    if meeting_best:
        start_ymd, end_ymd = meeting_best.value
        ev = {
            "series": "ASA",
            "year": 2026,
            "type": "congress",
            "start_date": start_ymd,
            "end_date": end_ymd,
            "location": "San Diego, CA, USA",
            "link": meeting_best.url,
            "priority": 10,
            "evidence": {
                "role": meeting_best.role,
                "trust": meeting_best.trust,
                "url": meeting_best.url,
                "snippet": meeting_best.snippet[:220]
            }
        }
        conflicts = _collect_conflicts(meeting_cands, meeting_best)
        if conflicts:
            ev["conflicts"] = {"meeting_range": conflicts}
        events.append(ev)
    else:
        warnings.append("Could not extract ASA 2026 meeting date range from any source.")

    if sci_best:
        open_ymd, close_ymd = sci_best.value

        conflicts = _collect_conflicts(sci_cands, sci_best)
        conflict_obj = {"scientific_abstracts_window": conflicts} if conflicts else None

        ev_open = {
            "series": "ASA",
            "year": 2026,
            "type": "abstract_open",
            "date": open_ymd,
            "location": "—",
            "link": sci_best.url,
            "priority": 10,
            "title": {
                "en": "ASA 2026 — Scientific abstracts open",
                "pt": "ASA 2026 — Abertura de resumos científicos"
            },
            "evidence": {
                "role": sci_best.role,
                "trust": sci_best.trust,
                "url": sci_best.url,
                "snippet": sci_best.snippet[:220]
            }
        }
        if conflict_obj:
            ev_open["conflicts"] = conflict_obj

        ev_close = {
            "series": "ASA",
            "year": 2026,
            "type": "abstract_deadline",
            "date": close_ymd,
            "location": "—",
            "link": sci_best.url,
            "priority": 10,
            "title": {
                "en": "ASA 2026 — Scientific abstracts deadline",
                "pt": "ASA 2026 — Prazo final resumos científicos"
            },
            "evidence": {
                "role": sci_best.role,
                "trust": sci_best.trust,
                "url": sci_best.url,
                "snippet": sci_best.snippet[:220]
            }
        }
        if conflict_obj:
            ev_close["conflicts"] = conflict_obj

        events.extend([ev_open, ev_close])
    else:
        warnings.append("Could not extract Scientific Abstracts submission window from any source.")

    # Optional extras (institutional-only right now)
    def add_open_close(best: Optional[Candidate], open_title: Dict[str, str], close_title: Dict[str, str], priority: int):
        if not best:
            return
        open_ymd, close_ymd = best.value
        events.append({
            "series": "ASA",
            "year": 2026,
            "type": "other_deadline",
            "date": open_ymd,
            "location": "—",
            "link": best.url,
            "priority": priority,
            "title": open_title,
            "evidence": {"role": best.role, "trust": best.trust, "url": best.url, "snippet": best.snippet[:220]}
        })
        events.append({
            "series": "ASA",
            "year": 2026,
            "type": "other_deadline",
            "date": close_ymd,
            "location": "—",
            "link": best.url,
            "priority": priority,
            "title": close_title,
            "evidence": {"role": best.role, "trust": best.trust, "url": best.url, "snippet": best.snippet[:220]}
        })

    add_open_close(
        general_best,
        {"en": "ASA 2026 — General session submissions open", "pt": "ASA 2026 — Abertura submissões (sessões gerais)"},
        {"en": "ASA 2026 — General session submissions deadline", "pt": "ASA 2026 — Prazo final (sessões gerais)"},
        priority=8
    )

    add_open_close(
        pbld_best,
        {"en": "ASA 2026 — PBLD submissions open", "pt": "ASA 2026 — Abertura submissões PBLD"},
        {"en": "ASA 2026 — PBLD submissions deadline", "pt": "ASA 2026 — Prazo final submissões PBLD"},
        priority=7
    )

    add_open_close(
        mcc_best,
        {"en": "ASA 2026 — Medically challenging cases open", "pt": "ASA 2026 — Abertura casos desafiadores"},
        {"en": "ASA 2026 — Medically challenging cases deadline", "pt": "ASA 2026 — Prazo final casos desafiadores"},
        priority=6
    )

    return events, warnings
