// assets/app.js — production version
// Loads ./data/i18n.json and ./data/events.json and renders the calendar UI.

const DATA_URL = "./data/events.json";
const I18N_URL = "./data/i18n.json";

async function fetchJson(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to fetch ${url}: ${res.status}`);
  }
  const json = await res.json();
  console.log("Loaded", url, "keys:", Object.keys(json || {}));
  return json;
}

function chooseLang(i18n) {
  // URL param ?lang=pt or ?lang=en overrides everything
  const params = new URLSearchParams(window.location.search);
  const paramLang = params.get("lang");
  if (paramLang === "pt" || paramLang === "en") return paramLang;

  // Browser language
  const nav = navigator.language || navigator.userLanguage || "en";
  if (nav.toLowerCase().startsWith("pt")) return "pt";

  return "en";
}

function ui(i18n, key, lang, fallback) {
  const uiRoot = i18n && i18n.ui ? i18n.ui : {};
  const entry = uiRoot[key];
  if (!entry) return fallback || key;
  return entry[lang] || entry.en || fallback || key;
}

function formatISODate(dateStr) {
  // dateStr is "YYYY-MM-DD"
  if (!dateStr) return "";
  const [y, m, d] = dateStr.split("-").map((v) => parseInt(v, 10));
  if (!y || !m || !d) return dateStr;
  const dt = new Date(y, m - 1, d);
  const dd = String(dt.getDate()).padStart(2, "0");
  const mm = String(dt.getMonth() + 1).padStart(2, "0");
  const yyyy = dt.getFullYear();
  return `${dd}/${mm}/${yyyy}`;
}

function daysDiff(fromISO, toISO) {
  const from = new Date(fromISO);
  const to = new Date(toISO);
  const msPerDay = 24 * 60 * 60 * 1000;
  return Math.round((to - from) / msPerDay);
}

function relativeDayLabel(i18n, lang, dateStr, todayStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  const today = new Date(todayStr);
  const msPerDay = 24 * 60 * 60 * 1000;
  const diff = Math.round((d - today) / msPerDay);

  if (diff === 0) {
    return ui(i18n, "today", lang, "Today");
  }
  if (diff > 0) {
    const tpl = ui(i18n, "in_days", lang, "in {n} days");
    return tpl.replace("{n}", diff);
  }
  // past
  const past = Math.abs(diff);
  const tpl = ui(i18n, "in_days", lang, "in {n} days");
  return tpl.replace("{n}", `-${past}`);
}

function splitEvents(events, todayStr) {
  const safe = Array.isArray(events) ? events : [];

  const upcoming = safe.filter((ev) => {
    if (!ev.date) return false;
    return ev.date >= todayStr;
  });

  const deadlines = upcoming.filter((ev) =>
    ev.type ? ev.type.toLowerCase().includes("deadline") : false
  );

  const congresses = upcoming.filter(
    (ev) => !ev.type || !ev.type.toLowerCase().includes("deadline")
  );

  const sortByDatePriority = (a, b) => {
    if (a.date !== b.date) return a.date.localeCompare(b.date);
    const pa = typeof a.priority === "number" ? a.priority : 0;
    const pb = typeof b.priority === "number" ? b.priority : 0;
    return pb - pa; // higher priority first
  };

  deadlines.sort(sortByDatePriority);
  congresses.sort(sortByDatePriority);

  return { deadlines, congresses };
}

function clearContainer(selector) {
  const el = document.querySelector(selector);
  if (el) el.innerHTML = "";
  return el;
}

function renderEventList(container, events, i18n, lang, kind) {
  if (!container) return;

  container.innerHTML = "";

  if (!events || events.length === 0) {
    const emptyKey = kind === "deadlines" ? "no_deadlines" : "no_congresses";
    const msg = ui(
      i18n,
      emptyKey,
      lang,
      kind === "deadlines"
        ? "No upcoming deadlines."
        : "No upcoming congresses."
    );
    const div = document.createElement("div");
    div.className = "empty-state";
    div.textContent = msg;
    container.appendChild(div);
    return;
  }

  const todayStr = new Date().toISOString().slice(0, 10);

  events.forEach((ev) => {
    const card = document.createElement("article");
    card.className = "event-card";

    const titleText =
      (ev.title && (ev.title[lang] || ev.title.en)) ||
      ev.title ||
      "(no title)";
    const titleEl = document.createElement("div");
    titleEl.className = "event-title";
    titleEl.textContent = titleText;
    card.appendChild(titleEl);

    const metaRow = document.createElement("div");
    metaRow.className = "event-meta-row";

    // Date chip
    if (ev.date) {
      const dateChip = document.createElement("span");
      dateChip.className = "event-chip event-date-main";
      const rel = relativeDayLabel(i18n, lang, ev.date, todayStr);
      dateChip.textContent = `${formatISODate(ev.date)} • ${rel}`;
      metaRow.appendChild(dateChip);
    }

    // Location
    if (ev.location) {
      const locChip = document.createElement("span");
      locChip.className = "event-chip";
      locChip.textContent = ev.location;
      metaRow.appendChild(locChip);
    }

    // Series
    if (ev.series) {
      const seriesChip = document.createElement("span");
      seriesChip.className = "event-chip event-series";
      seriesChip.textContent = ev.series;
      metaRow.appendChild(seriesChip);
    }

    card.appendChild(metaRow);

    // Link
    if (ev.link) {
      const linkRow = document.createElement("div");
      linkRow.className = "event-link";
      const a = document.createElement("a");
      a.href = ev.link;
      a.target = "_blank";
      a.rel = "noreferrer noopener";
      a.textContent = ui(i18n, "open", lang, "Open");
      linkRow.appendChild(a);
      card.appendChild(linkRow);
    }

    container.appendChild(card);
  });
}

function applyStaticTexts(i18n, data, lang) {
  // Subtitle
  const subtitleEl = document.querySelector("[data-subtitle]");
  if (subtitleEl) {
    subtitleEl.textContent = ui(
      i18n,
      "subtitle",
      lang,
      "Upcoming deadlines and congress dates."
    );
  }

  // Column titles
  const deadlinesTitleEl = document.querySelector(
    "[data-next-deadlines-title]"
  );
  if (deadlinesTitleEl) {
    deadlinesTitleEl.textContent = ui(
      i18n,
      "next_deadlines",
      lang,
      "Next deadlines"
    );
  }

  const congressesTitleEl = document.querySelector(
    "[data-upcoming-congresses-title]"
  );
  if (congressesTitleEl) {
    congressesTitleEl.textContent = ui(
      i18n,
      "upcoming_congresses",
      lang,
      "Upcoming congresses"
    );
  }

  // Last updated
  const lastUpdatedEl = document.querySelector("[data-last-updated]");
  if (lastUpdatedEl) {
    const label = ui(i18n, "last_updated", lang, "Last updated");
    const iso = data && data.generated_at ? data.generated_at : null;
    let datePart = "";
    if (iso && iso.length >= 10) {
      datePart = iso.slice(0, 10);
    } else {
      datePart = new Date().toISOString().slice(0, 10);
    }
    lastUpdatedEl.textContent = `${label}: ${formatISODate(datePart)}`;
  }
}

function setCounts(deadlinesLen, congressesLen) {
  const dlCount = document.querySelector("[data-next-deadlines-count]");
  if (dlCount) {
    dlCount.textContent = `${deadlinesLen} item(s)`;
  }
  const cgCount = document.querySelector(
    "[data-upcoming-congresses-count]"
  );
  if (cgCount) {
    cgCount.textContent = `${congressesLen} item(s)`;
  }
}

async function main() {
  try {
    const [i18n, data] = await Promise.all([
      fetchJson(I18N_URL),
      fetchJson(DATA_URL),
    ]);

    if (!Array.isArray(data.events)) {
      console.error("events.json payload:", data);
      throw new Error(
        "DATA_URL did not contain {events: []}. Check events.json structure."
      );
    }

    const lang = chooseLang(i18n);
    console.log("Using language:", lang);

    const todayStr = new Date().toISOString().slice(0, 10);
    const { deadlines, congresses } = splitEvents(data.events, todayStr);

    applyStaticTexts(i18n, data, lang);

    const deadlinesContainer = clearContainer("[data-next-deadlines]");
    const congressesContainer = clearContainer("[data-upcoming-congresses]");

    renderEventList(
      deadlinesContainer,
      deadlines,
      i18n,
      lang,
      "deadlines"
    );
    renderEventList(
      congressesContainer,
      congresses,
      i18n,
      lang,
      "congresses"
    );

    setCounts(deadlines.length, congresses.length);
  } catch (err) {
    console.error("Fatal error in main():", err);

    // Show visible error in the left column so you don't get a silent blank page
    const container =
      document.querySelector("[data-next-deadlines]") ||
      document.body;
    const div = document.createElement("div");
    div.className = "empty-state";
    div.style.marginTop = "12px";
    div.textContent =
      "Error loading calendar data. Check console logs for details.";
    container.appendChild(div);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  main();
});