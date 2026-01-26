[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.18376953-blue)](https://doi.org/10.5281/zenodo.18376953) 
[![GitHub Pages](https://img.shields.io/badge/live-GitHub%20Pages-brightgreen)](https://helenopaiva.github.io/AnesthesiaCalendar/) 
[![GitHub release](https://img.shields.io/github/v/release/HelenoPaiva/AnesthesiaCalendar)](https://github.com/HelenoPaiva/AnesthesiaCalendar/releases/tag/v1.0.0) 
![Last commit](https://img.shields.io/github/last-commit/HelenoPaiva/AnesthesiaCalendar) 
![License](https://img.shields.io/github/license/HelenoPaiva/AnesthesiaCalendar)

# Anesthesia Congress Calendar

A lightweight, automatically updated calendar of major anesthesia congresses and scientific deadlines.

Live version:  
https://helenopaiva.github.io/AnesthesiaCalendar/

---

## What this project is

The **Anesthesia Congress Calendar** is a public, read-only dashboard that aggregates **officially announced dates** from major international and regional anesthesia congresses.

It is designed as a quick, reliable reference for anesthesiologists who want to know — at a glance:

- When the **next major congress** will take place  
- When **abstract submission windows** open or close  
- When **key scientific deadlines** are approaching  

No accounts.  
No configuration.  
No noise.  

Just dates that matter.

---

## Congresses currently covered

The calendar currently tracks the following congress series:

- **ASA** — American Society of Anesthesiologists Annual Meeting  
- **Euroanaesthesia (ESAIC)** — European Society of Anaesthesiology and Intensive Care  
- **WCA (WFSA)** — World Congress of Anaesthesiologists  
- **COPA (SAESP)** — Congresso Paulista de Anestesiologia  
- **CBA (SBA)** — Congresso Brasileiro de Anestesiologia  

Each congress series has:

- Its **own dedicated scraper**
- A **distinct visual identity**
- Independent update logic

Only the **next upcoming edition** of each congress is displayed, even if later editions are already visible online.

---

## How it works

### Data collection

- Dates are scraped **directly from official congress or society websites**
- Scrapers are **year-agnostic**, adapting automatically as new editions go live
- No manual data entry
- No reliance on unreliable page metadata when known to be problematic

### Update frequency

- Data is refreshed **once per hour** using GitHub Actions
- The interface displays how recently the data was last updated

### Display logic

- **Congresses** and **deadlines** are shown in separate columns
- Congress events are always visually prioritized
- On mobile devices:
  - Congresses appear first
  - Deadlines are shown below
- Each congress series is consistently color-coded across the interface

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

All scrapers, workflows, and frontend code are public, versioned, and auditable.

---

## Scope and design philosophy

This project intentionally avoids:

- User accounts or login systems  
- Notifications, emails, or reminders  
- Personalization or tracking  
- Manual curation of dates  
- Feature creep  

The goal is a **reliable, always-current reference**, not a productivity or reminder platform.

---

## Author

Developed and maintained by  

**Heleno de Paiva Oliveira, MD, PhD**  
Professor of Anesthesiology  
Universidade Federal do Rio Grande do Norte (UFRN)
