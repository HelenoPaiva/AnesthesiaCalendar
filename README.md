# Anesthesia Congress Calendar

A lightweight, auto-updated calendar of major anesthesia congresses and deadlines.

Live at:  
https://helenopaiva.github.io/AnesthesiaCalendar/

---

## What this is

The **Anesthesia Congress Calendar** aggregates official dates from major international and regional anesthesia congresses and presents them in a simple, fast, mobile-friendly dashboard.

It focuses on what matters most to anesthesiologists:

- Upcoming **congress dates**
- Upcoming **abstract and registration deadlines**
- Clear prioritization of what comes next
- Minimal UI, no logins, no tracking

All data is **scraped automatically from official congress websites** and refreshed hourly.

---

## Currently covered congresses

The calendar currently tracks:

- **ASA** — American Society of Anesthesiologists Annual Meeting  
- **Euroanaesthesia (ESAIC)** — European Society of Anaesthesiology and Intensive Care  
- **WCA** — World Congress of Anaesthesiologists (WFSA)  
- **COPA (SAESP)** — Paulista Congress of Anesthesiology  

Each congress is handled independently and displayed consistently.

Only the **next upcoming edition** of each congress is shown, even if future editions already exist online.

---

## How the calendar works

### Data collection
- Dedicated scrapers fetch dates directly from official congress websites.
- Scrapers are **year-agnostic** and adapt as new editions go live.
- No manual data entry.

### Update frequency
- Calendar data is refreshed **once per hour** via GitHub Actions.
- The UI always shows when the data was last updated.

### Display logic
- **Congresses** are shown first (most important).
- **Deadlines** are shown separately.
- On mobile:
  - Congresses appear first
  - Deadlines appear below
- Color coding is consistent per congress series.

---

## User interface features

- Language toggle: **English / Portuguese**
- Clean, responsive layout
- Entire event cards are clickable
- Clear date ranges and relative time (“in 42 days”)
- No ads, no cookies, no analytics

---

## Source & transparency

This project is fully open-source.

GitHub repository:  
https://github.com/HelenoPaiva/AnesthesiaCalendar

All scraping logic, update workflows, and frontend code are public and auditable.

---

## Scope and philosophy

This project intentionally avoids:
- Accounts or user tracking
- Notifications or emails
- Overly complex filtering
- Manual curation

The goal is a **reliable, always-current reference**, not a productivity platform.

---

## Author

Developed and maintained by  
**Heleno de Paiva Oliveira, MD, PhD**  
Anesthesiologist
Universidade Federal do Rio Grande do Norte

Contributions, suggestions, and issue reports are welcome via GitHub.
