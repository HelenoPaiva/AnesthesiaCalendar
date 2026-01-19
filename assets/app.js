// assets/app.js
// FINAL SIMPLIFIED CHIP LOGIC
// - Congresses: DATE CHIP ONLY (series color applied)
// - Deadlines: DATE CHIP + SERIES CHIP ONLY
// - No location chips anywhere

const APP_VERSION = "2026-01-18 simplified-chips-1";

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
  if (!res.ok) throw new Error(`Failed to fetch ${url}`);
  return res.json();
}

// ------------------ Language ------------------

function chooseInitialLang() {
  try {
    const stored = localStorage.getItem("acc_lang");
    if (stored === "en" || stored === "pt") return stored;
  } catch {}
  return navigator.language?.startsWith("pt") ? "pt" : "en";
}

function ui(i18n, key, lang, fallback) {
  return i18n?.ui?.[key]?.[lang] || i18n?.ui?.[key]?.en || fallback || key;
}

// ------------------ Dates ------------------

function formatISODate(d) {
  if (!d) return "";
  const dt = new Date(d);
  if (isNaN(dt)) return d;
  return `${String(dt.getDate()).padStart(2, "0")}/${String(
    dt.getMonth() + 1
  ).padStart(2, "0")}/${dt.getFullYear()}`;
}

function getStart(ev) {
  return ev.date || ev.start_date || null;
}
function getEnd(ev) {
  return ev.end_date || ev.date || ev.start_date || null;
}

function relativeLabel(dateStr, lang) {
  const today = new Date();
  const d = new Date(dateStr);
  const diff = Math.round((d - today) / (24 * 60 * 60 * 1000));

  if (diff === 0) return lang === "pt" ? "hoje" : "today";
  if (diff > 0)
    return lang === "pt" ? `em ${diff} dias` : `in ${diff} days`;
  return lang === "pt"
    ? `há ${Math.abs(diff)} dias`
    : `${Math.abs(diff)} days ago`;
}

// ------------------ Classification ------------------

function isDeadline(ev) {
  return DEADLINE_TYPES.some((t) => (ev.type || "").includes(t));
}

function isCongress(ev) {
  return CONGRESS_TYPES.some((t) => (ev.type || "").includes(t));
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
    if (isCongress(ev)) congresses.push(ev);
    else deadlines.push(ev);
  });

  const sortFn = (a, b) =>
    (getStart(a) || "").localeCompare(getStart(b) || "");

  deadlines.sort(sortFn);
  congresses.sort(sortFn);

  return { deadlines, congresses };
}

// ------------------ Series → CSS class ------------------

function seriesToCssClass(series) {
  if (!series) return null;
  const key = series.toLowerCase();
  if (key === "asa") return "series-asa";
  if (key.startsWith("euro")) return "series-euroanaesthesia";
  return `series-${key.replace(/[^a-z0-9]+/g, "-")}`;
}

// ------------------ Rendering ------------------

function renderList(container, events, lang, kind) {
  container.innerHTML = "";

  if (!events.length) {
    container.innerHTML = `<div class="empty-state">${
      lang === "pt" ? "Nenhum item." : "No items."
    }</div>`;
    return;
  }

  events.forEach((ev) => {
    const card = document.createElement("article");
    card.className = "event-card series-colored";

    const sc = seriesToCssClass(ev.series);
    if (sc) card.classList.add(sc);

    const title = document.createElement("div");
    title.className = "event-title";
    title.textContent =
      ev.title?.[lang] || ev.title?.en || ev.title || "";
    card.appendChild(title);

    const meta = document.createElement("div");
    meta.className = "event-meta-row";

    // DATE CHIP (always)
    const start = getStart(ev);
    const end = getEnd(ev);

    if (start) {
      const chip = document.createElement("span");
      chip.className = "event-chip event-date-main";

      let txt = formatISODate(start);
      if (end && end !== start)
        txt += `–${formatISODate(end)}`;

      txt += ` • ${relativeLabel(start, lang)}`;
      chip.textContent = txt;
      meta.appendChild(chip);
    }

    // SERIES CHIP (deadlines only)
    if (kind === "deadlines" && ev.series) {
      const s = document.createElement("span");
      s.className = "event-chip event-series";
      s.textContent = ev.series;
      meta.appendChild(s);
    }

    card.appendChild(meta);

    if (ev.link) {
      const row = document.createElement("div");
      row.className = "event-link";

      const a = document.createElement("a");
      a.href = ev.link;
      a.target = "_blank";
      a.textContent = ui(
        appState.i18n,
        "open",
        lang,
        lang === "pt" ? "Abrir" : "Open"
      );
      row.appendChild(a);

      const btn = document.createElement("button");
      btn.className = "event-ics-btn";
      btn.textContent =
        lang === "pt"
          ? "Adicionar ao calendário"
          : "Save to calendar";
      btn.onclick = () => triggerICS(ev, lang);
      row.appendChild(btn);

      card.appendChild(row);
    }

    container.appendChild(card);
  });
}

// ------------------ ICS ------------------

function triggerICS(ev, lang) {
  const s = getStart(ev);
  if (!s) return;

  const e = getEnd(ev) || s;

  const ics = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "BEGIN:VEVENT",
    `DTSTART;VALUE=DATE:${s.replace(/-/g, "")}`,
    `DTEND;VALUE=DATE:${e.replace(/-/g, "")}`,
    `SUMMARY:${ev.title?.[lang] || ev.title?.en || ev.title}`,
    ev.link ? `URL:${ev.link}` : "",
    "END:VEVENT",
    "END:VCALENDAR",
  ]
    .filter(Boolean)
    .join("\r\n");

  const blob = new Blob([ics], { type: "text/calendar" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${ev.id || "event"}.ics`;
  a.click();
}

// ------------------ Main ------------------

async function main() {
  const [i18n, data] = await Promise.all([
    fetchJson(I18N_URL),
    fetchJson(DATA_URL),
  ]);

  const { deadlines, congresses } = classifyEvents(data.events);

  appState.i18n = i18n;
  appState.data = data;
  appState.deadlines = deadlines;
  appState.congresses = congresses;
  appState.lang = chooseInitialLang();

  renderList(
    document.querySelector("[data-next-deadlines]"),
    deadlines,
    appState.lang,
    "deadlines"
  );

  renderList(
    document.querySelector("[data-upcoming-congresses]"),
    congresses,
    appState.lang,
    "congresses"
  );

  document.querySelector("[data-app-version]").textContent =
    "app: " + APP_VERSION;
}

document.addEventListener("DOMContentLoaded", main);
