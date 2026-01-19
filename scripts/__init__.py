# scripts/scrapers/__init__.py
"""
Scraper registry for all congress series.

Each scraper function has signature:
    scrape_xxx(cfg: dict) -> tuple[list[dict], list[str]]

Where:
    - cfg is the entry from data/sources.json
    - returns (events, warnings)
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

ScraperFunc = Callable[[Dict[str, Any]], Tuple[List[Dict[str, Any]], List[str]]]

from .asa import scrape_asa
from .euroanaesthesia import scrape_euroanaesthesia
from .cba import scrape_cba
from .clasa import scrape_clasa
from .copa import scrape_copa
from .lasra import scrape_lasra
from .wca import scrape_wca

SCRAPERS: Dict[str, ScraperFunc] = {
    "ASA": scrape_asa,
    "EUROANAESTHESIA": scrape_euroanaesthesia,
    "CBA": scrape_cba,
    "CLASA": scrape_clasa,
    "COPA": scrape_copa,
    "LASRA": scrape_lasra,
    "WCA": scrape_wca,
}
