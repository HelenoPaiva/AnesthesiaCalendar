# scripts/scrapers/lasra.py
# LASRA — Latin American Society of Regional Anesthesia
#
# Strategy:
# - Fetch https://www.lasra.com.br/
# - Discover Google Drive PDF links on the page
# - Download the PDF
# - Extract text
# - Parse PT/EN date ranges
# - Reject any year < current year
# - Emit ONLY the next upcoming congress
#
# Version: v2026-01-20a

import io
import re
import sys
import datetime
import urllib.request
from typing import List, Dict, Optional

try:
    from pypdf import PdfReader
except ImportError:
    raise RuntimeError("pypdf is required for LASRA scraper")


SCRAPER_VERSION = "v2026-01-20a"
BASE_URL = "https://www.lasra.com.br/"


# -------------------- Utilities --------------------

def log(msg: str):
    print(f"[LASRA] {msg}")


def log_debug(msg: str):
    print(f"[LASRA DEBUG] {msg}")


def fetch(url: str, binary: bool = False, timeout: int = 20):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; AnesthesiaCalendar/1.0)"
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read() if binary else resp.read().decode("utf-8", errors="ignore")


# -------------------- Month maps --------------------

PT_MONTHS = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

EN_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


# -------------------- Core logic --------------------

def extract_drive_file_ids(html: str) -> List[str]:
    """
    Find Google Drive file IDs referenced in the LASRA homepage.
    """
    ids = re.findall(
        r"https://drive\.google\.com/file/d/([A-Za-z0-9_-]+)",
        html,
    )
    return list(dict.fromkeys(ids))  # deduplicate, preserve order


def download_drive_pdf(file_id: str) -> bytes:
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    return fetch(url, binary=True)


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    chunks = []
    for page in reader.pages:
        txt = page.extract_text() or ""
        chunks.append(txt)
    text = " ".join(chunks)
    text = re.sub(r"\s+", " ", text)
    return text


def parse_date_ranges(text: str) -> List[Dict]:
    """
    Extract possible date ranges from PDF text.
    Returns list of dicts with start_date, end_date, year.
    """
    now_year = datetime.date.today().year
    results = []

    # ---- Portuguese pattern: 23 a 26 de abril de 2026
    pt_pat = re.compile(
        r"(\d{1,2})\s*(?:a|-|–)\s*(\d{1,2})\s+de\s+([A-Za-zçéáãô]+)\s+20(\d{2})",
        re.IGNORECASE,
    )

    for m in pt_pat.finditer(text):
        d1, d2, month_raw, yy = m.groups()
        year = int("20" + yy)
        if year < now_year:
            continue

        month_key = month_raw.lower()
        if month_key not in PT_MONTHS:
            continue

        month = PT_MONTHS[month_key]
        start = datetime.date(year, month, int(d1))
        end = datetime.date(year, month, int(d2))

        results.append(
            {
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "year": year,
            }
        )

    # ---- English pattern: April 23–26, 2026
    en_pat = re.compile(
        r"([A-Za-z]+)\s+(\d{1,2})\s*(?:-|–|to)\s*(\d{1,2}),\s*20(\d{2})",
        re.IGNORECASE,
    )

    for m in en_pat.finditer(text):
        month_raw, d1, d2, yy = m.groups()
        year = int("20" + yy)
        if year < now_year:
            continue

        month_key = month_raw.lower()
        if month_key not in EN_MONTHS:
            continue

        month = EN_MONTHS[month_key]
        start = datetime.date(year, month, int(d1))
        end = datetime.date(year, month, int(d2))

        results.append(
            {
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "year": year,
            }
        )

    return results


# -------------------- Public entry point --------------------

def scrape() -> List[Dict]:
    log(f"Scraper version {SCRAPER_VERSION}")

    try:
        html = fetch(BASE_URL)
    except Exception as e:
        log(f"Failed to fetch LASRA homepage: {e}")
        return []

    file_ids = extract_drive_file_ids(html)
    log_debug(f"drive_files_found={len(file_ids)}")

    if not file_ids:
        log("No Google Drive PDF links found on LASRA homepage.")
        return []

    all_ranges = []

    for fid in file_ids:
        try:
            pdf_bytes = download_drive_pdf(fid)
            text = extract_text_from_pdf(pdf_bytes)
            ranges = parse_date_ranges(text)
            log_debug(f"file_id={fid} ranges_found={len(ranges)}")
            all_ranges.extend(ranges)
        except Exception as e:
            log(f"Failed processing PDF {fid}: {e}")

    if not all_ranges:
        log("No valid future date ranges found in LASRA PDFs.")
        return []

    # Pick the next upcoming congress (earliest start_date)
    all_ranges.sort(key=lambda r: r["start_date"])
    picked = all_ranges[0]

    year = picked["year"]

    event = {
        "series": "LASRA",
        "year": year,
        "type": "congress",
        "start_date": picked["start_date"],
        "end_date": picked["end_date"],
        "location": "Brazil",
        "link": BASE_URL,
        "priority": 7,
        "title": {
            "en": f"LASRA {year} — Latin American Society of Regional Anesthesia",
            "pt": f"LASRA {year} — Congresso Latino-Americano de Anestesia Regional",
        },
        "source": "scraped",
    }

    log_debug(
        f"picked={picked['start_date']}..{picked['end_date']} year={year}"
    )

    return [event]


# -------------------- CLI support --------------------

if __name__ == "__main__":
    events = scrape()
    for ev in events:
        print(ev)
