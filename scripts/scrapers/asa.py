from __future__ import annotations

from typing import Any, Dict, List, Tuple

def scrape_asa(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    urls = cfg.get("urls", []) or []
    warnings: List[str] = []
    # Placeholder: implement ASA parsing later
    if not urls:
        warnings.append("No source URLs configured in data/sources.json.")
    return [], warnings
