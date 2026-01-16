// assets/app.js
import { downloadICSForEvent } from "./ics.js";

const DATA_URL = "./data/events.json";
const I18N_URL = "./data/i18n.json";

const LANG_KEY = "acc_lang";
const DEFAULT_LANG = "en";

function $(id) {
  return document.getElementById(id);
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

function getLang() {
  const saved = localStorage.getItem(LANG_KEY);
  return saved === "pt" ? "pt" : DEFAULT_LANG;
}

function setLang(lang) {
  localStorage.setItem(LANG_KEY, lang);
  setActiveLangButton(lang);
}

function setActiveLangButton(lang) {
  const en = $("lang-en");
  const pt = $("lang-pt");
  if (!en || !pt) return;

  const activeStyle = {
    background: "rgba(148, 163, 184, 0.14)",
    color: "rgba(226, 232, 240, 0.95)",
  };
  const inactiveStyle = {
    background: "transparent",
    color: "rgba(148, 163, 184, 0.85)",
  };

  const apply = (el, isActive) => {
    el.style.background = isActive ? activeStyle.background : inactiveStyle.background;
    el.style.color = isActive ? activeStyle.color : inactiveStyle.color;
  };

  apply(en, lang === "en");
  apply(pt, lang === "pt");
}

async function fetchJSON(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch ${url}: ${res.status}`);
  return res.json();
}

function localeFor(lang) {
  return lang === "pt" ? "pt-BR" : "en";
}

function ymdTodayLocal() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

// Date-only parsing in local time (avoid Date("YYYY-MM-DD") UTC pitfalls)
function parseYMDLocal(ymd) {
  const [y, m, d] = String(ymd).split("-").map((x) => parseInt(x, 10));
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d, 0, 0, 0, 0);
}

function formatDateLocal(ymd, lang) {
  const dt = parseYMDLocal(ymd);
  if (!dt) return String(ymd || "—");
  return new Intl.DateTimeFormat(localeFor(lang), {
    year: "numeric",
    month: "short",
    day: "2-digit",
  }).format(dt);
}

function daysUntil(ymd) {
  const target = parseYMDLocal(ymd);
  if (!target) return null;

  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0);
  const ms = target.getTime() - today.getTime();
  return Math.round(ms / 86400000);
}

function isOngoing(ev, todayYMD) {
  return ev.type === "congress" && ev.start_date && ev.end_date && ev.start_date <= todayYMD && todayYMD <= ev.end_date;
}

function isPastEvent(ev, todayYMD) {
  if (ev.type === "congress") return !!ev.end_date && ev.end_date < todayYMD;
  return !!ev.date && ev.date < todayYMD;
}

function isFutureOrOngoing(ev, todayYMD) {
  if (isOngoing(ev, todayYMD)) return true;
  if (ev.type === "congress") return !!ev.start_date && ev.start_date > todayYMD;
  return !!ev.date && ev.date > todayYMD;
}

function whenKey(ev) {
  return ev.type === "congress" ? (ev.start_date || "9999-12-31") : (ev.date || "9999-12-31");
}

function sortByWhen(a, b) {
  const ak = whenKey(a);
  const bk = whenKey(b);
  if (ak < bk) return -1;
  if (ak > bk) return 1;
  const ap = a.priority ?? 0;
  const bp = b.priority ?? 0;
  return bp - ap;
}

function t(i18n, path, lang, fallback) {
  let cur = i18n;
  for (const k of path) {
    if (!cur || typeof cur !== "object") return fallback;
    cur = cur[k];
  }
  if (cur && typeof cur === "object" && (lang in cur)) return cur[lang];
  return fallback;
}

function applyUIStrings(i18n, lang) {
  const subtitle = $("subtitle");
  const updatedLabel = $("updated-label");
  const sectionUpcoming = $("section-upcoming");
  const nextDeadlines = $("next-deadlines");
  const nextCongresses = $("next-congresses");
  const footerText = $("footer-text");

  if (subtitle) subtitle.textContent = t(i18n, ["ui", "subtitle"], lang, "Upcoming deadlines and congress dates — auto-updated.");
  if (updatedLabel) updatedLabel.textContent = t(i18n, ["ui", "last_updated"], lang, "Last updated");
  if (sectionUpcoming) sectionUpcoming.textContent = t(i18n, ["ui", "upcoming"], lang, "Upcoming");
  if (nextDeadlines) nextDeadlines.textContent = t(i18n, ["ui", "next_deadlines"], lang, "Next deadlines");
  if (nextCongresses) nextCongresses.textContent = t(i18n, ["ui", "upcoming_congresses"], lang, "Upcoming congresses");
  if (footerText) footerText.textContent = t(i18n, ["ui", "footer"], lang, "Built as a static GitHub Pages site. Data refreshes via GitHub Actions.");
}

// human-readable "x hours ago" for last_updated
function formatUpdatedAgo(iso, lang) {
  if (!iso) return "—";
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return iso;

  const now = new Date();
  let diffMs = now.getTime() - dt.getTime();
  if (diffMs < 0) diffMs = 0;
  const seconds = Math.floor(diffMs / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  const isPt = lang === "pt";

  if (seconds < 45) return isPt ? "agora mesmo" : "just now";
  if (minutes < 60) {
    const n = minutes;
    if (isPt) return n === 1 ? "há 1 minuto" : `há ${n} minutos`;
    return n === 1 ? "1 minute ago" : `${n} minutes ago`;
  }
  if (hours < 48) {
    const n = hours;
    if (isPt) return n === 1 ? "há 1 hora" : `há ${n} horas`;
    return n === 1 ? "1 hour ago" : `${n} hours ago`;
  }
  const n = days;
  if (isPt) return n === 1 ? "há 1 dia" : `há ${n} dias`;
  return n === 1 ? "1 day ago" : `${n} days ago`;
}

function setTopStatus(data, lang) {
  const updatedValue = $("updated-value");
  if (!updatedValue) return;

  const iso = data.generated_at || "";
  updatedValue.textContent = iso ? formatUpdatedAgo(iso, lang) : "—";
}

// --- visual series differentiation ----------------------------------------

function seriesClass(ev) {
  const series = String(ev.series || "").toUpperCase();
  switch (series) {
    case "ASA":
      return "acc-card-series-asa";
    case "CBA":
      return "acc-card-series-cba";
    case "COPA":
      return "acc-card-series-copa";
    case "WCA":
      return "acc-card-series-wca";
    case "EUROANAESTHESIA":
      return "acc-card-series-euro";
    case "CLASA":
      return "acc-card-series-clasa";
    case "LASRA":
      return "acc-card-series-lasra";
    default:
      return "acc-card-series-default";
  }
}

function statusBadgeHTML(ev, i18n, lang) {
  const status = ev.status || "active";
  const label = t(i18n, ["status", status], lang, status);

  let cls = "badge badge-active";
  if (status === "ended") cls = "badge badge-ended";

  return `<span class="${cls}">${escapeHtml(label)}</span>`;
}

function typeTitle(ev, i18n, lang) {
  if (ev.title && typeof ev.title === "object" && ev.title[lang]) return ev.title[lang];

  const series = (ev.series || "").trim();
  const year = ev.year ? String(ev.year) : "";
  const typeLabel = t(i18n, ["types", ev.type], lang, ev.type);

  const left = [series, year].filter(Boolean).join(" ");
  return left ? `${left} — ${typeLabel}` : typeLabel;
}

function whenLabel(ev, lang) {
  if (ev.type === "congress") {
    const s = formatDateLocal(ev.start_date, lang);
    const e = formatDateLocal(ev.end_date, lang);
    return `${s} → ${e}`;
  }
  return formatDateLocal(ev.date, lang);
}

function metaLineHTML(ev, i18n, lang, todayYMD) {
  const when = whenLabel(ev, lang);
  const loc = ev.location ? ` · ${escapeHtml(ev.location)}` : "";

  let extra = "";

  if (ev.type !== "congress" && ev.date && ev.date >= todayYMD) {
    const d = daysUntil(ev.date);
    if (typeof d === "number") {
      const inText = t(i18n, ["ui", "in_days"], lang, "in {n} days").replace("{n}", String(d));
      extra += ` · <span class="acc-muted">${escapeHtml(inText)}</span>`;
    }
  }

  return `${escapeHtml(when)}${loc}${extra}`;
}

function actionsHTML(ev, i18n, lang, todayYMD) {
  const remindText = t(i18n, ["ui", "remind_me"], lang, "Remind me");
  const openText = t(i18n, ["ui", "open"], lang, "Open");

  const enabled = isFutureOrOngoing(ev, todayYMD);
  const disabledAttr = enabled ? "" : ' aria-disabled="true" disabled';

  const remindBtn = `
    <button class="chip" data-action="remind" data-id="${escapeAttr(ev.id)}"${disabledAttr}>
      ${escapeHtml(remindText)}
    </button>
  `;

  const openBtn = ev.link
    ? `<a class="chip" data-action="open" href="${escapeAttr(ev.link)}" target="_blank" rel="noreferrer">${escapeHtml(openText)}</a>`
    : "";

  return `${remindBtn}${openBtn}`;
}

function cardHTML(ev, i18n, lang, todayYMD) {
  const title = typeTitle(ev, i18n, lang);
  const badge = statusBadgeHTML(ev, i18n, lang);
  const meta = metaLineHTML(ev, i18n, lang, todayYMD);
  const actions = actionsHTML(ev, i18n, lang, todayYMD);
  const seriesCls = seriesClass(ev);

  return `
    <div class="acc-card ${seriesCls}">
      <div class="acc-card-head">
        <div class="min-w-0">
          <div class="acc-card-title break-words">${escapeHtml(title)}</div>
          <div class="acc-card-meta">${meta}</div>
        </div>
        <div class="shrink-0">${badge}</div>
      </div>
      <div class="acc-card-actions">${actions}</div>
    </div>
  `;
}

function renderEmpty(container, text) {
  container.innerHTML = `
    <div class="acc-card">
      <div class="acc-card-title">${escapeHtml(text)}</div>
    </div>
  `;
}

function renderList(container, items, i18n, lang, todayYMD, emptyText) {
  if (!items || items.length === 0) {
    renderEmpty(container, emptyText);
    return;
  }
  container.innerHTML = items.map((ev) => cardHTML(ev, i18n, lang, todayYMD)).join("");
}

function setTopStatusCounts(deadlinesCount, congressesCount, upcomingDeadlines, upcomingCongresses) {
  if (deadlinesCount) deadlinesCount.textContent = `${upcomingDeadlines.length}/10`;
  if (congressesCount) congressesCount.textContent = `${upcomingCongresses.length}/10`;
}

function renderAll(i18n, data, lang) {
  const todayYMD = ymdTodayLocal();

  applyUIStrings(i18n, lang);
  setTopStatus(data, lang);

  const deadlinesContainer = $("deadlines-container");
  const congressesContainer = $("congresses-container");
  const deadlinesCount = $("deadlines-count");
  const congressesCount = $("congresses-count");

  const all = Array.isArray(data.events) ? data.events.slice() : [];
  all.sort(sortByWhen);
  window.__ACC_EVENTS__ = all;

  const upcomingDeadlines = all
    .filter((ev) => ev.type !== "congress")
    .filter((ev) => !isPastEvent(ev, todayYMD))
    .slice(0, 10);

  const upcomingCongresses = all
    .filter((ev) => ev.type === "congress")
    .filter((ev) => !isPastEvent(ev, todayYMD))
    .slice(0, 10);

  setTopStatusCounts(deadlinesCount, congressesCount, upcomingDeadlines, upcomingCongresses);

  renderList(
    deadlinesContainer,
    upcomingDeadlines,
    i18n,
    lang,
    todayYMD,
    t(i18n, ["ui", "no_deadlines"], lang, "No upcoming deadlines found.")
  );

  renderList(
    congressesContainer,
    upcomingCongresses,
    i18n,
    lang,
    todayYMD,
    t(i18n, ["ui", "no_congresses"], lang, "No upcoming congresses found.")
  );
}

function bindGlobalHandlers(i18nRef) {
  document.body.addEventListener("click", (e) => {
    const target = e.target;
    if (!target) return;

    const btn = target.closest?.("[data-action='remind']");
    if (!btn) return;

    if (btn.hasAttribute("disabled") || btn.getAttribute("aria-disabled") === "true") return;

    const id = btn.getAttribute("data-id");
    if (!id) return;

    const events = window.__ACC_EVENTS__ || [];
    const ev = events.find((x) => x.id === id);
    if (!ev) return;

    const lang = getLang();
    downloadICSForEvent(ev, i18nRef.current, lang);
  });
}

async function main() {
  const [i18n, data] = await Promise.all([fetchJSON(I18N_URL), fetchJSON(DATA_URL)]);

  const i18nRef = { current: i18n };

  let lang = getLang();
  setActiveLangButton(lang);

  const enBtn = $("lang-en");
  const ptBtn = $("lang-pt");
  if (enBtn) {
    enBtn.addEventListener("click", () => {
      lang = "en";
      setLang(lang);
      renderAll(i18nRef.current, data, lang);
    });
  }
  if (ptBtn) {
    ptBtn.addEventListener("click", () => {
      lang = "pt";
      setLang(lang);
      renderAll(i18nRef.current, data, lang);
    });
  }

  bindGlobalHandlers(i18nRef);
  renderAll(i18nRef.current, data, lang);
}

main().catch((err) => {
  console.error(err);

  const container = $("deadlines-container") || document.body;
  const msg = err?.message ? String(err.message) : String(err);

  if (container) {
    container.innerHTML = `
      <div class="acc-card" style="border-color: rgba(248, 113, 113, 0.55);">
        <div class="acc-card-title" style="color: rgba(248, 113, 113, 0.95);">Failed to load data.</div>
        <div class="acc-card-meta mono" style="color: rgba(226, 232, 240, 0.85); margin-top: 6px;">
          ${escapeHtml(msg)}
        </div>
      </div>
    `;
  }
});
