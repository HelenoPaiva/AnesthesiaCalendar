from __future__ import annotations

from typing import Any, Dict, List, Tuple

# A scraper returns (events, warnings)
# events: List[dict] normalized-ish (without ledger fields)
# warnings: List[str]

def run_all_scrapers() -> Tuple[List[Dict[str, Any]], List[str]]:
    # For MVP: scrapers return empty.
    # Later we will implement each congress parser in its file and import here.
    events: List[Dict[str, Any]] = []
    warnings: List[str] = []
    return events, warnings
