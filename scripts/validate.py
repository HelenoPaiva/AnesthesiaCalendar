from __future__ import annotations

from typing import Any, Dict, List, Tuple


ALLOWED_TYPES = {
    "abstract_open",
    "abstract_deadline",
    "late_breaking_deadline",
    "acceptance_notification",
    "presenter_confirmation",
    "substitution_deadline",
    "early_bird_deadline",
    "regular_registration_deadline",
    "housing_deadline",
    "workshop_deadline",
    "other_deadline",
    "congress",
}


def validate_events(events: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    seen_ids = set()

    for i, ev in enumerate(events):
        prefix = f"events[{i}]"

        if "id" not in ev or not isinstance(ev["id"], str) or not ev["id"].strip():
            errors.append(f"{prefix}: missing/invalid id")
        else:
            if ev["id"] in seen_ids:
                errors.append(f"{prefix}: duplicate id={ev['id']}")
            seen_ids.add(ev["id"])

        for key in ["series", "type"]:
            if key not in ev or not isinstance(ev[key], str) or not ev[key].strip():
                errors.append(f"{prefix}: missing/invalid {key}")

        if ev.get("type") not in ALLOWED_TYPES:
            errors.append(f"{prefix}: type not allowed: {ev.get('type')}")

        if ev.get("type") == "congress":
            if not ev.get("start_date") or not ev.get("end_date"):
                errors.append(f"{prefix}: congress missing start_date/end_date")
            else:
                if str(ev["start_date"]) > str(ev["end_date"]):
                    errors.append(f"{prefix}: congress start_date after end_date")
        else:
            if not ev.get("date"):
                errors.append(f"{prefix}: non-congress missing date")

    ok = len(errors) == 0
    return ok, errors
