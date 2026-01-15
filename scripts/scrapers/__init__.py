from __future__ import annotations

from typing import Any, Dict, List, Tuple, Callable

from scripts.common import load_json

# Each scraper returns: (events, warnings)
ScraperFn = Callable[[Dict[str, Any]], Tuple[List[Dict[str, Any]], List[str]]]


def _load_sources() -> Dict[str, Any]:
    try:
        return load_json("data/sources.json")
    except Exception as e:
        return {"sources": [], "error": f"Failed to load data/sources.json: {e}"}


def run_all_scrapers() -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Runs all scrapers and returns (events, warnings).

    Design goals:
      - each congress can have a custom scraper
      - failures are isolated (one broken site won't break the whole update)
      - sources.json provides URLs and metadata for each series
    """
    sources_cfg = _load_sources()
    sources_list = sources_cfg.get("sources", [])
    warnings: List[str] = []

    if "error" in sources_cfg:
        warnings.append(str(sources_cfg["error"]))

    # Import scrapers here (explicit list keeps it obvious + easy to tailor)
    from scripts.scrapers.asa import scrape_asa
    from scripts.scrapers.cba import scrape_cba
    from scripts.scrapers.copa import scrape_copa
    from scripts.scrapers.euroanaesthesia import scrape_euroanaesthesia
    from scripts.scrapers.wca import scrape_wca
    from scripts.scrapers.clasa import scrape_clasa
    from scripts.scrapers.lasra import scrape_lasra

    registry: Dict[str, ScraperFn] = {
        "ASA": scrape_asa,
        "CBA": scrape_cba,
        "COPA": scrape_copa,
        "EUROANAESTHESIA": scrape_euroanaesthesia,
        "WCA": scrape_wca,
        "CLASA": scrape_clasa,
        "LASRA": scrape_lasra,
    }

    # Build per-series config map from sources.json
    cfg_by_series: Dict[str, Dict[str, Any]] = {}
    if isinstance(sources_list, list):
        for row in sources_list:
            if not isinstance(row, dict):
                continue
            series = str(row.get("series", "")).strip()
            if not series:
                continue
            cfg_by_series[series] = row

    all_events: List[Dict[str, Any]] = []

    for series, fn in registry.items():
        cfg = cfg_by_series.get(series, {"series": series, "urls": []})
        try:
            evs, warns = fn(cfg)
            if evs:
                all_events.extend(evs)
            if warns:
                warnings.extend([f"[{series}] {w}" for w in warns])
        except Exception as e:
            warnings.append(f"[{series}] scraper failed: {e}")

    return all_events, warnings
