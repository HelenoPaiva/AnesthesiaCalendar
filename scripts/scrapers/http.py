from __future__ import annotations

import gzip
import re
import urllib.request
from typing import Dict, Tuple, Optional


DEFAULT_HEADERS = {
    "User-Agent": "AnesthesiaCongressCalendarBot/1.0 (+GitHub Actions)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en,pt-BR;q=0.8,pt;q=0.7",
}


def fetch_text(url: str, timeout: int = 20, headers: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
    """
    Returns (text, content_type). Raises on HTTP errors.
    Tries to handle gzip content.
    """
    h = dict(DEFAULT_HEADERS)
    if headers:
        h.update(headers)

    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        content_type = resp.headers.get("Content-Type", "") or ""
        raw = resp.read()

        enc = resp.headers.get("Content-Encoding", "") or ""
        if "gzip" in enc.lower():
            raw = gzip.decompress(raw)

        # Try to detect charset
        charset = "utf-8"
        m = re.search(r"charset=([^\s;]+)", content_type, flags=re.I)
        if m:
            charset = m.group(1).strip().strip('"').strip("'")

        try:
            text = raw.decode(charset, errors="replace")
        except Exception:
            text = raw.decode("utf-8", errors="replace")

        return text, content_type
