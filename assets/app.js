// app.js — Anesthesia Congress Calendar (year-agnostic UI)

// ----------------------
// Basic helpers
// ----------------------

function parseISODate(dateStr) {
  // dateStr: "YYYY-MM-DD" → Date at local midnight
  const [y, m, d] = dateStr.split("-").map((x) => parseInt(x, 10));
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

function todayLocalMidnight() {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

function formatDateRange(startStr, endStr, locale) {
  const start = parseISODate(startStr);
  const end = parseISODate(endStr);
  if (!start || !end) return "";

  const optsShort = { day: "numeric", month: "short", year: "numeric" };
  const optsLong = { day: "numeric", month: "long", year: "numeric" };

  // Same month & year → "10–12 May 2026"
  if (
    start.getFullYear() === end.getFullYear() &&
    start.getMonth() === end.getMonth()
  ) {
    const monthYear = end.toLocaleDateString(locale, {
      month: "long",
      year: "numeric",
    });
    return `${start.getDate()}–${end.getDate()} ${monthYear}`;
  }

  // Different month/year → "28 Apr 2026 → 02 May 2026"
  return `${start.toLocaleDateString(locale, optsShort)} → ${end.toLocaleDateString(
    locale,
    optsShort
  )}`;
}

function formatSingleDate(dateStr, locale) {
  const d = parseISODate(dateStr);
  if (!d) return "";
  return d.toLocaleDateString(locale, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function humanizeLastUpdated(iso, locale) {
  if (!iso) return "";
  const updated = new Date(iso);
  if (isNaN(updated.getTime())) return "";

  const now = new Date();
  const diffMs = now - updated;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHours = Math.floor(diffMin / 60);
  const diffDays = Math.floor(diffHours / 24);

  const en = {
    justNow: "just now",
    minutes: (n) => `${n} minute${n !== 1 ? "s" : ""} ago`,
    hours: (n) => `${n} hour${n !== 1 ? "s" : ""} ago`,
    days: (n) => `${n} day${n !== 1 ? "s" : ""} ago`,
  };
  const pt = {
    justNow: "agora mesmo",
    minutes: (n) => `há ${n} minuto${n !== 1 ? "s" : ""}`,
    hours: (n) => `há ${n} hora${n !== 1 ? "s" : ""}`,
    days: (n) => `há ${n} dia${n !== 1 ? "s" : ""}`,
  };

  const t = locale === "pt" ? pt : en;

  if (diffMin < 1) return t.justNow;
  if (diffHours < 1) return t.minutes(diffMin);
  if (diffDays < 1) return t.hours(diffHours);
  return t.days(diffDays);
}

// ----------------------
// i18n
// ----------------------

const I18N = {
  en: {
    lastUpdated: "Last updated",
    upcoming: "Upcoming",
    nextDeadlines: "Next deadlines",
    upcomingCongresses: "Upcoming congresses",
    noDeadlines: "No upcoming deadlines found.",
    noCongresses: "No upcoming congresses found.",
    remindMe: "Remind me",
    open: "Open",
    statusActive: "Active",
  },
  pt: {
    lastUpdated: "Atualizado",
    upcoming: "Próximos",
    nextDeadlines: "Próximos prazos",
    upcomingCongresses: "Próximos congressos",
    noDeadlines: "Nenhum prazo futuro encontrado.",
    noCongresses: "Nenhum congresso futuro encontrado.",
    remindMe: "Lembrar",
    open: "Abrir",
    statusActive: "Ativo",
  },
};

let currentLocale = "en";

function setLocale(locale) {
  currentLocale = locale;
  document.documentElement.setAttribute("data-locale", locale);
  render(); // re-render using cached data
}

// ----------------------
// Data state
// ----------------------

let rawEvents = [];
let lastUpdatedAt = null;

// ----------------------
// Year-agnostic logic:
// only one edition per series
// ----------------------

function computeActiveYearBySeries(events, today) {
  // For each series (ASA, WCA, EUROANAESTHESIA, etc.) pick the
  // first congress whose end_date is in the future.
  const bySeries = {};

  for (const ev of events) {
    if (ev.type !== "congress" || !ev.start_date || !ev.end_date) continue;
    const start = parseISODate(ev.start_date);
    const end = parseISODate(ev.end_date);
    if (!start || !end) continue;
    if (end < today) continue; // congress already over

    const series = ev.series || "UNKNOWN";
    if (!bySeries[series]) {
      bySeries[series] = [];
    }
    bySeries[series].push({
      year: ev.year,
      start,
      end,
    });
  }

  const activeYearBySeries = {};
  for (const [series, list] of Object.entries(bySeries)) {
    list.sort((a, b) => a.start - b.start);
    if (list.length > 0) {
      activeYearBySeries[series] = list[0].year;
    }
  }

  return activeYearBySeries;
}

function filterEventsToActiveEditions(events) {
  const today = todayLocalMidnight();

  const activeYearBySeries = computeActiveYearBySeries(events, today);

  // If a series has no upcoming congress (no congress with end_date >= today),
  // we hide that series entirely for now.
  return events.filter((ev) => {
    const series = ev.series || "UNKNOWN";
    const activeYear = activeYearBySeries[series];
    if (!activeYear) return false;
    return ev.year === activeYear;
  });
}

// ----------------------
// Rendering
// ----------------------

function render() {
  const t = I18N[currentLocale];

  const lastUpdatedEl = document.querySelector("[data-last-updated]");
  if (lastUpdatedEl) {
    lastUpdatedEl.textContent = lastUpdatedAt
      ? humanizeLastUpdated(lastUpdatedAt, currentLocale)
      : "—";
  }

  const mainTitleEl = document.querySelector("[data-section-upcoming-title]");
  if (mainTitleEl) {
    mainTitleEl.textContent = t.upcoming;
  }

  const deadlinesTitleEl = document.querySelector("[data-next-deadlines-title]");
  if (deadlinesTitleEl) {
    deadlinesTitleEl.textContent = t.nextDeadlines;
  }

  const congressesTitleEl = document.querySelector("[data-upcoming-congresses-title]");
  if (congressesTitleEl) {
    congressesTitleEl.textContent = t.upcomingCongresses;
  }

  const deadlinesContainer = document.querySelector("[data-next-deadlines]");
  const congressesContainer = document.querySelector("[data-upcoming-congresses]");

  if (!deadlinesContainer || !congressesContainer) return;

  deadlinesContainer.innerHTML = "";
  congressesContainer.innerHTML = "";

  const today = todayLocalMidnight();

  // Apply year-agnostic filter: only one edition per series
  const events = filterEventsToActiveEditions(rawEvents);

  const upcomingDeadlines = events
    .filter((ev) => ev.date && ev.type && ev.type !== "congress")
    .map((ev) => {
      const d = parseISODate(ev.date);
      return { ev, d };
    })
    .filter(({ d }) => d && d >= today)
    .sort((a, b) => a.d - b.d)
    .slice(0, 10);

  const upcomingCongresses = events
    .filter((ev) => ev.type === "congress" && ev.start_date && ev.end_date)
    .map((ev) => {
      const start = parseISODate(ev.start_date);
      const end = parseISODate(ev.end_date);
      return { ev, start, end };
    })
    .filter(({ end }) => end && end >= today)
    .sort((a, b) => a.start - b.start)
    .slice(0, 10);

  if (upcomingDeadlines.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-message";
    empty.textContent = t.noDeadlines;
    deadlinesContainer.appendChild(empty);
  } else {
    for (const { ev, d } of upcomingDeadlines) {
      deadlinesContainer.appendChild(renderDeadlineCard(ev, d, t));
    }
  }

  if (upcomingCongresses.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-message";
    empty.textContent = t.noCongresses;
    congressesContainer.appendChild(empty);
  } else {
    for (const { ev, start, end } of upcomingCongresses) {
      congressesContainer.appendChild(renderCongressCard(ev, start, end, t));
    }
  }

  // Update counters
  const deadlinesCountEl = document.querySelector("[data-next-deadlines-count]");
  if (deadlinesCountEl) {
    deadlinesCountEl.textContent = `${Math.min(upcomingDeadlines.length, 10)}/10`;
  }
  const congressesCountEl = document.querySelector("[data-upcoming-congresses-count]");
  if (congressesCountEl) {
    congressesCountEl.textContent = `${Math.min(upcomingCongresses.length, 10)}/10`;
  }
}

function seriesClass(series) {
  if (!series) return "";
  const s = series.toLowerCase();
  if (s === "asa") return "card--asa";
  if (s === "wca") return "card--wca";
  if (s === "euroanaesthesia") return "card--euro";
  if (s === "copa") return "card--copa";
  if (s === "cba") return "card--cba";
  if (s === "clasa") return "card--clasa";
  if (s === "lasra") return "card--lasra";
  return "";
}

function renderDeadlineCard(ev, dateObj, t) {
  const card = document.createElement("article");
  card.className = `card ${seriesClass(ev.series)}`;

  const header = document.createElement("div");
  header.className = "card-header";

  const titleEl = document.createElement("h3");
  titleEl.className = "card-title";
  titleEl.textContent = ev.title?.[currentLocale] || ev.title?.en || ev.id || "Deadline";

  const status = document.createElement("span");
  status.className = "chip chip--status";
  status.textContent = t.statusActive;

  header.appendChild(titleEl);
  header.appendChild(status);

  const body = document.createElement("div");
  body.className = "card-body";

  const line = document.createElement("p");
  line.className = "card-meta";
  line.textContent = `${formatSingleDate(ev.date, currentLocale)} — ${daysDiffLabel(dateObj, t)}`;
  body.appendChild(line);

  const actions = document.createElement("div");
  actions.className = "card-actions";

  const remindBtn = document.createElement("button");
  remindBtn.className = "btn btn-secondary";
  remindBtn.textContent = t.remindMe;
  remindBtn.addEventListener("click", () => {
    alert("Reminder not implemented yet. (Local-only, no email.)");
  });

  const openLink = document.createElement("a");
  openLink.className = "btn btn-primary";
  openLink.href = ev.link || "#";
  openLink.target = "_blank";
  openLink.rel = "noopener noreferrer";
  openLink.textContent = t.open;

  actions.appendChild(remindBtn);
  actions.appendChild(openLink);

  card.appendChild(header);
  card.appendChild(body);
  card.appendChild(actions);

  return card;
}

function renderCongressCard(ev, start, end, t) {
  const card = document.createElement("article");
  card.className = `card ${seriesClass(ev.series)}`;

  const header = document.createElement("div");
  header.className = "card-header";

  const titleEl = document.createElement("h3");
  titleEl.className = "card-title";
  titleEl.textContent = ev.title?.[currentLocale] || ev.title?.en || ev.id || "Congress";

  const status = document.createElement("span");
  status.className = "chip chip--status";
  status.textContent = t.statusActive;

  header.appendChild(titleEl);
  header.appendChild(status);

  const body = document.createElement("div");
  body.className = "card-body";

  const range = document.createElement("p");
  range.className = "card-meta";
  range.textContent = `${formatDateRange(ev.start_date, ev.end_date, currentLocale)} · ${ev.location || ""}`;
  body.appendChild(range);

  const actions = document.createElement("div");
  actions.className = "card-actions";

  const remindBtn = document.createElement("button");
  remindBtn.className = "btn btn-secondary";
  remindBtn.textContent = t.remindMe;
  remindBtn.addEventListener("click", () => {
    alert("Reminder not implemented yet. (Local-only, no email.)");
  });

  const openLink = document.createElement("a");
  openLink.className = "btn btn-primary";
  openLink.href = ev.link || "#";
  openLink.target = "_blank";
  openLink.rel = "noopener noreferrer";
  openLink.textContent = t.open;

  actions.appendChild(remindBtn);
  actions.appendChild(openLink);

  card.appendChild(header);
  card.appendChild(body);
  card.appendChild(actions);

  return card;
}

function daysDiffLabel(dateObj, t) {
  const today = todayLocalMidnight();
  const diffMs = dateObj - today;
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays < 0) {
    const n = Math.abs(diffDays);
    return currentLocale === "pt"
      ? `há ${n} dia${n !== 1 ? "s" : ""}`
      : `${n} day${n !== 1 ? "s" : ""} ago`;
  }
  if (diffDays === 0) {
    return currentLocale === "pt" ? "hoje" : "today";
  }
  return currentLocale === "pt"
    ? `em ${diffDays} dia${diffDays !== 1 ? "s" : ""}`
    : `in ${diffDays} day${diffDays !== 1 ? "s" : ""}`;
}

// ----------------------
// Data loading
// ----------------------

async function loadData() {
  try {
    const res = await fetch("data/events.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    rawEvents = data.events || data || [];
    lastUpdatedAt = data.updated_at || null;

    render();
  } catch (err) {
    console.error("Failed to load events:", err);
  }
}

// ----------------------
// Language toggle wiring
// ----------------------

function initLocaleToggle() {
  const enBtn = document.querySelector("[data-lang-en]");
  const ptBtn = document.querySelector("[data-lang-pt]");

  if (enBtn) {
    enBtn.addEventListener("click", () => setLocale("en"));
  }
  if (ptBtn) {
    ptBtn.addEventListener("click", () => setLocale("pt"));
  }
}

// ----------------------
// Boot
// ----------------------

document.addEventListener("DOMContentLoaded", () => {
  initLocaleToggle();
  loadData();
});