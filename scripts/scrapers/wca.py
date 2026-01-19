# scripts/scrapers/wca.py
# EXECUTION PROBE — DO NOT ADD LOGIC

from typing import Any, Dict, List, Tuple


def scrape_wca(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    This scraper intentionally does NOTHING except emit a unique error.
    If this message appears in the ledger, this function is being executed.
    """
    raise RuntimeError("WCA PROBE: scrape_wca() IS BEING EXECUTED")
