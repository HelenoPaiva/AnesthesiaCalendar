// app.js — robust version: works with events.json OR ledger.json, always renders

// ----------------------
// Basic helpers
// ----------------------

function parseISODate(dateStr) {
  if (!dateStr || typeof dateStr !== "string") return null;
  var parts = dateStr.split("-");
  if (parts.length !== 3) return null;
  var y = parseInt(parts[0], 10);
  var m = parseInt(parts[1], 10);
  var d = parseInt(parts[2], 10);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

function todayLocalMidnight() {
  var now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

function formatDateRange(startStr, endStr, locale) {
  var start = parseISODate(startStr);
  var end = parseISODate(endStr);
  if (!start || !end) return "";

  var optsShort = { day: "numeric", month: "short", year: "numeric" };

  if (
    start.getFullYear() === end.getFullYear() &&
    start.getMonth() === end.getMonth()
  ) {
    var monthYear = end.toLocaleDateString(locale, {
      month: "long",
      year: "numeric"
    });
    return start.getDate() + "–" + end.getDate() + " " + monthYear;
  }

  return (
    start.toLocaleDateString(locale, optsShort) +
    " → " +
    end.toLocaleDateString(locale, optsShort)
  );
}

function formatSingleDate(dateStr, locale) {
  var d = parseISODate(dateStr);
  if (!d) return "";
  return d.toLocaleDateString(locale, {
    day: "numeric",
    month: "short",
    year: "numeric"
  });
}

function humanizeLastUpdated(iso, locale) {
  if (!iso) return "";
  var updated = new Date(iso);
  if (isNaN(updated.getTime())) return "";

  var now = new Date();
  var diffMs = now - updated;
  var diffSec = Math.floor(diffMs / 1000);
  var diffMin = Math.floor(diffSec / 60);
  var diffHours = Math.floor(diffMin / 60);
  var diffDays = Math.floor(diffHours / 24);

  var en = {
    justNow: "just now",
    minutes: function (n) { return n + " minute" + (n !== 1 ? "s" : "") + " ago"; },
    hours: function (n) { return n + " hour" + (n !== 1 ? "s" : "") + " ago"; },
    days: function (n) { return n + " day" + (n !== 1 ? "s" : "") + " ago"; }
  };
  var pt = {
    justNow: "agora mesmo",
    minutes: function (n) { return "há " + n + " minuto" + (n !== 1 ? "s" : ""); },
    hours: function (n) { return "há " + n + " hora" + (n !== 1 ? "s" : ""); },
    days: function (n) { return "há " + n + " dia" + (n !== 1 ? "s" : ""); }
  };

  var t = locale === "pt" ? pt : en;

  if (diffMin < 1) return t.justNow;
  if (diffHours < 1) return t.minutes(diffMin);
  if (diffDays < 1) return t.hours(diffHours);
  return t.days(diffDays);
}

// ----------------------
// i18n
// ----------------------

var I18N = {
  en: {
    lastUpdated: "Last updated",
    upcoming: "Upcoming",
    nextDeadlines: "Next deadlines",
    upcomingCongresses: "Upcoming congresses",
    noDeadlines: "No upcoming deadlines found.",
    noCongresses: "No upcoming congresses found.",
    remindMe: "Remind me",
    open: "Open",
    statusActive: "Active"
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
    statusActive: "Ativo"
  }
};

var currentLocale = "en";

function setLocale(locale) {
  currentLocale = locale;
  document.documentElement.setAttribute("data-locale", locale);
  render();
}

// ----------------------
// Data state
// ----------------------

var rawEvents = [];
var lastUpdatedAt = null;

// ----------------------
// Main render
// ----------------------

function render() {
  var t = I18N[currentLocale];

  var lastUpdatedEl = document.querySelector("[data-last-updated]");
  if (lastUpdatedEl) {
    lastUpdatedEl.textContent = lastUpdatedAt
      ? humanizeLastUpdated(lastUpdatedAt, currentLocale)
      : "—";
  }

  var mainTitleEl = document.querySelector("[data-section-upcoming-title]");
  if (mainTitleEl) mainTitleEl.textContent = t.upcoming;

  var deadlinesTitleEl = document.querySelector("[data-next-deadlines-title]");
  if (deadlinesTitleEl) deadlinesTitleEl.textContent = t.nextDeadlines;

  var congressesTitleEl = document.querySelector("[data-upcoming-congresses-title]");
  if (congressesTitleEl) congressesTitleEl.textContent = t.upcomingCongresses;

  var deadlinesContainer = document.querySelector("[data-next-deadlines]");
  var congressesContainer = document.querySelector("[data-upcoming-congresses]");
  if (!deadlinesContainer || !congressesContainer) return;

  deadlinesContainer.innerHTML = "";
  congressesContainer.innerHTML = "";

  var today = todayLocalMidnight();
  var events = rawEvents || [];

  // === Deadlines: all upcoming
  var upcomingDeadlines = [];
  for (var i = 0; i < events.length; i++) {
    var ev = events[i];
    if (!ev || !ev.type || ev.type === "congress" || !ev.date) continue;
    var d = parseISODate(ev.date);
    if (d && d >= today) {
      upcomingDeadlines.push({ ev: ev, d: d });
    }
  }
  upcomingDeadlines.sort(function (a, b) { return a.d - b.d; });
  if (upcomingDeadlines.length > 10) {
    upcomingDeadlines = upcomingDeadlines.slice(0, 10);
  }

  // === Congresses: all upcoming (for now, no dedupe)
  var upcomingCongresses = [];
  for (var j = 0; j < events.length; j++) {
    var ev2 = events[j];
    if (!ev2 || ev2.type !== "congress" || !ev2.start_date || !ev2.end_date) continue;
    var start = parseISODate(ev2.start_date);
    var end = parseISODate(ev2.end_date);
    if (end && end >= today) {
      upcomingCongresses.push({ ev: ev2, start: start, end: end });
    }
  }
  upcomingCongresses.sort(function (a, b) { return a.start - b.start; });
  if (upcomingCongresses.length > 10) {
    upcomingCongresses = upcomingCongresses.slice(0, 10);
  }

  // === Render deadlines
  if (upcomingDeadlines.length === 0) {
    var emptyD = document.createElement("div");
    emptyD.className = "empty-message";
    emptyD.textContent = t.noDeadlines;
    deadlinesContainer.appendChild(emptyD);
  } else {
    for (var dIdx = 0; dIdx < upcomingDeadlines.length; dIdx++) {
      var pair = upcomingDeadlines[dIdx];
      deadlinesContainer.appendChild(renderDeadlineCard(pair.ev, pair.d, t));
    }
  }

  // === Render congresses
  if (upcomingCongresses.length === 0) {
    var emptyC = document.createElement("div");
    emptyC.className = "empty-message";
    emptyC.textContent = t.noCongresses;
    congressesContainer.appendChild(emptyC);
  } else {
    for (var cIdx = 0; cIdx < upcomingCongresses.length; cIdx++) {
      var pairC = upcomingCongresses[cIdx];
      congressesContainer.appendChild(
        renderCongressCard(pairC.ev, pairC.start, pairC.end, t)
      );
    }
  }

  // Counters
  var deadlinesCountEl = document.querySelector("[data-next-deadlines-count]");
  if (deadlinesCountEl) {
    deadlinesCountEl.textContent =
      Math.min(upcomingDeadlines.length, 10) + "/10";
  }
  var congressesCountEl = document.querySelector("[data-upcoming-congresses-count]");
  if (congressesCountEl) {
    congressesCountEl.textContent =
      Math.min(upcomingCongresses.length, 10) + "/10";
  }
}

function seriesClass(series) {
  if (!series) return "";
  var s = String(series).toLowerCase();
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
  var card = document.createElement("article");
  card.className = "card " + seriesClass(ev.series);

  var header = document.createElement("div");
  header.className = "card-header";

  var titleEl = document.createElement("h3");
  titleEl.className = "card-title";
  var title = null;
  if (ev.title && ev.title[currentLocale]) {
    title = ev.title[currentLocale];
  } else if (ev.title && ev.title.en) {
    title = ev.title.en;
  } else if (ev.id) {
    title = ev.id;
  } else {
    title = "Deadline";
  }
  titleEl.textContent = title;

  var status = document.createElement("span");
  status.className = "chip chip--status";
  status.textContent = t.statusActive;

  header.appendChild(titleEl);
  header.appendChild(status);

  var body = document.createElement("div");
  body.className = "card-body";

  var line = document.createElement("p");
  line.className = "card-meta";
  line.textContent =
    formatSingleDate(ev.date, currentLocale) +
    " — " +
    daysDiffLabel(dateObj);
  body.appendChild(line);

  var actions = document.createElement("div");
  actions.className = "card-actions";

  var remindBtn = document.createElement("button");
  remindBtn.className = "btn btn-secondary";
  remindBtn.textContent = t.remindMe;
  remindBtn.addEventListener("click", function () {
    alert("Reminder not implemented yet. (Local-only, no email.)");
  });

  var openLink = document.createElement("a");
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
  var card = document.createElement("article");
  card.className = "card " + seriesClass(ev.series);

  var header = document.createElement("div");
  header.className = "card-header";

  var titleEl = document.createElement("h3");
  titleEl.className = "card-title";
  var title = null;
  if (ev.title && ev.title[currentLocale]) {
    title = ev.title[currentLocale];
  } else if (ev.title && ev.title.en) {
    title = ev.title.en;
  } else if (ev.id) {
    title = ev.id;
  } else {
    title = "Congress";
  }
  titleEl.textContent = title;

  var status = document.createElement("span");
  status.className = "chip chip--status";
  status.textContent = t.statusActive;

  header.appendChild(titleEl);
  header.appendChild(status);

  var body = document.createElement("div");
  body.className = "card-body";

  var range = document.createElement("p");
  range.className = "card-meta";
  range.textContent =
    formatDateRange(ev.start_date, ev.end_date, currentLocale) +
    " · " +
    (ev.location || "");
  body.appendChild(range);

  var actions = document.createElement("div");
  actions.className = "card-actions";

  var remindBtn = document.createElement("button");
  remindBtn.className = "btn btn-secondary";
  remindBtn.textContent = t.remindMe;
  remindBtn.addEventListener("click", function () {
    alert("Reminder not implemented yet. (Local-only, no email.)");
  });

  var openLink = document.createElement("a");
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

function daysDiffLabel(dateObj) {
  var today = todayLocalMidnight();
  var diffMs = dateObj - today;
  var diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays < 0) {
    var n = Math.abs(diffDays);
    return currentLocale === "pt"
      ? "há " + n + " dia" + (n !== 1 ? "s" : "")
      : n + " day" + (n !== 1 ? "s" : "") + " ago";
  }
  if (diffDays === 0) {
    return currentLocale === "pt" ? "hoje" : "today";
  }
  return currentLocale === "pt"
    ? "em " + diffDays + " dia" + (diffDays !== 1 ? "s" : "")
    : "in " + diffDays + " day" + (diffDays !== 1 ? "s" : "");
}

// ----------------------
// Data loading (robust against different shapes)
// ----------------------

function extractEventsFromData(data) {
  if (!data) return [];

  // Case 1: already an array of events
  if (Object.prototype.toString.call(data) === "[object Array]") {
    return data;
  }

  // Case 2: { events: [...], updated_at: ... }
  if (data.events && Object.prototype.toString.call(data.events) === "[object Array]") {
    return data.events;
  }

  // Case 3: ledger-style { items: { key: { event: {...} } }, ... }
  if (data.items && typeof data.items === "object") {
    var out = [];
    for (var key in data.items) {
      if (!data.items.hasOwnProperty(key)) continue;
      var item = data.items[key];
      if (item && item.event) out.push(item.event);
    }
    return out;
  }

  return [];
}

function loadData() {
  fetch("data/events.json", { cache: "no-cache" })
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (data) {
      rawEvents = extractEventsFromData(data);
      if (data && data.updated_at) {
        lastUpdatedAt = data.updated_at;
      } else {
        lastUpdatedAt = null;
      }
      render();
    })
    .catch(function (err) {
      console.error("Failed to load events:", err);
      // Still render something (empty state) so the UI isn't frozen
      rawEvents = [];
      lastUpdatedAt = null;
      render();
    });
}

// ----------------------
// Language toggle wiring
// ----------------------

function initLocaleToggle() {
  var enBtn = document.querySelector("[data-lang-en]");
  var ptBtn = document.querySelector("[data-lang-pt]");

  if (enBtn) {
    enBtn.addEventListener("click", function () {
      setLocale("en");
    });
  }
  if (ptBtn) {
    ptBtn.addEventListener("click", function () {
      setLocale("pt");
    });
  }
}

// ----------------------
// Boot
// ----------------------

document.addEventListener("DOMContentLoaded", function () {
  initLocaleToggle();
  // Render once with empty data so "No upcoming..." appears even if fetch dies
  render();
  loadData();
});