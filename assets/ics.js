// Minimal ICS generator (client-side)
// - Creates all-day events for deadlines and multi-day all-day events for congress ranges
// - Adds default alarms: 30d, 7d, 1d before start

function pad2(n) {
  return String(n).padStart(2, "0");
}

function ymdToDateLocal(ymd) {
  // ymd: "YYYY-MM-DD"
  const [y, m, d] = ymd.split("-").map((x) => parseInt(x, 10));
  return new Date(y, m - 1, d, 0, 0, 0, 0);
}

function formatDateICSAllDay(dt) {
  // all-day uses YYYYMMDD
  const y = dt.getFullYear();
  const m = pad2(dt.getMonth() + 1);
  const d = pad2(dt.getDate());
  return `${y}${m}${d}`;
}

function escapeICS(text) {
  return String(text || "")
    .replace(/\\/g, "\\\\")
    .replace(/\n/g, "\\n")
    .replace(/,/g, "\\,")
    .replace(/;/g, "\\;");
}

function buildUID(id) {
  // stable-ish UID. If you change domain later, it still works.
  return `${id}@anesthesia-congress-calendar`;
}

function makeICS({ uid, title, description, location, startYMD, endYMDExclusive, alarmsDays = [30, 7, 1] }) {
  const dtstamp = new Date();
  const dtstampStr =
    dtstamp.getUTCFullYear().toString() +
    pad2(dtstamp.getUTCMonth() + 1) +
    pad2(dtstamp.getUTCDate()) +
    "T" +
    pad2(dtstamp.getUTCHours()) +
    pad2(dtstamp.getUTCMinutes()) +
    pad2(dtstamp.getUTCSeconds()) +
    "Z";

  const lines = [];
  lines.push("BEGIN:VCALENDAR");
  lines.push("VERSION:2.0");
  lines.push("PRODID:-//Anesthesia Congress Calendar//EN");
  lines.push("CALSCALE:GREGORIAN");
  lines.push("METHOD:PUBLISH");

  lines.push("BEGIN:VEVENT");
  lines.push(`UID:${escapeICS(uid)}`);
  lines.push(`DTSTAMP:${dtstampStr}`);
  lines.push(`SUMMARY:${escapeICS(title)}`);
  if (description) lines.push(`DESCRIPTION:${escapeICS(description)}`);
  if (location) lines.push(`LOCATION:${escapeICS(location)}`);

  lines.push(`DTSTART;VALUE=DATE:${startYMD}`);
  lines.push(`DTEND;VALUE=DATE:${endYMDExclusive}`);

  // Alarms
  for (const days of alarmsDays) {
    lines.push("BEGIN:VALARM");
    lines.push("ACTION:DISPLAY");
    lines.push(`DESCRIPTION:${escapeICS(title)}`);
    lines.push(`TRIGGER:-P${days}D`);
    lines.push("END:VALARM");
  }

  lines.push("END:VEVENT");
  lines.push("END:VCALENDAR");

  return lines.join("\r\n");
}

export function downloadICSForEvent(event, i18n, lang) {
  const isRange = event.type === "congress" && event.start_date && event.end_date;

  const series = event.series || "";
  const year = event.year ? String(event.year) : "";
  const typeLabel = (i18n?.types?.[event.type]?.[lang]) || event.type;

  const title =
    (event.title?.[lang]) ||
    `${series} ${year} — ${typeLabel}`;

  const link = event.link ? `\n${event.link}` : "";
  const statusNote =
    event.status && event.status !== "active"
      ? `\n${(i18n?.status?.[event.status]?.[lang]) || event.status}`
      : "";

  const description = `${title}${statusNote}${link}`.trim();
  const location = event.location || "";

  if (!isRange) {
    const dt = ymdToDateLocal(event.date);
    const start = formatDateICSAllDay(dt);
    // all-day DTEND is exclusive; +1 day
    const endDt = new Date(dt.getFullYear(), dt.getMonth(), dt.getDate() + 1);
    const end = formatDateICSAllDay(endDt);

    const ics = makeICS({
      uid: buildUID(event.id),
      title,
      description,
      location,
      startYMD: start,
      endYMDExclusive: end,
    });

    triggerDownload(ics, safeFilename(`${event.id}.ics`));
    return;
  }

  // Range congress
  const startDt = ymdToDateLocal(event.start_date);
  const endDtInclusive = ymdToDateLocal(event.end_date);
  // DTEND exclusive: end_date + 1
  const endExclusive = new Date(
    endDtInclusive.getFullYear(),
    endDtInclusive.getMonth(),
    endDtInclusive.getDate() + 1
  );

  const start = formatDateICSAllDay(startDt);
  const end = formatDateICSAllDay(endExclusive);

  const ics = makeICS({
    uid: buildUID(event.id),
    title,
    description,
    location,
    startYMD: start,
    endYMDExclusive: end,
  });

  triggerDownload(ics, safeFilename(`${event.id}.ics`));
}

function triggerDownload(content, filename) {
  const blob = new Blob([content], { type: "text/calendar;charset=utf-8" });
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();

  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function safeFilename(name) {
  return String(name).replace(/[^a-zA-Z0-9._-]/g, "_");
}
