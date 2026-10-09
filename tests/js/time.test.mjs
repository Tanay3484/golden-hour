// Run with: node tests/js/time.test.mjs  (no npm deps; loads the browser module via a data: URL)
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../../src/golden_hour/static/time.js", import.meta.url), "utf8");
const { zonedToEpoch, formatCountdown, buildIcs } = await import(
  "data:text/javascript," + encodeURIComponent(source)
);

const iso = (s, tz) => new Date(zonedToEpoch(s, tz)).toISOString();
assert.equal(iso("2026-10-08T18:00:00", "Europe/Berlin"), "2026-10-08T16:00:00.000Z"); // CEST
assert.equal(iso("2026-10-09T06:30:00", "Asia/Kolkata"), "2026-10-09T01:00:00.000Z"); // +5:30
assert.equal(iso("2026-10-26T17:00:00", "Europe/Berlin"), "2026-10-26T16:00:00.000Z"); // after DST
assert.equal(iso("2026-10-08T18:15:00", "America/New_York"), "2026-10-08T22:15:00.000Z");

const M = 60000;
assert.deepEqual(formatCountdown(72 * M, 112 * M), { phase: "soon", text: "Starts in 1h 12m" });
assert.deepEqual(formatCountdown(5 * M, 45 * M), { phase: "soon", text: "Starts in 5 min" });
assert.deepEqual(formatCountdown(30 * 1000, 40 * M), { phase: "soon", text: "Starts in 1 min" });
assert.deepEqual(formatCountdown(-1, 25 * M), { phase: "now", text: "Now: go outside! 25 min left" });
assert.equal(formatCountdown(-50 * M, -10 * M).phase, "done");

const ics = buildIcs({
  title: "Golden Hour: Chase the last light; west, then back",
  description: "1. Walk west\n2. Watch the sky",
  startIso: "2026-10-08T18:00:00",
  endIso: "2026-10-08T18:40:00",
  timezone: "Europe/Berlin",
});
assert.ok(ics.includes("DTSTART:20261008T160000Z"));
assert.ok(ics.includes("DTEND:20261008T164000Z"));
assert.ok(ics.includes("light\\; west\\, then"));
assert.ok(ics.includes("1. Walk west\\n2. Watch"));
assert.ok(ics.endsWith("END:VCALENDAR\r\n"));
for (const line of ics.split("\r\n")) assert.ok(Buffer.byteLength(line) <= 75, `too long: ${line}`);
console.log("time.js: all assertions passed");
