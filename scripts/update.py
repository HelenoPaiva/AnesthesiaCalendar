from __future__ import annotations

import json
import hashlib
import importlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


# -----------------------------------------------------------------------------
# Paths & helpers
# -----------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

EVENTS_PATH = DATA_DIR / "events.json"
LEDGER_PATH = DATA_DIR / "ledger.json"
SOURCES_PATH = DATA_DIR / "sources.json"
MANUAL_OVERRIDES_PATH = DATA_DIR / "manual_overrides.json"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return default


def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


# -----------------------------------------------------------------------------
# ID generation
# -----------------------------------------------------------------------------

def _event_key(ev: Dict[str, Any]) -> str:
    """Build a deterministic key from the event fields."""
    series = str(ev.get("series", "")).upper()
    year = str(ev.get("year", "") or "")
    etype = str(ev.get("type", "")).lower()
    # date or start_date is the main temporal anchor
    date = str(ev.get("date") or ev.get("start_date") or "")
    # location + link help distinguish rare edge cases
    loc = str(ev.get("location", "") or "")
    link = str(ev.get("link", "") or "")
    key = "|".join([series, year, etype, date, loc, link])
    return key


def assign_ids(events: List[Dict[str, Any]]) -> None:
    """
    Assigns a stable ID to each event if it doesn't already have one.
    Pattern: <series-lower>-<year-or-na>-<type>-<hash10>
    """
    for ev in events:
        if ev.get("id"):
            continue

        series = str(ev.get("series", "X")).lower()
        year = str(ev.get("year") or "na")
        etype = str(ev.get("type", "event")).lower()

        key = _event_key(ev).encode("utf-8", errors="ignore")
        digest = hashlib.md5(key).hexdigest()[:10]

        ev["id"] = f"{series}-{year}-{etype}-{digest}"


# -----------------------------------------------------------------------------
# Scraper registry
# -----------------------------------------------------------------------------

@dataclass
class ScraperSpec:
    series: str
    module_name: str
    func_name: str


SCRAPERS: List[ScraperSpec] = [
    ScraperSpec("ASA", "asa", "scrape_asa"),
    ScraperSpec("CBA", "cba", "scrape_cba"),
    ScraperSpec("COPA", "copa", "scrape_copa"),
    ScraperSpec("WCA", "wca", "scrape_wca"),
    ScraperSpec("EUROANAESTHESIA", "euroanaesthesia", "scrape_euroanaesthesia"),
    ScraperSpec("CLASA", "clasa", "scrape_clasa"),
    ScraperSpec("LASRA", "lasra", "scrape_lasra"),
]


def load_sources_cfg() -> Dict[str, Dict[str, Any]]:
    """
    Returns a map: series -> config dict
    taken from data/sources.json.
    """
    raw = load_json(SOURCES_PATH, {"sources": []})
    series_map: Dict[str, Dict[str, Any]] = {}

    for entry in raw.get("sources", []):
        if not isinstance(entry, dict):
            continue
        series = str(entry.get("series", "")).upper()
        if not series:
            continue
        series_map[series] = entry

    return series_map


def run_scrapers(now_iso: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Runs all available scrapers and returns (events, warnings).
    Each scraper returns (events, warnings) where events are dicts.
    """
    sources_cfg = load_sources_cfg()
    all_events: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for spec in SCRAPERS:
        series = spec.series.upper()
        cfg = sources_cfg.get(series, {})

        try:
            mod = importlib.import_module(f"scripts.scrapers.{spec.module_name}")
            scrape_fn = getattr(mod, spec.func_name)
        except Exception as e:
            warnings.append(f"[{series}] scraper not available: {e}")
            continue

        try:
            events, w = scrape_fn(cfg)
        except Exception as e:
            warnings.append(f"[{series}] scraper failed: {e}")
            continue

        for msg in w or []:
            # Prefix once with series for clarity
            if msg.startswith("["):
                warnings.append(msg)
            else:
                warnings.append(f"[{series}] {msg}")

        for ev in events or []:
            if not isinstance(ev, dict):
                continue
            ev.setdefault("series", series)
            ev.setdefault("source", "scraped")
            all_events.append(ev)

    # Manual overrides, if any (you said you'll keep this empty in production)
    manual_raw = load_json(MANUAL_OVERRIDES_PATH, {"events": []})
    for ev in manual_raw.get("events", []):
        if not isinstance(ev, dict):
            continue
        ev.setdefault("source", "manual")
        all_events.append(ev)

    # Assign IDs deterministically
    assign_ids(all_events)

    return all_events, warnings


# -----------------------------------------------------------------------------
# Ledger / events generation
# -----------------------------------------------------------------------------

def rebuild_ledger(now_iso: str, events: List[Dict[str, Any]], warnings: List[str]) -> Dict[str, Any]:
    """
    Snapshot-style ledger:
      - ONLY contains events seen in this run
      - All statuses are 'active'
      - No tombstones / 'missing' logic at all
    """
    prev = load_json(LEDGER_PATH, {"updated_at": "", "items": {}, "warnings": []})
    prev_items: Dict[str, Any] = prev.get("items", {}) or {}

    new_items: Dict[str, Any] = {}

    for ev in events:
        ev_id = str(ev.get("id"))
        if not ev_id:
            # Should not happen, but avoid crashing if something went wrong
            continue

        prev_entry = prev_items.get(ev_id)
        first_seen = prev_entry.get("first_seen_at") if prev_entry else now_iso

        new_items[ev_id] = {
            "first_seen_at": first_seen,
            "last_seen_at": now_iso,
            "status": "active",
            "event": ev,
        }

    ledger = {
        "updated_at": now_iso,
        "items": new_items,
        "warnings": warnings,
    }
    return ledger


def build_events_json(now_iso: str, ledger: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build data/events.json from the ledger.

    IMPORTANT: Only 'active' events are included.
    There is NO 'missing' status anymore, and no tombstones.
    """
    items: Dict[str, Any] = ledger.get("items", {}) or {}

    events: List[Dict[str, Any]] = []
    for ev_id, entry in items.items():
        if entry.get("status") != "active":
            # In this new model, this shouldn't happen,
            # but we enforce it here just in case.
            continue
        ev = entry.get("event")
        if isinstance(ev, dict):
            events.append(ev)

    # Optional: sort by series/year/date for stable output
    def sort_key(ev: Dict[str, Any]) -> Tuple[str, int, str]:
        series = str(ev.get("series", ""))
        year = int(ev.get("year") or 0)
        date = str(ev.get("date") or ev.get("start_date") or "")
        return (series, year, date)

    events.sort(key=sort_key)

    return {
        "generated_at": now_iso,
        "events": events,
    }


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------

def main() -> None:
    now_iso = utcnow_iso()

    events, warnings = run_scrapers(now_iso)
    ledger = rebuild_ledger(now_iso, events, warnings)
    events_json = build_events_json(now_iso, ledger)

    save_json(LEDGER_PATH, ledger)
    save_json(EVENTS_PATH, events_json)


if __name__ == "__main__":
    main()
