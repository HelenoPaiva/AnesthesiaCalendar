# scripts/update.py
"""
Orchestrator for all scrapers.

Reads data/sources.json, calls the appropriate scraper for each series,
merges results, applies manual overrides, and writes:

    data/events.json
    data/ledger.json

This file is what the GitHub Actions workflow should run, e.g.:

    python -m scripts.update
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .scrapers import SCRAPERS


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SourceConfig:
    series: str
    priority: int | None
    raw: Dict[str, Any]


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

SOURCES_PATH = DATA_DIR / "sources.json"
EVENTS_PATH = DATA_DIR / "events.json"
LEDGER_PATH = DATA_DIR / "ledger.json"
MANUAL_OVERRIDES_PATH = DATA_DIR / "manual_overrides.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso_utc() -> str:
    """Current time in ISO 8601 with +00:00, matching existing files."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=False)


def _normalize_sources(raw: Any) -> List[SourceConfig]:
    """
    Accepts either:
      - a list of objects, or
      - an object with a 'sources' list.

    Returns a list of SourceConfig.
    """
    if isinstance(raw, dict) and "sources" in raw:
        entries = raw["sources"]
    else:
        entries = raw

    result: List[SourceConfig] = []
    if not isinstance(entries, list):
        return result

    for item in entries:
        if not isinstance(item, dict):
            continue
        series = item.get("series")
        if not series:
            continue
        priority = item.get("priority")
        result.append(SourceConfig(series=series, priority=priority, raw=item))

    return result


def _deep_merge(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
    """
    Recursively merge src into dst (in-place).
    Used for manual_overrides.json.
    """
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            _deep_merge(dst[key], value)
        else:
            dst[key] = value


# ---------------------------------------------------------------------------
# Core orchestration
# ---------------------------------------------------------------------------

def run_all_scrapers() -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Run all scrapers listed in data/sources.json using the SCRAPERS registry.
    """
    raw_sources = _load_json(SOURCES_PATH, default=[])
    sources = _normalize_sources(raw_sources)

    all_events: List[Dict[str, Any]] = []
    all_warnings: List[str] = []

    for cfg in sources:
        series = cfg.series
        scraper = SCRAPERS.get(series)

        if scraper is None:
            all_warnings.append(f"[{series}] No scraper registered in scripts/scrapers/__init__.py.")
            continue

        try:
            events, warnings = scraper(cfg.raw)
        except Exception as e:  # pragma: no cover - network / scraper bugs
            all_warnings.append(f"[{series}] Scraper raised exception: {e!r}")
            continue

        all_events.extend(events)
        all_warnings.extend(warnings)

    return all_events, all_warnings


def apply_manual_overrides(events: List[Dict[str, Any]]) -> None:
    """
    Apply manual overrides from data/manual_overrides.json (if present),
    matching by event['id'].
    """
    overrides = _load_json(MANUAL_OVERRIDES_PATH, default={})
    if not isinstance(overrides, dict):
        return

    by_id: Dict[str, Dict[str, Any]] = overrides

    for ev in events:
        ev_id = ev.get("id")
        if not ev_id:
            continue
        if ev_id in by_id and isinstance(by_id[ev_id], dict):
            _deep_merge(ev, by_id[ev_id])


def update_ledger(events: List[Dict[str, Any]], warnings: List[str]) -> Dict[str, Any]:
    """
    Update data/ledger.json based on current events.
    Preserves first_seen_at when possible.
    """
    now = _now_iso_utc()
    old_ledger = _load_json(LEDGER_PATH, default={"items": {}, "warnings": []})
    old_items: Dict[str, Any] = old_ledger.get("items", {}) or {}

    new_items: Dict[str, Any] = {}

    # Index new events by id
    for ev in events:
        ev_id = ev.get("id")
        if not ev_id:
            # If an event has no id, skip it; scrapers should always set an id.
            continue

        prev = old_items.get(ev_id)
        first_seen = prev.get("first_seen_at") if isinstance(prev, dict) else now

        new_items[ev_id] = {
            "first_seen_at": first_seen,
            "last_seen_at": now,
            "status": "active",
            "event": ev,
        }

    # Build ledger object
    ledger = {
        "updated_at": now,
        "items": new_items,
        "warnings": warnings,
    }

    return ledger


def build_events_and_ledger() -> None:
    """
    Orchestrate scraping + overrides + writing JSON files.
    """
    now = _now_iso_utc()

    events, warnings = run_all_scrapers()
    apply_manual_overrides(events)

    # Sort events by date/start_date then priority descending (optional, but nice)
    def _event_sort_key(ev: Dict[str, Any]):
        # congresses use start_date; deadlines use date
        date = ev.get("date") or ev.get("start_date") or "9999-12-31"
        # negative priority so higher priority comes first
        prio = -(ev.get("priority") or 0)
        return (date, prio)

    events_sorted = sorted(events, key=_event_sort_key)

    events_json = {
        "generated_at": now,
        "events": events_sorted,
    }
    _save_json(EVENTS_PATH, events_json)

    ledger_json = update_ledger(events_sorted, warnings)
    _save_json(LEDGER_PATH, ledger_json)


def main() -> None:
    build_events_and_ledger()


if __name__ == "__main__":
    main()
