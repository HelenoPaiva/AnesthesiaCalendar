import { downloadICSForEvent } from "./ics.js";

const DATA_URL = "./data/events.json";
const I18N_URL = "./data/i18n.json";

const LANG_KEY = "acc_lang";
const DEFAULT_LANG = "en";

function $(id) {
  return document.getElementById(id);
}

function setActiveLangButton(lang) {
  const en = $("lang-en");
  const pt = $("lang-pt");
  const base = "px-3 py-1.5 rounded-lg text-sm font-medium";
  const active = " bg-slate-900 text-white";
  const inactive = " text-slate-700 hover:bg-slate-100";

  en.className = base + (lang === "en" ? active : inactive);
  pt.className = base + (lang === "pt" ? active : inactive);
}

function getLang() {
  const saved = localStorage.getItem(LANG_KEY);
  return saved === "pt" ? "pt" : "en";
}

function setLang(lang) {
  localStorage.setItem(LANG_KEY, lang);
  setActiveLangButton(lang);
}

function formatDateLocal(ymd, locale) {
  // Parse as local date safely: new Date(y, m-1, d)
  const [y, m, d] = ymd.split("-").map((x) => parseInt(x, 10));
  const dt = new Date(y, m - 1, d, 0, 0, 0, 0);
  return new Intl.DateTimeFormat(locale, { year: "numeric", month: "short", day: "2-digit" }).format(dt);
}

function daysUntil(ymd) {
  const [y, m, d] = ymd.split("-").map((x) => parseInt(x, 10));
  const target = new Date(y, m - 1, d, 0, 0, 0, 0);
  const now = new Date();
  // today at midnight local
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0);
  const ms = target.getTime() - today.getTime();
  return Math.round(ms / 86400000);
}

function ymdTodayLocal() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function isOngoing(event, todayYMD) {
  if (event.type !== "congress") return false;
  if (!event.start_date || !event.end_date) return false;
  return event.start_date <= todayYMD && todayYMD <= event.end_date;
}

function isTodayDeadline(event, todayYMD) {
  return !!event.date && event.date === todayYMD;
}

function isFutureEvent(event, todayYMD) {
  if (event.type === "congress" && event.start_date) return event.start_date > todayYMD;
  if (event.date) return event.date > todayYMD;
  return false;
}

function isPastEvent(event, todayYMD) {
  if (event.type === "congress" && event.end_date) return event.end_date < todayYMD;
  if (event.date) return event.date < todayYMD;
  return false;
}

function sortByWhen(a, b) {
  const aKey = a.type === "congress" ? a.start_date : a.date;
  const bKey = b.type === "congress" ? b.start_date : b.date;
  if (aKey < bKey) return -1;
  if (aKey > bKey) return 1;
  // tie-break: priority desc
  const ap = a.priority ?? 0;
  const bp = b.priority ?? 0;
  return bp - ap;
}

function badgeHTML(event, i18n, lang) {
  const status = event.status || "active";
  const label = (i18n.status?.[status]?.[lang]) || status;

  let cls = "badge badge-active";
  if (status === "missing") cls = "badge badge-missing";
  if (status === "ended") cls = "badge badge-ended";
  if (status === "manual") cls = "badge badge-manual";

  return `<span class="${cls}">${escapeHtml(label)}</span>`;
}

function typeLabel(event, i18n, lang) {
  if (event.title?.[lang]) return event.title[lang];
  const series = event.series || "";
  const year = event.year ? String(event.year) : "";
  const t = (i18n.types?.[event.type]?.[lang]) || event.type;
  // For congress we prefer "Series YYYY — Congress"
  if (event.type === "congress") return `${series} ${year} — ${t}`;
  return `${series} ${year} — ${t}`;
}

function whenLabel(event, i18n, lang, locale) {
  if (event.type === "congress") {
    const s = formatDateLocal(event.start_date, locale);
    const e = formatDateLocal(event.end_date, locale);
    return `${s} → ${e}`;
  }
  return formatDateLocal(event.date, locale);
}

function metaLine(event, i18n, lang, todayYMD) {
  const locale = lang === "pt" ? "pt-BR" : "en";
  const when = whenLabel(event, i18n, lang, locale);
  const loc = event.location ? ` · ${escapeHtml(event.location)}` : "";
  let extra = "";

  // Show "in X days" for future single-date deadlines
  if (event.type !== "congress" && event.date && event.date > todayYMD) {
    const d = daysUntil(event.date);
    const inText = (i18n.ui?.in_days?.[lang] || "in {n} days").replace("{n}", String(d));
    extra = ` · <span class="text-slate-600">${escapeHtml(inText)}</span>`;
  }

  // For missing events: last seen note
  if (event.status === "missing" && event.last_seen_at) {
    const lastSeen = event.last_seen_at.slice(0, 10);
    const seenText = (i18n.ui?.last_seen?.[lang] || "last seen {d}").replace("{d}", lastSeen);
    extra += ` · <span class="text-amber-700">${escapeHtml(seenText)}</span>`;
  }

  return `<div class="text-sm text-slate-700">${escapeHtml(when)}${loc}${extra}</div>`;
}

function actionsHTML(event, i18n, lang, todayYMD) {
  const isFuture = isFutureEvent(event, todayYMD) || isOngoing(event, todayYMD);
  const remindText = i18n.ui?.remind_me?.[lang] || "Remind me";
  const openText = i18n.ui?.open?.[lang] || "Open";

  const remindDisabled = isFuture ? "" : ' aria-disabled="true" disabled';
  const remindBtn = `
    <button class="chip" data-action="remind" data-id="${escapeAttr(event.id)}"${remindDisabled}>
      ${escapeHtml(remindText)}
    </button>
  `;

  const openBtn = event.link
    ? `<a class="chip" data-action="open" href="${escapeAttr(event.link)}" target="_blank" rel="noreferrer">${escapeHtml(openText)}</a>`
    : "";

  return `<div class="flex flex-wrap items-center gap-2 mt-2">${remindBtn}${openBtn}</div>`;
}

function cardHTML(event, i18n, lang, todayYMD) {
  const title = typeLabel(event, i18n, lang);
  const badge = badgeHTML(event, i18n, lang);
  const meta = metaLine(event, i18n, lang, todayYMD);
  const actions = actionsHTML(event, i18n, lang, todayYMD);

  return `
    <div class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div class="flex items-start justify-between gap-2">
        <div class="min-w-0">
          <div class="text-base font-semibold leading-snug break-words">${escapeHtml(title)}</div>
          ${meta}
        </div>
        <div class="shrink-0">${badge}</div>
      </div>
      ${actions}
    </div>
  `;
}

function renderEmpty(container, text) {
  container.innerHTML = `
    <div class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm text-sm text-slate-600">
      ${escapeHtml(text)}
    </div>
  `;
}

function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(s) {
  return escapeHtml(s).replaceAll("`", "&#096;");
}

async function fetchJSON(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch ${url}: ${res.status}`);
  return res.json();
}

function applyUIStrings(i18n, lang) {
  const ui = i18n.ui || {};
  const t = (key, fallback) => ui[key]?.[lang] || fallback;

  $("subtitle").textContent = t("subtitle", "Upcoming deadlines and congress dates — auto-updated.");
  $("today-label").textContent = t("today", "Today");
  $("updated-label").textContent = t("last_updated", "Last updated");
  $("section-today").textContent = t("happening_today", "Happening today");
  $("section-upcoming").textContent = t("upcoming", "Upcoming");
  $("next-deadlines").textContent = t("next_deadlines", "Next deadlines");
  $("next-congresses").textContent = t("upcoming_congresses", "Upcoming congresses");
  $("footer-text").textContent = t("footer", "Built as a static GitHub Pages site. Data refreshes via GitHub Actions.");
}

function bindActions({ i18n, lang, events, todayYMD }) {
  // Delegate reminders
  document.body.addEventListener("click", (e) => {
    const btn = e.target?.closest?.("[data-action='remind']");
    if (!btn) return;

    if (btn.hasAttribute("disabled") || btn.getAttribute("aria-disabled") === "true") return;

    const id = btn.getAttribute("data-id");
    const ev = events.find((x) => x.id === id);
    if (!ev) return;

    downloadICSForEvent(ev, i18n, lang);
  });
}

function computeTodayDisplay(lang) {
  const locale = lang === "pt" ? "pt-BR" : "en";
  const now = new Date();
  const fmt = new Intl.DateTimeFormat(locale, {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "2-digit",
  });
  return fmt.format(now);
}

function timeZoneHint() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "";
  } catch {
    return "";
  }
}

async function main() {
  const i18n = await fetchJSON(I18N_URL);
  const data = await fetchJSON(DATA_URL);

  let lang = getLang();
  setActiveLangButton(lang);

  const todayYMD = ymdTodayLocal();
  $("today-value").textContent = computeTodayDisplay(lang);
  $("tz-hint").textContent = timeZoneHint() ? `(${timeZoneHint()})` : "";

  $("updated-value").textContent = data.generated_at ? String(data.generated_at) : "—";

  // Lang toggle
  $("lang-en").addEventListener("click", () => {
    lang = "en";
    setLang(lang);
    renderAll(i18n, data, lang);
  });
  $("lang-pt").addEventListener("click", () => {
    lang = "pt";
    setLang(lang);
    renderAll(i18n, data, lang);
  });

  // First render
  renderAll(i18n, data, lang);

  // Bind actions (uses latest events reference)
  // We re-bind once; we keep the same array object by rebuilding inside renderAll,
  // so we store it globally in window for simplicity.
  bindActions({
    i18n,
    lang,
    events: window.__ACC_EVENTS__ || [],
    todayYMD,
  });
}

function renderAll(i18n, data, lang) {
  const todayYMD = ymdTodayLocal();
  applyUIStrings(i18n, lang);

  $("today-value").textContent = computeTodayDisplay(lang);
  $("updated-value").textContent = data.generated_at ? String(data.generated_at) : "—";

  const allEvents = Array.isArray(data.events) ? data.events.slice() : [];
  allEvents.sort(sortByWhen);
  window.__ACC_EVENTS__ = allEvents;

  const todayContainer = $("today-container");
  const deadlinesContainer = $("deadlines-container");
  const congressesContainer = $("congresses-container");

  const todayItems = allEvents.filter(
    (ev) => isTodayDeadline(ev, todayYMD) || isOngoing(ev, todayYMD)
  );

  if (todayItems.length === 0) {
    // If none today, show next actionable item
    const next = allEvents.find((ev) => !isPastEvent(ev, todayYMD));
    const emptyText =
      next
        ? (i18n.ui?.nothing_today_next?.[lang] || "Nothing today. Next: {x}")
            .replace("{x}", typeLabel(next, i18n, lang))
        : (i18n.ui?.nothing_today?.[lang] || "Nothing today.");
    renderEmpty(todayContainer, emptyText);
  } else {
    todayContainer.innerHTML = todayItems.map((ev) => cardHTML(ev, i18n, lang, todayYMD)).join("");
  }

  const upcomingDeadlines = allEvents
    .filter((ev) => ev.type !== "congress")
    .filter((ev) => !isPastEvent(ev, todayYMD))
    .slice(0, 10);

  const upcomingCongresses = allEvents
    .filter((ev) => ev.type === "congress")
    .filter((ev) => !isPastEvent(ev, todayYMD))
    .slice(0, 10);

  $("deadlines-count").textContent = `${upcomingDeadlines.length}/10`;
  $("congresses-count").textContent = `${upcomingCongresses.length}/10`;

  if (upcomingDeadlines.length === 0) {
    renderEmpt
