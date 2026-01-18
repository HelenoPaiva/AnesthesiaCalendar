// assets/app.js — full calendar logic with i18n, lang switch and ICS export
// Supports congresses with start_date/end_date (range events).
// Visible version marker included to defeat "is this file even loaded?" problems.

const APP_VERSION = "2026-01-17 congress-fix-2";

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

const CONGRESS_TYPES = [
  "congress",
  "meeting",
  "main_event",
  "annual_meeting",
];

const appState = {
  i18n: null,
  data: null,
  deadlines: [],
  congresses: [],
  lang: "en",
};

async function fetchJson(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch ${url}: ${res.status}`);
  const json = await res.json();
  console.log("[ACC]", APP_VERSION, "Loaded", url, "keys:", Object.keys(json || {}));
  return json;
}

function getStoredLang() {
  try {
    const v = localStorage.getItem("acc_lang");
    if (v === "en" || v === "pt") return v;
  } catch (e) {}
  return null;
}

function chooseInitialLang(i18n) {
  const params = new URLSearchParams(window.location.search);
  const paramLang = params.get("lang");
  if (paramLang === "pt" || paramLang === "en") return paramLang;

  const stored = getStoredLang();
  if (stored) return stored;

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
  if (!dateStr) return "";
  const [y, m, d] = dateStr.split("-").map((v) => parseInt(v, 10));
  if (!y || !m || !d) return dateStr;
  const dt = new Date(y, m - 1, d);
  const dd = String(dt.getDate()).padStart(2, "0");
  const mm = String(dt.getMonth() + 1).padStart(2, "0");
  const yyyy = dt.getFullYear();
  return `${dd}/${mm}/${yyyy}`;
}

// ---- Critical: main date for filtering and relative labels ----
function getEventStartISO(ev) {
  return ev.date || ev.start_date || null;
}
function getEventEndISO(ev) {
  return ev.end_date || ev.date || ev.start_date || null;
}

function formatTimeAgo(date, lang) {
  const now = new Date();
  const diffMs = now - date;
  const sec = Math.round(diffMs / 1000);
  const t = (en, pt) => (lang === "pt" ? pt : en);

  if (sec < 45) return t("just now", "agora mesmo");

  const min = Math.round(sec / 60);
  if (min < 60) return min === 1 ? t("1 minute ago", "há 1 minuto") : t(`${min} minutes ago`, `há ${min} minutos`);

  const h = Math.round(min / 60);
  if (h < 24) return h === 1 ? t("1 hour ago", "há 1 hora") : t(`${h} hours ago`, `há ${h} horas`);

  const d = Math.round(h / 24);
  return d === 1 ? t("1 day ago", "há 1 dia") : t(`${d} days ago`, `há ${d} dias`);
}

function relativeDayLabel(i18n, lang, dateStr, todayStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  const today = new Date(todayStr);
  const msPerDay = 24 * 60 * 60 * 1000;
  const diff = Math.round((d - today) / msPerDay);

  if (diff === 0) return ui(i18n, "today", lang, lang === "pt" ? "Hoje" : "Today");

  const tpl = ui(
    i18n,
    "in_days",
    lang,
    lang === "pt" ? "em {n} dias" : "in {n} days"
  );

  if (diff > 0) return tpl.replace("{n}", diff);
  return tpl.replace("{n}", `-${Math.abs(diff)}`);
}

function isDeadline(ev) {
  const type = (ev.type || "").toLowerCase();
  const titleStr = (ev.title && (ev.title.en || ev.title.pt)) || ev.title || "";
  const isDeadlineType = DEADLINE_TYPES.some((t) => type.includes(t));
  const looksDeadlineTitle = /deadline|submissions?|abstracts?/i.test(titleStr);
  return isDeadlineType || looksDeadlineTitle;
}

function isCongress(ev) {
  const type = (ev.type || "").toLowerCase();
  const titleStr = (ev.title && (ev.title.en || ev.title.pt)) || ev.title || "";
  const isCongressType = CONGRESS_TYPES.some((t) => type.includes(t));
  const looksCongressTitle = /congress|annual meeting|meeting/i.test(titleStr);
  return isCongressType || looksCongressTitle;
}

function classifyEvents(events, todayStr) {
  const safe = Array.isArray(events) ? events : [];

  // upcoming must consider date OR start_date
  const upcoming = safe.filter((ev) => {
    const startIso = getEventStartISO(ev);
    return startIso && startIso >= todayStr;
  });

  const deadlines = [];
  const congresses = [];

  upcoming.forEach((ev) => {
    if (isDeadline(ev)) {
      deadlines.push(ev);
      return;
    }
    if (isCongress(ev)) {
      congresses.push(ev);
      return;
    }
    // fallback
    if (ev.series && ev.year) congresses.push(ev);
    else deadlines.push(ev);
  });

  const sortByStartPriority = (a, b) => {
    const da = getEventStartISO(a) || "";
    const db = getEventStartISO(b) || "";
    if (da !== db) return da.localeCompare(db);
    const pa = typeof a.priority === "number" ? a.priority : 0;
    const pb = typeof b.priority === "number" ? b.priority : 0;
    return pb - pa;
  };

  deadlines.sort(sortByStartPriority);
  congresses.sort(sortByStartPriority);

  console.log("[ACC]", APP_VERSION, "classified:", {
    deadlines: deadlines.length,
    congresses: congresses.length,
  });

  return { deadlines, congresses };
}

function clearContainer(selector) {
  const el = document.querySelector(selector);
  if (el) el.innerHTML = "";
  return el;
}

function getTitleForEvent(ev, lang) {
  if (ev.title && (ev.title[lang] || ev.title.en)) return ev.title[lang] || ev.title.en;
  return ev.title || "(no title)";
}

// ---- ICS ----
function toICSDate(isoDate) {
  if (!isoDate) return null;
  const [y, m, d] = isoDate.split("-");
  if (!y || !m || !d) return null;
  return `${y}${m}${d}`;
}

function plusOneDayISO(isoDate) {
  const dt = new Date(isoDate);
  if (isNaN(dt.getTime())) return null;
  dt.setDate(dt.getDate() + 1);
  const yyyy = dt.getFullYear();
  const mm = String(dt.getMonth() + 1).padStart(2, "0");
  const dd = String(dt.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function buildICS(ev, lang) {
  const startIso = getEventStartISO(ev);
  if (!startIso) return null;

  const endIsoRaw = getEventEndISO(ev) || startIso;
  const endIso = plusOneDayISO(endIsoRaw) || plusOneDayISO(startIso);

  const dtStart = toICSDate(startIso);
  const dtEnd = toICSDate(endIso);

  const nowIso = new Date().toISOString().replace(/[-:]/g, "").split(".")[0];
  const dtStamp = `${nowIso}Z`;

  const title = getTitleForEvent(ev, lang);
  const descriptionParts = [];
  if (ev.series) descriptionParts.push(ev.series);
  if (ev.location) descriptionParts.push(ev.location);
  if (ev.link) descriptionParts.push(ev.link);
  const description = descriptionParts.join(" — ");

  const uidBase = ev.id || `${ev.series || "event"}-${startIso}`;
  const uid = `${uidBase}@anesthesia-congress-calendar`;

  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//AnesthesiaCongressCalendar//EN",
    "BEGIN:VEVENT",
    `UID:${uid}`,
    `DTSTAMP:${dtStamp}`,
    `DTSTART;VALUE=DATE:${dtStart}`,
    `DTEND;VALUE=DATE:${dtEnd}`,
    `SUMMARY:${title}`,
    description ? `DESCRIPTION:${description}` : "",
    ev.link ? `URL:${ev.link}` : "",
    "END:VEVENT",
    "END:VCALENDAR",
  ].filter(Boolean);

  return lines.join("\r\n");
}

function triggerICSDownload(ev, lang) {
  const ics = buildICS(ev, lang);
  if (!ics) return;

  const blob = new Blob([ics], { type: "text/calendar;charset=utf-8" });
  const url = URL.createObjectURL(blob);

  const safeId = (ev.id || `${ev.series || "event"}-${getEventStartISO(ev) || ""}`)
    .replace(/[^a-zA-Z0-9-_]/g, "_")
    .slice(0, 60);
  const filename = `${safeId || "event"}.ics`;

  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function renderEventList(container, events, i18n, lang, kind) {
  if (!container) return;
  container.innerHTML = "";

  if (!events || events.length === 0) {
    const emptyKey = kind === "deadlines" ? "no_deadlines" : "no_congresses";
    const fallback =
      kind === "deadlines"
        ? lang === "pt" ? "Nenhum prazo futuro." : "No upcoming deadlines."
        : lang === "pt" ? "Nenhum congresso futuro." : "No upcoming congresses.";
    const msg = ui(i18n, emptyKey, lang, fallback);

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

    const titleEl = document.createElement("div");
    titleEl.className = "event-title";
    titleEl.textContent = getTitleForEvent(ev, lang);
    card.appendChild(titleEl);

    const metaRow = document.createElement("div");
    metaRow.className = "event-meta-row";

    const startIso = getEventStartISO(ev);
    const endIso = ev.end_date || null;

    if (startIso) {
      const dateChip = document.createElement("span");
      dateChip.className = "event-chip event-date-main";

      let datePart = formatISODate(startIso);
      if (endIso && endIso !== startIso) {
        datePart = `${formatISODate(startIso)}–${formatISODate(endIso)}`;
      }

      const rel = relativeDayLabel(i18n, lang, startIso, todayStr);
      dateChip.textContent = `${datePart} • ${rel}`;
      metaRow.appendChild(dateChip);
    }

    if (ev.location) {
      const locChip = document.createElement("span");
      locChip.className = "event-chip";
      locChip.textContent = ev.location;
      metaRow.appendChild(locChip);
    }

    if (ev.series) {
      const seriesChip = document.createElement("span");
      seriesChip.className = "event-chip event-series";
      seriesChip.textContent = ev.series;
      metaRow.appendChild(seriesChip);
    }

    card.appendChild(metaRow);

    if (ev.link) {
      const linkRow = document.createElement("div");
      linkRow.className = "event-link";

      const openAnchor = document.createElement("a");
      openAnchor.href = ev.link;
      openAnchor.target = "_blank";
      openAnchor.rel = "noreferrer noopener";
      openAnchor.textContent = ui(i18n, "open", lang, lang === "pt" ? "Abrir" : "Open");
      linkRow.appendChild(openAnchor);

      const sep = document.createElement("span");
      sep.textContent = "·";
      linkRow.appendChild(sep);

      const icsBtn = document.createElement("button");
      icsBtn.type = "button";
      icsBtn.className = "event-ics-btn";
      icsBtn.textContent = lang === "pt" ? "Adicionar ao calendário" : "Save to calendar";
      icsBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        triggerICSDownload(ev, lang);
      });
      linkRow.appendChild(icsBtn);

      card.appendChild(linkRow);
    }

    container.appendChild(card);
  });
}

function applyStaticTexts() {
  const { i18n, data, lang } = appState;

  const subtitleEl = document.querySelector("[data-subtitle]");
  if (subtitleEl) {
    subtitleEl.textContent = ui(
      i18n,
      "subtitle",
      lang,
      lang === "pt"
        ? "Prazos e datas de congressos — auto-atualizado."
        : "Upcoming deadlines and congress dates — auto-updated."
    );
  }

  const deadlinesTitleEl = document.querySelector("[data-next-deadlines-title]");
  if (deadlinesTitleEl) {
    deadlinesTitleEl.textContent = ui(i18n, "next_deadlines", lang, lang === "pt" ? "Próximos prazos" : "Next deadlines");
  }

  const congressesTitleEl = document.querySelector("[data-upcoming-congresses-title]");
  if (congressesTitleEl) {
    congressesTitleEl.textContent = ui(i18n, "upcoming_congresses", lang, lang === "pt" ? "Próximos congressos" : "Upcoming congresses");
  }

  const lastUpdatedEl = document.querySelector("[data-last-updated]");
  if (lastUpdatedEl) {
    const label = ui(i18n, "last_updated", lang, lang === "pt" ? "Atualizado" : "Last updated");
    let dt = null;
    if (data && data.generated_at) {
      const parsed = new Date(data.generated_at);
      if (!isNaN(parsed.getTime())) dt = parsed;
    }
    if (!dt) dt = new Date();
    lastUpdatedEl.textContent = `${label}: ${formatTimeAgo(dt, lang)}`;
  }

  const dlCount = document.querySelector("[data-next-deadlines-count]");
  if (dlCount) dlCount.textContent = (lang === "pt" ? `${appState.deadlines.length} item(ns)` : `${appState.deadlines.length} item(s)`);

  const cgCount = document.querySelector("[data-upcoming-congresses-count]");
  if (cgCount) cgCount.textContent = (lang === "pt" ? `${appState.congresses.length} item(ns)` : `${appState.congresses.length} item(s)`);

  const verEl = document.querySelector("[data-app-version]");
  if (verEl) verEl.textContent = `app: ${APP_VERSION}`;
}

function renderAll() {
  applyStaticTexts();

  const deadlinesContainer = clearContainer("[data-next-deadlines]");
  const congressesContainer = clearContainer("[data-upcoming-congresses]");

  renderEventList(deadlinesContainer, appState.deadlines, appState.i18n, appState.lang, "deadlines");
  renderEventList(congressesContainer, appState.congresses, appState.i18n, appState.lang, "congresses");
}

function setupLangSwitcher() {
  const switchEl = document.querySelector("[data-lang-switch]");
  if (!switchEl) return;

  const buttons = Array.from(switchEl.querySelectorAll("[data-lang-btn]"));

  function updateActive() {
    buttons.forEach((btn) => {
      const code = btn.getAttribute("data-lang-btn");
      if (code === appState.lang) btn.classList.add("lang-btn--active");
      else btn.classList.remove("lang-btn--active");
    });
  }

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const code = btn.getAttribute("data-lang-btn");
      if (code !== "en" && code !== "pt") return;
      if (code === appState.lang) return;
      appState.lang = code;
      try { localStorage.setItem("acc_lang", code); } catch (e) {}
      updateActive();
      renderAll();
    });
  });

  updateActive();
}

async function main() {
  try {
    const [i18n, data] = await Promise.all([fetchJson(I18N_URL), fetchJson(DATA_URL)]);

    if (!Array.isArray(data.events)) {
      console.error("events.json payload:", data);
      throw new Error("events.json missing {events: []}");
    }

    const todayStr = new Date().toISOString().slice(0, 10);
    const { deadlines, congresses } = classifyEvents(data.events, todayStr);

    appState.i18n = i18n;
    appState.data = data;
    appState.deadlines = deadlines;
    appState.congresses = congresses;
    appState.lang = chooseInitialLang(i18n);

    console.log("[ACC]", APP_VERSION, "lang:", appState.lang);

    setupLangSwitcher();
    renderAll();
  } catch (err) {
    console.error("[ACC] Fatal error:", err);
    const container = document.querySelector("[data-next-deadlines]") || document.body;
    const div = document.createElement("div");
    div.className = "empty-state error-state";
    div.textContent = "Error loading calendar data. Check console logs for details.";
    container.appendChild(div);
  }
}

document.addEventListener("DOMContentLoaded", main);