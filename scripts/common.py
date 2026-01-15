from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Optional


ISO_DATE = "YYYY-MM-DD"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def stable_event_id(ev: Dict[str, Any]) -> str:
    """
    Create a stable id based on series/year/type + date or range.
    """
    series = str(ev.get("series", "")).strip().lower()
    year = str(ev.get("year", "")).strip()
    etype = str(ev.get("type", "")).strip().lower()

    if etype == "congress":
        s = ev.get("start_date", "")
        e = ev.get("end_date", "")
        key = f"{series}-{year}-{etype}-{s}-{e}"
    else:
        d = ev.get("date", "")
        key = f"{series}-{year}-{etype}-{d}"

    # Keep readable but collision-resistant
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
    return f"{series}-{year}-{etype}-{h}"


def normalize_event(ev: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize to canonical keys. Does not set status fields (ledger does that).
    """
    out = dict(ev)

    out["series"] = str(out.get("series", "")).strip()
    out["year"] = int(out["year"]) if "year" in out and str(out["year"]).isdigit() else out.get("year")
    out["type"] = str(out.get("type", "")).strip()

    # Optional fields
    if "priority" not in out:
        out["priority"] = 0

    if "location" not in out:
        out["location"] = ""

    if "link" not in out:
        out["link"] = ""

    # Ensure title shape if present
    if "title" in out and isinstance(out["title"], dict):
        out["title"] = {
            "en": out["title"].get("en", ""),
            "pt": out["title"].get("pt", "")
        }

    return out


def when_key(ev: Dict[str, Any]) -> str:
    if ev.get("type") == "congress":
        return str(ev.get("start_date", "9999-12-31"))
    return str(ev.get("date", "9999-12-31"))


def today_ymd_local() -> str:
    # Updater runs in UTC. For ended tagging we prefer a simple UTC date.
    # UI will use user local date anyway.
    now = datetime.now(timezone.utc)
    return now.date().isoformat()


def mark_ended(ev: Dict[str, Any], today_ymd: str) -> bool:
    if ev.get("type") == "congress":
        end_date = ev.get("end_date")
        return bool(end_date and str(end_date) < today_ymd)
    d = ev.get("date")
    return bool(d and str(d) < today_ymd)
