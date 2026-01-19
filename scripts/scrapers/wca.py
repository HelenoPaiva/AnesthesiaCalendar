# scripts/scrapers/wca.py
# MINIMAL PROBE VERSION — NO SCRAPING, ONLY A LEDGER WARNING

from typing import Any, Dict, List, Tuple


def scrape_wca(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Probe function: produces no events and a single warning.

    If this exact message appears in ledger.json under "warnings",
    we know wca.py is being executed by the build pipeline.
    """
    events: List[Dict[str, Any]] = []
    warnings: List[str] = ["[WCA PROBE] scrape_wca() in scripts/scrapers/wca.py was executed"]
    return events, warnings
