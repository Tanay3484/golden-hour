// Countdown + calendar export (R5.1, R5.2). Server times are naive wall-clock times in the
// forecast location's IANA time zone, so everything converts through `zonedToEpoch`.

const MINUTE = 60_000;

function tzOffsetMs(epoch, timeZone) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(new Date(epoch));
  const v = Object.fromEntries(parts.map((p) => [p.type, Number(p.value)]));
  return Date.UTC(v.year, v.month - 1, v.day, v.hour, v.minute, v.second) - epoch;
}

/** "2026-10-08T18:00:00" (wall time in `timeZone`) -> epoch milliseconds. */
export function zonedToEpoch(isoLocal, timeZone) {
  const [d, t] = isoLocal.split("T");
  const [Y, M, D] = d.split("-").map(Number);
  const [h, m, s = 0] = t.split(":").map(Number);
  const asUtc = Date.UTC(Y, M - 1, D, h, m, Math.floor(s));
  const first = tzOffsetMs(asUtc, timeZone);
  const second = tzOffsetMs(asUtc - first, timeZone); // corrects across DST changes
  return asUtc - second;
}

export function formatCountdown(msUntilStart, msUntilEnd) {
  if (msUntilEnd <= 0) return { phase: "done", text: "Done. Hope it was a good one." };
  if (msUntilStart <= 0) {
    const left = Math.ceil(msUntilEnd / MINUTE);
    return { phase: "now", text: `Now: go outside! ${left} min left` };
  }
  const totalMin = Math.ceil(msUntilStart / MINUTE);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  const text = h ? `Starts in ${h}h ${m}m` : `Starts in ${m} min`;
  return { phase: "soon", text };
}

/** Updates `el` every second. Returns a function that stops the timer. */
export function startCountdown(el, startIso, endIso, timeZone) {
  const start = zonedToEpoch(startIso, timeZone);
  const end = zonedToEpoch(endIso, timeZone);
  const tick = () => {
    const now = Date.now();
    const { phase, text } = formatCountdown(start - now, end - now);
    el.textContent = text;
    el.dataset.phase = phase;
    if (phase === "done") clearInterval(timer);
  };
  const timer = setInterval(tick, 1000);
  tick();
  return () => clearInterval(timer);
}

function icsDate(epoch) {
  return new Date(epoch).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
}

function icsEscape(text) {
  return String(text)
    .replace(/\\/g, "\\\\")
    .replace(/;/g, "\\;")
    .replace(/,/g, "\\,")
    .replace(/\r?\n/g, "\\n");
}

// RFC 5545 lines must be <= 75 octets; 60 characters leaves room for multi-byte UTF-8.
function fold(line) {
  const chunks = [];
  for (let i = 0; i < line.length; i += 60) chunks.push(line.slice(i, i + 60));
  return chunks.join("\r\n ");
}

export function buildIcs({ title, description = "", startIso, endIso, timezone }) {
  const start = zonedToEpoch(startIso, timezone);
  const end = zonedToEpoch(endIso, timezone);
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Golden Hour//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "BEGIN:VEVENT",
    `UID:${icsDate(start)}-${Math.random().toString(36).slice(2, 10)}@golden-hour`,
    `DTSTAMP:${icsDate(Date.now())}`,
    `DTSTART:${icsDate(start)}`,
    `DTEND:${icsDate(end)}`,
    `SUMMARY:${icsEscape(title)}`,
    `DESCRIPTION:${icsEscape(description)}`,
    "BEGIN:VALARM",
    "TRIGGER:-PT10M",
    "ACTION:DISPLAY",
    `DESCRIPTION:${icsEscape(title)}`,
    "END:VALARM",
    "END:VEVENT",
    "END:VCALENDAR",
  ];
  return lines.map(fold).join("\r\n") + "\r\n";
}

export function downloadIcs(icsString, filename = "golden-hour.ics") {
  const url = URL.createObjectURL(new Blob([icsString], { type: "text/calendar" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
