// assets/app.js
// Stable, repo-friendly SPA logic:
// - EN default + PT toggle (persisted)
// - User-system timezone for "today"
// - Fetches data/events.json + data/i18n.json
// - Renders "Today" + Upcoming Deadlines/Congresses
// - Uses dashboard theme classes (acc-*)
// - Reminder chip generates ICS via assets/ics.js

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
  // safe for attributes; keep it simple
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

  // Matches acc-toggle styles; we just set inline background for active state
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

function computeTodayDisplay(lang) {
  const locale = localeFor(lang);
  const now = new Date();
  return new Intl.DateTimeFormat(locale, {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "2-digit",
  }).format(now);
}

function timeZoneHint() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "";
  } catch {
    return "";
  }
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

function isTodayDeadline(ev, todayYMD) {
  return !!ev.date && ev.date === todayYMD;
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
  // path like ["ui","today"] or ["types","abstract_deadline"]
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
  const todayLabel = $("today-label");
  const updatedLabel = $("updated-label");
  const sectionToday = $("section-today");
  const sectionUpcoming = $("section-upcoming");
  const nextDeadlines = $("next-deadlines");
  const nextCongresses = $("next-congresses");
  const footerText = $("footer-text");

  if (subtitle) subtitle.textContent = t(i18n, ["ui", "subtitle"], lang, "Upcoming deadlines and congress dates — auto-updated.");
  if (todayLabel) todayLabel.textContent = t(i18n, ["ui", "today"], lang, "Today");
  if (updatedLabel) updatedLabel.textContent = t(i18n, ["ui", "last_updated"], lang, "Last updated");
  if (sectionToday) sectionToday.textContent = t(i18n, ["ui", "happening_today"], lang, "Happening today");
  if (sectionUpcoming) sectionUpcoming.textContent = t(i18n, ["ui", "upcoming"], lang, "Upcoming");
  if (nextDeadlines) nextDeadlines.textContent = t(i18n, ["ui", "next_deadlines"], lang, "Next deadlines");
  if (nextCongresses) nextCongresses.textContent = t(i18n, ["ui", "upcoming_congresses"], lang, "Upcoming congresses");
  if (footerText) footerText.textContent = t(i18n, ["ui", "footer"], lang, "Built as a static GitHub Pages site. Data refreshes via GitHub Actions.");
}

function statusBadgeHTML(ev, i18n, lang) {
  const status = ev.status || "active";
  const label = t(i18n, ["status", status], lang, status);

  let cls = "badge badge-active";
  if (status === "missing") cls = "badge badge-missing";
  if (status === "ended") cls = "badge badge-ended";
  if (status === "manual") cls = "badge badge-manual";

  return `<span class="${cls}">${escapeHtml(label)}</span>`;
}

function typeTitle(ev, i18n, lang) {
  if (ev.title && typeof ev.title === "object" && ev.title[lang]) return ev.title[lang];

  const series = (ev.series || "").trim();
  const year = ev.year ? String(ev.year) : "";
  const typeLabel = t(i18n, ["types", ev.type], lang, ev.type);

  // Keep consistent: "ASA 2026 — Scientific abstracts deadline"
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

  // Future countdown for single-day deadlines
  if (ev.type !== "congress" && ev.date && ev.date > todayYMD) {
    const d = daysUntil(ev.date);
    if (typeof d === "number") {
      const inText = t(i18n, ["ui", "in_days"], lang, "in {n} days").replace("{n}", String(d));
      extra += ` · <span class="acc-muted">${escapeHtml(inText)}</span>`;
    }
  }

  // Missing event: last seen tag line
  if (ev.status === "missing" && ev.last_seen_at) {
    const lastSeen = String(ev.last_seen_at).slice(0, 10);
    const seenText = t(i18n, ["ui", "last_seen"], lang, "last seen {d}").replace("{d}", lastSeen);
    extra += ` · <span style="color: rgba(245, 158, 11, 0.95)">${escapeHtml(seenText)}</span>`;
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

  return `
    <div class="acc-card">
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

function setTopStatus(i18n, data, lang) {
  const todayValue = $("today-value");
  const updatedValue = $("updated-value");
  const tzHint = $("tz-hint");

  if (todayValue) todayValue.textContent = computeTodayDisplay(lang);
  if (updatedValue) updatedValue.textContent = data.generated_at ? String(data.generated_at) : "—";

  const tz = timeZoneHint();
  if (tzHint) tzHint.textContent = tz ? `(${tz})` : "";
}

function renderAll(i18n, data, lang) {
  const todayYMD = ymdTodayLocal();

  applyUIStrings(i18n, lang);
  setTopStatus(i18n, data, lang);

  const todayContainer = $("today-container");
  const deadlinesContainer = $("deadlines-container");
  const congressesContainer = $("congresses-container");
  const deadlinesCount = $("deadlines-count");
  const congressesCount = $("congresses-count");

  const all = Array.isArray(data.events) ? data.events.slice() : [];
  all.sort(sortByWhen);
  window.__ACC_EVENTS__ = all;

  // Today items: deadlines today OR congress ongoing
  const todayItems = all.filter((ev) => isTodayDeadline(ev, todayYMD) || isOngoing(ev, todayYMD));

  if (todayItems.length === 0) {
    // next actionable (not past)
    const next = all.find((ev) => !isPastEvent(ev, todayYMD));
    const text = next
      ? t(i18n, ["ui", "nothing_today_next"], lang, "Nothing today. Next: {x}").replace("{x}", typeTitle(next, i18n, lang))
      : t(i18n, ["ui", "nothing_today"], lang, "Nothing today.");
    renderEmpty(todayContainer, text);
  } else {
    renderList(todayContainer, todayItems, i18n, lang, todayYMD, "");
  }

  // Upcoming deadlines (non-congress) excluding past
  const upcomingDeadlines = all
    .filter((ev) => ev.type !== "congress")
    .filter((ev) => !isPastEvent(ev, todayYMD))
    .slice(0, 10);

  // Upcoming congresses excluding past
  const upcomingCongresses = all
    .filter((ev) => ev.type === "congress")
    .filter((ev) => !isPastEvent(ev, todayYMD))
    .slice(0, 10);

  if (deadlinesCount) deadlinesCount.textContent = `${upcomingDeadlines.length}/10`;
  if (congressesCount) congressesCount.textContent = `${upcomingCongresses.length}/10`;

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
  // Single delegated handler; stable even across rerenders.
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

    // Language affects ICS titles; read current lang each click
    const lang = getLang();
    downloadICSForEvent(ev, i18nRef.current, lang);
  });
}

async function main() {
  const [i18n, data] = await Promise.all([fetchJSON(I18N_URL), fetchJSON(DATA_URL)]);

  // Keep i18n in a mutable ref for handlers
  const i18nRef = { current: i18n };

  let lang = getLang();
  setActiveLangButton(lang);

  // Toggle buttons
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

  // First render
  renderAll(i18nRef.current, data, lang);
}

main().catch((err) => {
  console.error(err);

  const todayContainer = $("today-container");
  const msg = err?.message ? String(err.message) : String(err);

  if (todayContainer) {
    todayContainer.innerHTML = `
      <div class="acc-card" style="border-color: rgba(248, 113, 113, 0.55);">
        <div class="acc-card-title" style="color: rgba(248, 113, 113, 0.95);">Failed to load data.</div>
        <div class="acc-card-meta mono" style="color: rgba(226, 232, 240, 0.85); margin-top: 6px;">
          ${escapeHtml(msg)}
        </div>
      </div>
    `;
  }
});
