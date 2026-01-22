# Anesthesia Congress Calendar

A lightweight, auto-updated calendar of major anesthesia congresses and scientific deadlines.

Live version:  
https://helenopaiva.github.io/AnesthesiaCalendar/

---

## What this project is

The **Anesthesia Congress Calendar** is a public, read-only dashboard that aggregates **official dates** from major international and regional anesthesia congresses.

It is designed as a quick reference for anesthesiologists who want to know:

- When the **next congress** takes place
- When **abstract submissions** close
- When **registration deadlines** are approaching

No accounts, no setup, no noise — just dates that matter.

---

## Currently covered congresses

The calendar currently tracks and displays data from:

- **ASA** — American Society of Anesthesiologists Annual Meeting  
- **Euroanaesthesia (ESAIC)** — European Society of Anaesthesiology and Intensive Care  
- **WCA** — World Congress of Anaesthesiologists (WFSA)  
- **COPA (SAESP)** — Paulista Congress of Anesthesiology  
- **CBA (SBA)** — Congresso Brasileiro de Anestesiologia  

Each congress series has its **own scraper** and **distinct visual identity**.

Only the **next upcoming edition** of each congress is displayed, even if future editions are already visible online.

---

## How it works

### Data collection
- Dates are scraped **directly from official congress websites**
- Scrapers are **year-agnostic** and adapt as new editions go live
- No manual data entry
- No reliance on page metadata when it is known to be unreliable

### Update frequency
- Data is refreshed **once per hour** using GitHub Actions
- The interface shows how recently the data was updated

### Display logic
- **Congresses** and **deadlines** are shown in separate columns
- Congresses are always prioritized visually
- On mobile:
  - Congresses appear first
  - Deadlines appear below
- Each congress series is consistently color-coded

---

## User interface features

- Language toggle: **English / Portuguese**
- Fully responsive layout (desktop and mobile)
- Entire event cards are clickable
- Clear date ranges and relative timing (e.g. “in 42 days”)
- No ads, no cookies, no analytics, no tracking

---

## Transparency & source code

This project is fully open-source.

GitHub repository:  
https://github.com/HelenoPaiva/AnesthesiaCalendar

All scrapers, workflows, and frontend code are public and auditable.

---

## Scope and philosophy

This project intentionally avoids:

- User accounts
- Notifications or emails
- Personalization or tracking
- Manual curation of dates
- Feature creep

The goal is a **reliable, always-current reference**, not a productivity or reminder system.

---

## Author

Developed and maintained by  
**Heleno de Paiva Oliveira, MD, PhD**  
Anesthesiologist  
Universidade Federal do Rio Grande do Norte (UFRN)

Suggestions, corrections, and issue reports are welcome via GitHub.
