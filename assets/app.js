// assets/app.js — OPERATIONAL VERSION (lang + last-updated + counts)
// Simplified chips:
// - Congresses: DATE CHIP ONLY (series color applies to card + date chip)
// - Deadlines: DATE CHIP + SERIES CHIP ONLY (series chip matches series color)
// - No location chips anywhere
// + Congress dedup: only the next upcoming congress per series
// + WCA handling: WCA / World Congress of Anaesthesiologists forced as congress, with own series class
//
// 2026-01-19 (v6):
// - ICS support fully removed
// - Deadlines classified before congresses
// - Whole event card clickable
// - Congress column first (desktop + mobile)
// - Repo link localized

const APP_VERSION = "2026-01-19 operational-no-ics-cleanup";

const DATA_URL = "./data/events.json";
const I18N_URL = "./data/i18n.json";

const DEADLINE_TYPES = [
  "abstract_deadline",
  "pbl_deadline",
  "other_deadline",
  "registration_deadline",
  "hotel_deadline",
  "early_bird_deadline",
  "submission_deadline",
  "poster_deadline",
  "deadline",
];

const CONGRESS_TYPES = ["congress", "meeting", "main_event", "annual_meeting"];

const appState = {
  i18n: null,
  data: null,
  deadlines: [],
  congresses: [],
  lang: "en",
};

// ------------------ Fetch ------------------

async function fetchJson(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch ${url}: ${res.status}`);
  return await res.json();
}

// ------------------ Language ------------------

function getStoredLang() {
  try {
    const v = localStorage.getItem("acc_lang");
    if (v === "en" || v === "pt") return v;
  } catch {}
  return null;
}

function chooseInitialLang() {
  const params = new URLSearchParams(window.location.search);
  const paramLang = params.get("lang");
  if (paramLang === "pt" || paramLang === "en") return paramLang;

  const stored = getStoredLang();
  if (stored) return stored;

  const nav = navigator.language || "en";
  return nav.toLowerCase().startsWith("pt") ? "pt" : "en";
}

function ui(i18n, key, lang, fallback) {
  return i18n?.ui?.[key]?.[lang] || i18n?.ui?.[key]?.en || fallback || key;
}

function setupLangSwitcher() {
  const switchEl = document.querySelector("[data-lang-switch]");
  if (!switchEl) return;

  const buttons = Array.from(switchEl.querySelectorAll("[data-lang-btn]"));

  function updateActive() {
    buttons.forEach((btn) => {
      btn.classList.toggle(
        "lang-btn--active",
        btn.getAttribute("data-lang-btn") === appState.lang
      );
    });
  }

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const code = btn.getAttribute("data-lang-btn");
      if (code === appState.lang) return;
      appState.lang = code;
      try {
        localStorage.setItem("acc_lang", code);
      } catch {}
      updateActive();
      renderAll();
    });
  });

  updateActive();
}

// ------------------ Dates ------------------

function formatISODate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return `${String(d).padStart(2, "0")}/${String(m).padStart(2, "0")}/${y}`;
}

function getStart(ev) {
  return ev.date || ev.start_date || null;
}

function getEnd(ev) {
  return ev.end_date || ev.date || ev.start_date || null;
}

function relativeDayLabel(i18n, lang, dateStr, todayStr) {
  const d = new Date(dateStr);
  const today = new Date(todayStr);
  const diff = Math.round((d - today) / 86400000);

  if (diff === 0) return ui(i18n, "today", lang, "Today");
  const tpl = ui(i18n, "in_days", lang, "in {n} days");
  return tpl.replace("{n}", diff);
}

function formatTimeAgo(date, lang) {
  const sec = Math.round((Date.now() - date.getTime()) / 1000);
  const t = (en, pt) => (lang === "pt" ? pt : en);

  if (sec < 60) return t("just now", "agora mesmo");
  const min = Math.round(sec / 60);
  if (min < 60) return t(`${min} minutes ago`, `há ${min} minutos`);
  const h = Math.round(min / 60);
  if (h < 24) return t(`${h} hours ago`, `há ${h} horas`);
  const d = Math.round(h / 24);
  return t(`${d} days ago`, `há ${d} dias`);
}

// ------------------ Classification ------------------

function isDeadline(ev) {
  const type = (ev.type || "").toLowerCase();
  return DEADLINE_TYPES.some((t) => type.includes(t));
}

function isCongress(ev) {
  const type = (ev.type || "").toLowerCase();
  const series = (ev.series || "").toLowerCase();
  const title = String(ev.title?.en || ev.title || "").toLowerCase();

  if (CONGRESS_TYPES.some((t) => type.includes(t))) return true;
  if (series.includes("wca") || series.includes("wfsa")) return true;
  if (title.includes("world congress") || title.includes("wca")) return true;

  return false;
}

function classifyEvents(events) {
  const todayStr = new Date().toISOString().slice(0, 10);

  const upcoming = events.filter((ev) => {
    const s = getStart(ev);
    return s && s >= todayStr;
  });

  const deadlines = [];
  const congresses = [];

  upcoming.forEach((ev) => {
    if (isDeadline(ev)) deadlines.push(ev);
    else if (isCongress(ev)) congresses.push(ev);
    else deadlines.push(ev);
  });

  const sortFn = (a, b) => (getStart(a) || "").localeCompare(getStart(b) || "");
  deadlines.sort(sortFn);
  congresses.sort(sortFn);

  const seen = new Set();
  const deduped = [];
  for (const ev of congresses) {
    const key = (ev.series || "").toLowerCase();
    if (key && seen.has(key)) continue;
    if (key) seen.add(key);
    deduped.push(ev);
  }

  return { deadlines, congresses: deduped };
}

// ------------------ Series → CSS class ------------------

function seriesToCssClass(series) {
  if (!series) return null;
  return `series-${String(series).toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}

// ------------------ Rendering ------------------

function clearContainer(sel) {
  const el = document.querySelector(sel);
  if (el) el.innerHTML = "";
  return el;
}

function openEventLink(url) {
  if (url) window.open(url, "_blank", "noopener");
}

function renderEventList(container, events, kind) {
  const { i18n, lang } = appState;
  if (!container) return;

  if (!events.length) {
    const div = document.createElement("div");
    div.className = "empty-state";
    div.textContent =
      kind === "deadlines"
        ? ui(i18n, "no_deadlines", lang, "No upcoming deadlines.")
        : ui(i18n, "no_congresses", lang, "No upcoming congresses.");
    container.appendChild(div);
    return;
  }

  const todayStr = new Date().toISOString().slice(0, 10);

  events.forEach((ev) => {
    const card = document.createElement("article");
    card.className = "event-card series-colored";

    const sc = seriesToCssClass(ev.series);
    if (sc) card.classList.add(sc);

    const title = document.createElement("div");
    title.className = "event-title";
    title.textContent = ev.title?.[lang] || ev.title?.en || ev.title;
    card.appendChild(title);

    const meta = document.createElement("div");
    meta.className = "event-meta-row";

    const start = getStart(ev);
    const end = getEnd(ev);
    if (start) {
      const chip = document.createElement("span");
      chip.className = "event-chip event-date-main";
      chip.textContent =
        formatISODate(start) +
        (end && end !== start ? `–${formatISODate(end)}` : "") +
        ` • ${relativeDayLabel(i18n, lang, start, todayStr)}`;
      meta.appendChild(chip);
    }

    if (kind === "deadlines" && ev.series) {
      const sc = document.createElement("span");
      sc.className = "event-chip event-series";
      sc.textContent = ev.series;
      meta.appendChild(sc);
    }

    card.appendChild(meta);

    if (ev.link) {
      card.tabIndex = 0;
      card.style.cursor = "pointer";
      card.onclick = () => openEventLink(ev.link);
      card.onkeydown = (e) => {
        if (e.key === "Enter" || e.key === " ") openEventLink(ev.link);
      };
    }

    container.appendChild(card);
  });
}

// ------------------ Static texts ------------------

function applyStaticTexts() {
  const { i18n, data, lang } = appState;

  document.querySelector("[data-subtitle]").textContent = ui(
    i18n,
    "subtitle",
    lang,
    "Upcoming deadlines and congress dates — auto-updated."
  );

  document.querySelector("[data-next-deadlines-title]").textContent = ui(
    i18n,
    "next_deadlines",
    lang,
    "Next deadlines"
  );

  document.querySelector("[data-upcoming-congresses-title]").textContent = ui(
    i18n,
    "upcoming_congresses",
    lang,
    "Upcoming congresses"
  );

  document.querySelector("[data-next-deadlines-count]").textContent = `${appState.deadlines.length} item(s)`;
  document.querySelector("[data-upcoming-congresses-count]").textContent = `${appState.congresses.length} item(s)`;

  const last = document.querySelector("[data-last-updated]");
  const dt = new Date(data.generated_at || Date.now());
  last.textContent = `${ui(i18n, "last_updated", lang, "Last updated")}: ${formatTimeAgo(
    dt,
    lang
  )}`;

  document.querySelector("[data-repo-link]").textContent = ui(
    i18n,
    "repo_link",
    lang,
    "View source on GitHub"
  );

  document.querySelector("[data-app-version]").textContent = `app: ${APP_VERSION}`;
}

function renderAll() {
  applyStaticTexts();
  renderEventList(clearContainer("[data-upcoming-congresses]"), appState.congresses, "congresses");
  renderEventList(clearContainer("[data-next-deadlines]"), appState.deadlines, "deadlines");
}

// ------------------ Main ------------------

async function main() {
  try {
    const [i18n, data] = await Promise.all([fetchJson(I18N_URL), fetchJson(DATA_URL)]);
    const { deadlines, congresses } = classifyEvents(data.events);

    appState.i18n = i18n;
    appState.data = data;
    appState.deadlines = deadlines;
    appState.congresses = congresses;
    appState.lang = chooseInitialLang();

    setupLangSwitcher();
    renderAll();
  } catch (err) {
    console.error(err);
  }
}

document.addEventListener("DOMContentLoaded", main);
