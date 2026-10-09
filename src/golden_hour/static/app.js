import { buildIcs, downloadIcs, startCountdown, zonedToEpoch } from "./time.js";

const $ = (sel) => document.querySelector(sel);

// Must be defined before `state`, which reads saved hobbies on load.
const HOBBIES = [
  ["photography", "Photography", "i-camera"],
  ["nature", "Nature & birds", "i-leaf"],
  ["history", "History", "i-history"],
  ["art", "Art", "i-art"],
  ["running", "Running & walking", "i-walk"],
  ["reading", "Reading & sketching", "i-book"],
  ["coffee", "Coffee outside", "i-cafe"],
  ["sports", "Sports", "i-sport"],
];
const MAX_HOBBIES = 3;

const CATEGORY_ICON = {
  park: "i-park",
  water: "i-water",
  view: "i-view",
  art: "i-art",
  history: "i-history",
  museum: "i-history",
  library: "i-book",
  cafe: "i-cafe",
  sport: "i-sport",
};

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

// ---------- tiny DOM helpers ----------

function el(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.append(content);
  return node;
}

function icon(id) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "icon");
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `#${id}`);
  svg.append(use);
  return svg;
}

function button(label, onClick, className) {
  const b = el("button", className);
  b.type = "button";
  b.append(label);
  b.addEventListener("click", onClick);
  return b;
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

function elapsedTimer(node) {
  const started = Date.now();
  node.textContent = "0s";
  return setInterval(() => (node.textContent = `${Math.round((Date.now() - started) / 1000)}s`), 1000);
}

function store(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* storage unavailable: keep in memory only */
  }
}

// ---------- units (R3.4) ----------

function loadUnit() {
  try {
    return localStorage.getItem("gh-unit") === "F" ? "F" : "C";
  } catch {
    return "C";
  }
}

const toUnit = (c) => (state.unit === "F" ? Math.round((c * 9) / 5 + 32) : Math.round(c));
const fmtTemp = (c) => `${toUnit(c)}°${state.unit}`;
const convertText = (s) => s.replace(/(-?\d+(?:\.\d+)?)°C/g, (_, c) => fmtTemp(Number(c)));

$("#unit-toggle").addEventListener("click", () => {
  state.unit = state.unit === "C" ? "F" : "C";
  store("gh-unit", state.unit);
  renderUnitButton();
  if (state.chosen) renderWindow(state.chosen);
  if (state.plan) renderAlternates();
});

function renderUnitButton() {
  for (const s of document.querySelectorAll("#unit-toggle span")) {
    s.classList.toggle("on", s.dataset.unit === state.unit);
  }
  $("#unit-toggle").setAttribute("aria-label", `Temperature unit: °${state.unit}. Switch unit`);
}

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

function renderHobbies() {
  const full = state.hobbies.length >= MAX_HOBBIES;
  $("#hobbies").replaceChildren(
    ...HOBBIES.map(([id, label, iconId]) => {
      const on = state.hobbies.includes(id);
      const chip = button(label, () => {
        state.hobbies = on ? state.hobbies.filter((h) => h !== id) : [...state.hobbies, id];
        store("gh-hobbies", JSON.stringify(state.hobbies));
        renderHobbies();
      }, "chip");
      chip.prepend(icon(iconId));
      chip.setAttribute("aria-pressed", String(on));
      chip.disabled = full && !on;
      return chip;
    }),
  );
}

// ---------- location (R1) ----------

function locate() {
  if (!("geolocation" in navigator)) return showCitySearch("Location isn't available in this browser.");
  navigator.geolocation.getCurrentPosition(
    (pos) => setLocation({ lat: pos.coords.latitude, lon: pos.coords.longitude, name: null }),
    () => showCitySearch("No problem: search for your city instead."),
    { timeout: 10000, maximumAge: 10 * 60 * 1000 },
  );
}

function showCitySearch(message) {
  $("#locate").hidden = false;
  $("#place-row").hidden = true;
  $("#locate-status").textContent = message;
  $("#city-form").hidden = false;
  $("#city").focus();
}

$("#city-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = $("#city").value.trim();
  const list = $("#city-results");
  list.replaceChildren();
  const note = (msg) => list.append(el("li", "option-note", msg));
  try {
    const res = await fetch(`/api/geocode?q=${encodeURIComponent(q)}`);
    if (!res.ok) throw new Error(res.status);
    const places = await res.json();
    if (!places.length) return note("No matches. Try a bigger nearby city.");
    for (const p of places) {
      const label = [p.name, p.country].filter(Boolean).join(", ");
      const b = button(label, () => setLocation({ lat: p.lat, lon: p.lon, name: label }));
      b.prepend(icon("i-pin"), " ");
      list.append(el("li", null, b));
    }
  } catch {
    note("City search is unavailable right now. Please try again.");
  }
});

function setLocation(loc) {
  state.loc = loc;
  $("#locate").hidden = true;
  $("#place-row").hidden = false;
  $("#place-label").textContent = loc.name ?? "Your current location";
  $("#when").hidden = false;
}

$("#change-place").addEventListener("click", () => {
  $("#when").hidden = true;
  $("#city-results").replaceChildren();
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
  const label = btn.querySelector(".btn-label");
  const err = $("#plan-error");
  const showError = (msg) => {
    err.textContent = msg;
    err.hidden = false;
  };
  err.hidden = true;
  const ranges = readRanges();
  if (ranges.some((r) => r.end <= r.start)) return showError("Each free time needs to end after it starts.");

  btn.disabled = true;
  label.textContent = "Checking the sky…";
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
    label.textContent = "Find my golden hour";
  }
});

function renderPlan() {
  const { plan } = state;
  $("#empty").hidden = true;
  $("#plan").hidden = false;
  const note = $("#plan-note");
  note.hidden = !plan.note;
  note.textContent = plan.note ?? "";
  $("#best").hidden = !plan.best;
  if (plan.best) choose(plan.best);
  else {
    $("#places").hidden = true;
    $("#suggestion").hidden = true;
    state.stopCountdown?.();
  }
  renderAlternates();
  if (window.matchMedia("(max-width: 959px)").matches) {
    $("#plan").scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

const hhmm = (iso) => iso.slice(11, 16);

function stat(iconId, value, label) {
  const tile = el("div", "stat");
  tile.append(icon(iconId), el("span", "stat-value", value), el("span", "stat-label", label));
  return tile;
}

function renderWindow(w) {
  $("#best-day").textContent = w.day === "today" ? "Today" : "Tomorrow";
  $("#best-duration").textContent = `${w.duration_min} min`;
  $("#best-time").textContent = `${hhmm(w.start)}–${hhmm(w.end)}`;
  $("#best-score").textContent = w.score;
  $("#score-arc").style.strokeDashoffset = String(169.6 * (1 - w.score / 100));
  $("#best-reasons").replaceChildren(...w.reasons.map((r) => el("li", null, convertText(r))));
  const x = w.weather;
  $("#best-weather").replaceChildren(
    stat("i-temp", fmtTemp(x.temp_c), "Temperature"),
    stat("i-drop", `${x.precip_prob}%`, "Chance of rain"),
    stat("i-wind", `${Math.round(x.wind_kmh)} km/h`, "Wind"),
    stat("i-sun", String(Math.round(x.uv)), "UV index"),
  );
  renderTimeline();
}

// Daylight bar: sunrise → sunset + 15 min, golden hour shaded, windows marked (R3.3).
function renderTimeline() {
  const { plan, chosen } = state;
  const tz = plan.timezone;
  const t = (iso) => zonedToEpoch(iso, tz);
  const start = t(plan.sunrise);
  const end = t(plan.sunset) + 15 * 60_000;
  const pct = (ms) => `${Math.min(100, Math.max(0, ((ms - start) / (end - start)) * 100))}%`;
  const span = (cls, from, to) => {
    const node = el("div", cls);
    node.style.left = pct(from);
    node.style.width = `calc(${pct(to)} - ${pct(from)})`;
    return node;
  };

  const track = el("div", "tl-track");
  track.append(span("tl-golden", t(plan.sunset) - 60 * 60_000, t(plan.sunset)));
  for (const w of [plan.best, ...plan.alternates].filter(Boolean)) {
    track.append(span(w === chosen ? "tl-win best" : "tl-win", t(w.start), t(w.end)));
  }
  const now = Date.now();
  if (now > start && now < end) {
    const marker = el("div", "tl-now");
    marker.style.left = pct(now);
    track.append(marker);
  }
  const labels = el("div", "tl-labels");
  const sunrise = el("span");
  sunrise.append(icon("i-sunrise"), hhmm(plan.sunrise));
  const sunset = el("span");
  sunset.append(hhmm(plan.sunset), icon("i-sunset"));
  labels.append(sunrise, sunset);
  $("#timeline").replaceChildren(track, labels);
}

function renderAlternates() {
  const { plan } = state;
  const options = [plan.best, ...plan.alternates].filter(Boolean);
  $("#alts-wrap").hidden = options.length < 2;
  $("#alts").replaceChildren(
    ...options.map((w) => {
      const b = button("", () => choose(w));
      b.setAttribute("aria-pressed", String(w === state.chosen));
      b.append(
        el("span", "alt-time", `${hhmm(w.start)}–${hhmm(w.end)}`),
        el("span", "alt-reason", convertText(w.reasons[0] ?? "")),
        el("span", "alt-score", String(w.score)),
      );
      return el("li", null, b);
    }),
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

// Real places first; the single activity is the fallback (R10.1). One model call either way.
async function requestActivity(w) {
  const token = ++state.suggestToken;
  state.places = null;
  state.suggestion = null;
  $("#suggestion").hidden = true;
  $("#suggest-note").hidden = true;
  $("#places").hidden = false;
  $("#places-loading").hidden = false;
  $("#places-status").textContent = "Looking for places near you…";
  $("#places-list").replaceChildren();
  $("#places-attribution").hidden = true;

  const timer = elapsedTimer($("#places-elapsed"));
  const request = { lat: state.loc.lat, lon: state.loc.lon, window: w, hobbies: state.hobbies };
  let found = [];
  try {
    const data = await postJson("/api/places", request);
    found = data.places;
    if (!found.length && data.fallback && token === state.suggestToken) {
      // The server couldn't reach OpenStreetMap: ask it from this browser instead (R10.5).
      $("#places-status").textContent = "Asking OpenStreetMap directly…";
      const elements = await overpassFromBrowser(data.fallback);
      if (elements) found = (await postJson("/api/places/from-osm", { ...request, elements })).places;
    }
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

// Same cell-centre query the server would have sent (R10.2), tried against each instance
// within 25 s. Returns the raw elements, or null if none answered.
async function overpassFromBrowser({ query, urls }) {
  const deadline = Date.now() + 25_000;
  for (const url of urls) {
    const remaining = deadline - Date.now();
    if (remaining < 2000) break;
    const abort = new AbortController();
    const timeout = setTimeout(() => abort.abort(), remaining);
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: `data=${encodeURIComponent(query)}`,
        signal: abort.signal,
      });
      if (!res.ok) continue;
      const data = await res.json();
      if (Array.isArray(data.elements)) return data.elements.slice(0, 2000);
    } catch {
      /* try the next instance */
    } finally {
      clearTimeout(timeout);
    }
  }
  return null;
}

function renderPlaces(places) {
  $("#places-loading").hidden = true;
  $("#places-attribution").hidden = false;
  $("#places-list").replaceChildren(
    ...places.map((p) => {
      const row = $("#place-row-tpl").content.firstElementChild.cloneNode(true);
      row.dataset.id = p.id;
      row.dataset.cat = p.category;
      row.querySelector(".place-icon").replaceChildren(icon(CATEGORY_ICON[p.category] ?? "i-pin"));
      row.querySelector(".place-name").textContent = p.name;
      row.querySelector(".place-kind").textContent = p.kind.replace(/_/g, " ");
      row.querySelector(".place-walk").textContent = `${p.walk_min} min walk`;
      const map = row.querySelector(".place-map");
      map.href = p.osm_url;
      map.setAttribute("aria-label", `${p.name} on OpenStreetMap`);
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
  const timer = elapsedTimer($("#suggest-elapsed"));

  try {
    const s = await postJson("/api/suggest", { window: w, place_name: state.loc.name });
    if (token !== state.suggestToken) return;
    state.suggestion = s;
    renderSuggestion(s);
  } catch {
    if (token !== state.suggestToken) return;
    renderSuggestion({
      title: "Couldn't get a suggestion. Just go for a walk!",
      steps: [],
      what_to_notice: "Whatever catches your eye.",
      bring: [],
      source: "fallback",
    });
  } finally {
    clearInterval(timer);
  }
}

function renderSuggestion(s) {
  $("#suggest-loading").hidden = true;
  $("#suggest-body").hidden = false;
  $("#suggest-source").hidden = s.source !== "fallback";
  $("#suggest-title").textContent = s.title;
  $("#suggest-steps").replaceChildren(...s.steps.map((step) => el("li", null, step)));
  $("#suggest-notice").textContent = s.what_to_notice;
  $("#suggest-bring-wrap").hidden = !s.bring.length;
  $("#suggest-bring").textContent = s.bring.join(", ");
}

renderUnitButton();
renderHobbies();
locate();
