import { buildIcs, downloadIcs, startCountdown } from "./time.js";

const $ = (sel) => document.querySelector(sel);

// Must be defined before `state`, which reads saved hobbies on load.
const HOBBIES = [
  ["photography", "📷 Photography"],
  ["nature", "🐦 Nature & birds"],
  ["history", "🏛️ History"],
  ["art", "🎨 Art"],
  ["running", "🏃 Running & walking"],
  ["reading", "📖 Reading & sketching"],
  ["coffee", "☕ Coffee outside"],
  ["sports", "⚽ Sports"],
];
const MAX_HOBBIES = 3;

const state = {
  loc: null, // { lat, lon, name }
  plan: null,
  chosen: null,
  suggestion: null,
  places: null, // { places: [...], lines: {id: line} } when the places card is showing
  stopCountdown: null,
  suggestToken: 0,
  unit: loadUnit(),
  hobbies: loadHobbies(),
};

// ---------- hobbies (R7) ----------

function loadHobbies() {
  try {
    const saved = JSON.parse(localStorage.getItem("gh-hobbies") || "[]");
    const known = new Set(HOBBIES.map(([id]) => id));
    return Array.isArray(saved) ? saved.filter((h) => known.has(h)).slice(0, MAX_HOBBIES) : [];
  } catch {
    return [];
  }
}

function saveHobbies() {
  try {
    localStorage.setItem("gh-hobbies", JSON.stringify(state.hobbies));
  } catch {
    /* storage unavailable: keep in memory only */
  }
}

function renderHobbies() {
  const full = state.hobbies.length >= MAX_HOBBIES;
  $("#hobbies").replaceChildren(
    ...HOBBIES.map(([id, label]) => {
      const on = state.hobbies.includes(id);
      const el = button(label, () => {
        state.hobbies = on ? state.hobbies.filter((h) => h !== id) : [...state.hobbies, id];
        saveHobbies();
        renderHobbies();
      });
      el.className = "chip";
      el.setAttribute("aria-pressed", String(on));
      el.disabled = full && !on;
      return el;
    }),
  );
}

// ---------- units (R3.4) ----------

function loadUnit() {
  try {
    return localStorage.getItem("gh-unit") === "F" ? "F" : "C";
  } catch {
    return "C";
  }
}

function saveUnit(unit) {
  try {
    localStorage.setItem("gh-unit", unit);
  } catch {
    /* storage unavailable: keep in memory only */
  }
}

const toUnit = (c) => (state.unit === "F" ? Math.round((c * 9) / 5 + 32) : Math.round(c));
const fmtTemp = (c) => `${toUnit(c)}°${state.unit}`;
const convertText = (s) => s.replace(/(-?\d+(?:\.\d+)?)°C/g, (_, c) => fmtTemp(Number(c)));

$("#unit-toggle").addEventListener("click", () => {
  state.unit = state.unit === "C" ? "F" : "C";
  saveUnit(state.unit);
  renderUnitButton();
  if (state.chosen) renderWindow(state.chosen);
  if (state.plan) renderAlternates();
});

function renderUnitButton() {
  $("#unit-toggle").textContent = `°${state.unit}`;
}

// ---------- location (R1) ----------

function locate() {
  if (!("geolocation" in navigator)) return showCitySearch("Location isn't available in this browser.");
  $("#locate-status").textContent = "Finding your location…";
  navigator.geolocation.getCurrentPosition(
    (pos) => setLocation({ lat: pos.coords.latitude, lon: pos.coords.longitude, name: null }),
    () => showCitySearch("No problem, you can search for your city instead."),
    { timeout: 10000, maximumAge: 10 * 60 * 1000 },
  );
}

function showCitySearch(message) {
  $("#locate").hidden = false;
  $("#locate-status").textContent = message;
  $("#city-form").hidden = false;
  $("#city").focus();
}

$("#city-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = $("#city").value.trim();
  const list = $("#city-results");
  list.replaceChildren();
  try {
    const res = await fetch(`/api/geocode?q=${encodeURIComponent(q)}`);
    if (!res.ok) throw new Error(res.status);
    const places = await res.json();
    if (!places.length) {
      list.append(li(text("No matches. Try a bigger nearby city.")));
      return;
    }
    for (const p of places) {
      const label = [p.name, p.country].filter(Boolean).join(", ");
      const btn = button(label, () => setLocation({ lat: p.lat, lon: p.lon, name: label }));
      list.append(li(btn));
    }
  } catch {
    list.append(li(text("City search is unavailable right now. Please try again.")));
  }
});

function setLocation(loc) {
  state.loc = loc;
  $("#locate").hidden = true;
  $("#place-label").textContent = loc.name ?? "Your current location";
  $("#when").hidden = false;
}

$("#change-place").addEventListener("click", () => {
  $("#when").hidden = true;
  showCitySearch("Search for a city.");
});

// ---------- free time (R2) ----------

function addRange(start = "", end = "") {
  const row = $("#range-row").content.firstElementChild.cloneNode(true);
  row.querySelector(".start").value = start;
  row.querySelector(".end").value = end;
  row.querySelector(".remove").addEventListener("click", () => row.remove());
  $("#ranges").append(row);
  row.querySelector(".start").focus();
}

$("#add-range").addEventListener("click", () => {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  const h = (now.getHours() + 1) % 24;
  addRange(`${pad(h)}:00`, `${pad(Math.min(h + 1, 23))}:${h + 1 > 23 ? "59" : "00"}`);
});

function readRanges() {
  return [...document.querySelectorAll("#ranges .range")]
    .map((row) => ({ start: row.querySelector(".start").value, end: row.querySelector(".end").value }))
    .filter((r) => r.start && r.end);
}

// ---------- plan (R3) ----------

$("#plan-btn").addEventListener("click", async () => {
  const btn = $("#plan-btn");
  const err = $("#plan-error");
  err.hidden = true;
  const ranges = readRanges();
  if (ranges.some((r) => r.end <= r.start)) return showError("Each free time needs to end after it starts.");

  btn.disabled = true;
  btn.textContent = "Checking the sky…";
  try {
    const res = await fetch("/api/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lat: state.loc.lat, lon: state.loc.lon, free_ranges: ranges }),
    });
    if (res.status === 502) throw new Error("The weather service is unavailable. Try again in a minute.");
    if (!res.ok) throw new Error("Something went wrong. Check your times and try again.");
    state.plan = await res.json();
    renderPlan();
  } catch (e) {
    showError(e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Find my golden hour";
  }

  function showError(msg) {
    err.textContent = msg;
    err.hidden = false;
  }
});

function renderPlan() {
  const { plan } = state;
  $("#plan").hidden = false;
  const note = $("#plan-note");
  note.hidden = !plan.note;
  note.textContent = plan.note ?? "";
  $("#best").hidden = !plan.best;
  if (plan.best) choose(plan.best);
  else {
    $("#suggestion").hidden = true;
    state.stopCountdown?.();
  }
  renderAlternates();
  $("#plan").scrollIntoView({ behavior: "smooth", block: "start" });
}

const hhmm = (iso) => iso.slice(11, 16);

function renderWindow(w) {
  $("#best-day").textContent = w.day === "today" ? "Today" : "Tomorrow";
  $("#best-duration").textContent = `${w.duration_min} min`;
  $("#best-time").textContent = `${hhmm(w.start)}–${hhmm(w.end)}`;
  $("#best-score").textContent = w.score;
  $("#best-reasons").replaceChildren(...w.reasons.map((r) => li(text(convertText(r)))));
  const x = w.weather;
  $("#best-weather").textContent =
    `${fmtTemp(x.temp_c)} · ${x.precip_prob}% rain · wind ${Math.round(x.wind_kmh)} km/h · UV ${Math.round(x.uv)}`;
}

function renderAlternates() {
  const { plan } = state;
  const options = [plan.best, ...plan.alternates].filter((w) => w && w !== state.chosen);
  $("#alts-wrap").hidden = !options.length;
  $("#alts").replaceChildren(
    ...options.map((w) =>
      li(button(`${hhmm(w.start)}–${hhmm(w.end)} · ${w.score}/100 · ${convertText(w.reasons[0] ?? "")}`, () => choose(w))),
    ),
  );
}

function choose(w) {
  state.chosen = w;
  renderWindow(w);
  renderAlternates();
  state.stopCountdown?.();
  state.stopCountdown = startCountdown($("#countdown"), w.start, w.end, state.plan.timezone);
  requestActivity(w);
}

// ---------- calendar (R5.1) ----------

$("#ics-btn").addEventListener("click", () => {
  const w = state.chosen;
  const s = state.suggestion;
  const p = state.places;
  let description = "Go outside for a bit.";
  if (p) {
    description = [
      "Top places near you:",
      ...p.places.map((x, i) => `${i + 1}. ${x.name} (${x.walk_min} min walk): ${p.lines[x.id] ?? ""}`),
      "Places © OpenStreetMap contributors",
    ].join("\n");
  } else if (s) {
    description = [s.title, ...s.steps.map((step, i) => `${i + 1}. ${step}`), `Notice: ${s.what_to_notice}`].join("\n");
  }
  const ics = buildIcs({
    title: p ? `Golden Hour: ${p.places[0].name}` : s ? `Golden Hour: ${s.title}` : "Golden Hour: go outside",
    description,
    startIso: w.start,
    endIso: w.end,
    timezone: state.plan.timezone,
  });
  downloadIcs(ics, `golden-hour-${w.start.slice(0, 10)}.ics`);
});

// ---------- places (spec 002: R8–R10) ----------

function elapsedTimer(el) {
  const started = Date.now();
  el.textContent = "0s";
  return setInterval(() => (el.textContent = `${Math.round((Date.now() - started) / 1000)}s`), 1000);
}

async function postJson(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(res.status);
  return res.json();
}

// Real places first; the single activity is the fallback (R10.1). One model call either way.
async function requestActivity(w) {
  const token = ++state.suggestToken;
  state.places = null;
  state.suggestion = null;
  $("#suggestion").hidden = true;
  $("#suggest-note").hidden = true;
  $("#places").hidden = false;
  $("#places-loading").hidden = false;
  $("#places-list").replaceChildren();
  $("#places-attribution").hidden = true;

  const timer = elapsedTimer($("#places-elapsed"));
  let found = [];
  try {
    const data = await postJson("/api/places", {
      lat: state.loc.lat,
      lon: state.loc.lon,
      window: w,
      hobbies: state.hobbies,
    });
    found = data.places;
  } catch {
    found = [];
  } finally {
    clearInterval(timer);
  }
  if (token !== state.suggestToken) return; // user picked another window meanwhile

  if (found.length < 3) {
    $("#places").hidden = true;
    $("#suggest-note").hidden = false;
    requestSuggestion(w, token);
    return;
  }

  state.places = { places: found, lines: {} };
  renderPlaces(found);
  try {
    const lines = await postJson("/api/places/describe", { window: w, places: found, hobbies: state.hobbies });
    if (token !== state.suggestToken) return;
    state.places.lines = lines.lines;
    renderPlaceLines(lines.lines);
  } catch {
    if (token !== state.suggestToken) return;
    renderPlaceLines({});
  }
}

function renderPlaces(places) {
  $("#places-loading").hidden = true;
  $("#places-attribution").hidden = false;
  $("#places-list").replaceChildren(
    ...places.map((p) => {
      const row = $("#place-row").content.firstElementChild.cloneNode(true);
      row.dataset.id = p.id;
      row.querySelector(".place-name").textContent = p.name;
      row.querySelector(".place-meta").textContent = `${p.kind.replace(/_/g, " ")} · ${p.walk_min} min walk`;
      row.querySelector(".place-map").href = p.osm_url;
      return row;
    }),
  );
}

function renderPlaceLines(lines) {
  for (const row of document.querySelectorAll("#places-list .place")) {
    const line = row.querySelector(".place-line");
    line.textContent = lines[row.dataset.id] ?? "Worth a look while you're out.";
    line.classList.remove("loading");
  }
}

// ---------- suggestion (R4) ----------

async function requestSuggestion(w, token = ++state.suggestToken) {
  state.suggestion = null;
  $("#suggestion").hidden = false;
  $("#suggest-loading").hidden = false;
  $("#suggest-body").hidden = true;

  const started = Date.now();
  const elapsed = $("#suggest-elapsed");
  elapsed.textContent = "0s";
  const timer = setInterval(() => (elapsed.textContent = `${Math.round((Date.now() - started) / 1000)}s`), 1000);

  try {
    const res = await fetch("/api/suggest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ window: w, place_name: state.loc.name }),
    });
    if (!res.ok) throw new Error(res.status);
    const s = await res.json();
    if (token !== state.suggestToken) return; // user picked another window meanwhile
    state.suggestion = s;
    renderSuggestion(s);
  } catch {
    if (token !== state.suggestToken) return;
    $("#suggest-loading").hidden = true;
    $("#suggest-body").hidden = false;
    $("#suggest-title").textContent = "Couldn't get a suggestion. Just go for a walk!";
    $("#suggest-steps").replaceChildren();
    $("#suggest-notice").textContent = "Whatever catches your eye.";
    $("#suggest-bring-wrap").hidden = true;
  } finally {
    clearInterval(timer);
  }
}

function renderSuggestion(s) {
  $("#suggest-loading").hidden = true;
  $("#suggest-body").hidden = false;
  $("#suggest-source").hidden = s.source !== "fallback";
  $("#suggest-title").textContent = s.title;
  $("#suggest-steps").replaceChildren(...s.steps.map((step) => li(text(step))));
  $("#suggest-notice").textContent = s.what_to_notice;
  $("#suggest-bring-wrap").hidden = !s.bring.length;
  $("#suggest-bring").textContent = s.bring.join(", ");
}

// ---------- tiny DOM helpers ----------

function li(child) {
  const el = document.createElement("li");
  el.append(child);
  return el;
}

function text(s) {
  return document.createTextNode(s);
}

function button(label, onClick) {
  const el = document.createElement("button");
  el.type = "button";
  el.textContent = label;
  el.addEventListener("click", onClick);
  return el;
}

renderUnitButton();
renderHobbies();
locate();
