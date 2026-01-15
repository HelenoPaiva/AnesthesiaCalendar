# Anesthesia Congress Calendar

Static GitHub Pages site that lists upcoming anesthesiology congress deadlines and dates,
with an auto-updating data pipeline via GitHub Actions.

## What you get
- EN UI by default + PT toggle (persisted in localStorage)
- "Happening today" section (user local time)
- Upcoming deadlines + upcoming congresses (chronological)
- Reminder chip: downloads an `.ics` event (no email collection)
- Hourly updater + ledger:
  - If an event appears and later disappears from sources, it stays visible as "Removed from source"
  - If an event never appeared, it never shows

## Hosting (GitHub Pages)
1. Repo Settings → Pages
2. Source: `main` branch → `/ (root)`
3. Your site: `https://<username>.github.io/<repo>/`

## Editing data (MVP)
Edit:
- `data/manual_overrides.json`

Then either:
- wait for the hourly workflow, or
- run the workflow manually: Actions → "Update anesthesia congress calendar data" → Run workflow

## Next steps
- Implement scrapers per congress in `scripts/scrapers/`
- Replace placeholder `data/sources.json` URLs with official sources
- Add evidence capture for each extracted date (URL + snippet)
