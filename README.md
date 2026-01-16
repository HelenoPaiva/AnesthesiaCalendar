# Anesthesia Congress Calendar

A lightweight, fully automated calendar of upcoming anesthesiology congresses and deadlines, built for anesthesiologists.

The project continuously tracks major national and international anesthesia meetings (e.g. ASA, CBA, WCA, Euroanaesthesia, LASRA) and displays:

- Upcoming congress dates  
- Abstract submission windows and key deadlines  
- What is happening *today*  
- Chronologically ordered upcoming events  

The site updates automatically via GitHub Actions and requires **no manual data entry**.

---

## 🌐 Live version

👉 **https://helenopaiva.github.io/AnesthesiaCalendar/**  

---

## ✨ Key features

- **Fully automated scraping**  
  All data is obtained from official congress websites. If an event is not visible at the source, it is not shown.

- **Multi-year aware**  
  Future congresses (2027, 2028, …) appear automatically as soon as they are published by the organizers.

- **No tombstones / no stale data**  
  Events that disappear from the source disappear from the calendar.

- **Language toggle**  
  English (default) ↔ Portuguese UI switch.

- **Timezone-safe**  
  Dates are interpreted in the user’s local system timezone.

- **Reminder-friendly**  
  Each future event can generate a calendar reminder (ICS), without accounts or email collection.

- **Static & fast**  
  Runs entirely on GitHub Pages — no backend, no database, no cookies.

---

## 🛠 How it works

1. **GitHub Actions** runs scheduled crawlers (hourly).
2. Scrapers fetch and parse official congress pages.
3. A snapshot of currently detected events is written to `data/events.json`.
4. The frontend reads this file and renders the calendar.

There is no long-term persistence of removed events — the site always reflects the current state of the sources.

---

## 🚧 Project status

- ASA: fully automated (congress + submission deadlines)
- Other societies: scrapers in progress
- UI/UX: MVP complete, visual polish ongoing

---

## 📄 License

MIT License.
