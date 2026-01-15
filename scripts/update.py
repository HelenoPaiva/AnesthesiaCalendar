from __future__ import annotations

from typing import Any, Dict, List, Tuple

from scripts.common import (
    load_json,
    save_json,
    utc_now_iso,
    stable_event_id,
    normalize_event,
    when_key,
    today_ymd_local,
    mark_ended,
)
from scripts.validate import validate_events
from scripts.scrapers import run_all_scrapers


PATH_EVENTS = "data/events.json"
PATH_LEDGER = "data/ledger.json"
PATH_MANUAL = "data/manual_overrides.json"


def main() -> None:
    now = utc_now_iso()
    today = today_ymd_local()

    ledger = load_json(PATH_LEDGER)
    ledger_items: Dict[str, Any] = ledger.get("items", {}) if isinstance(ledger, dict) else {}
    if not isinstance(ledger_items, dict):
        ledger_items = {}

    manual = load_json(PATH_MANUAL)
    manual_events = manual.get("events", []) if isinstance(manual, dict) else []
    if not isinstance(manual_events, list):
        manual_events = []

    scraped_events, warnings = run_all_scrapers()

    # Normalize and assign IDs
    current: Dict[str, Dict[str, Any]] = {}

    def ingest(ev: Dict[str, Any], source: str) -> None:
        e = normalize_event(ev)
        e["source"] = source
        e["id"] = stable_event_id(e)
        current[e["id"]] = e

    for ev in scraped_events:
        ingest(ev, "scraped")

    for ev in manual_events:
        ingest(ev, "manual")

    # Update ledger
    # Rules:
    # - If event exists in current snapshot: status=active (or manual), last_seen=now
    # - If event existed before but not in current: status=missing
    # - Ended tagging is computed for presentation (status can remain missing/active/manual, but we also set ended if past)
    for eid, ev in current.items():
        if eid not in ledger_items:
            ledger_items[eid] = {
                "first_seen_at": now,
                "last_seen_at": now,
                "status": "manual" if ev.get("source") == "manual" else "active",
            }
        else:
            ledger_items[eid]["last_seen_at"] = now
            ledger_items[eid]["status"] = "manual" if ev.get("source") == "manual" else "active"

        # Store latest event payload for display
        ledger_items[eid]["event"] = ev

    # Mark missing items
    for eid, item in list(ledger_items.items()):
        if not isinstance(item, dict):
            continue
        if eid not in current:
            # If we have an event payload, keep it and mark missing
            if "event" in item and isinstance(item["event"], dict):
                item["status"] = "missing"

    ledger_out = {
        "updated_at": now,
        "items": ledger_items,
        "warnings": warnings,
    }
    save_json(PATH_LEDGER, ledger_out)

    # Build events feed for frontend:
    # Include:
    # - all items that have ever appeared (ledger has them)
    # Exclude:
    # - items with no event payload (shouldn't happen, but safe)
    events_out: List[Dict[str, Any]] = []
    for eid, item in ledger_items.items():
        if not isinstance(item, dict):
            continue
        ev = item.get("event")
        if not isinstance(ev, dict):
            continue

        out = dict(ev)
        out["id"] = eid
        out["status"] = item.get("status", "active")
        out["first_seen_at"] = item.get("first_seen_at")
        out["last_seen_at"] = item.get("last_seen_at")

        # Compute ended presentation status
        if mark_ended(out, today):
            out["status"] = "ended"

        events_out.append(out)

    # Sort for stable output (frontend sorts too, but stable JSON is nice)
    events_out.sort(key=lambda x: (when_key(x), -(x.get("priority") or 0)))

    ok, errors = validate_events(events_out)
    if not ok:
        # Still write events.json for debugging, but fail the action
        save_json(PATH_EVENTS, {"generated_at": now, "events": events_out, "errors": errors})
        raise SystemExit("Validation failed:\n" + "\n".join(errors))

    save_json(PATH_EVENTS, {"generated_at": now, "events": events_out})


if __name__ == "__main__":
    main()
