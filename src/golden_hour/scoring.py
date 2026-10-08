"""Picks the best outdoor windows from a forecast.

Pipeline: plan_day -> candidate_windows -> (weather_for, score_window) -> pick_windows.
Rules and numbers: specs/001-golden-hour-mvp/design.md §4.2.
"""

from datetime import date, datetime, timedelta

from golden_hour.models import DayLight, Forecast, Plan, TimeRange, Window, WindowWeather

HOUR = timedelta(hours=1)
QUARTER = timedelta(minutes=15)
MIN_WINDOW = timedelta(minutes=20)
MAX_WINDOW = timedelta(minutes=40)
AFTER_SUNSET = timedelta(minutes=15)
IDEAL_TEMP_C = 19.5


def weather_for(forecast: Forecast, start: datetime, end: datetime) -> WindowWeather:
    """Worst-case weather across the forecast hours that [start, end) overlaps."""
    hours = [h for h in forecast.hours if h.time < end and h.time + HOUR > start]
    if not hours:
        raise ValueError(f"no forecast hours for {start}–{end}")
    return WindowWeather(
        temp_c=max((h.temp_c for h in hours), key=lambda t: abs(t - IDEAL_TEMP_C)),
        precip_prob=max(h.precip_prob for h in hours),
        wind_kmh=max(h.wind_kmh for h in hours),
        uv=max(h.uv for h in hours),
        cloud_cover=max(h.cloud_cover for h in hours),
    )


def score_window(
    w: WindowWeather, start: datetime, end: datetime, sunset: datetime
) -> tuple[int, list[str]]:
    """Score 0-100 and up to 3 short reasons, most important first."""
    initial_score = 100
    # Each rule adds (effect on score, short reason). Score and reasons both come from this list.
    factors: list[tuple[float, str]] = []

    rain = w.precip_prob
    if rain < 20:
        factors.append((-0.8 * rain, f"dry ({rain}% rain)"))
    elif rain < 50:
        factors.append((-0.8 * rain, f"{rain}% chance of rain"))
    else:
        factors.append((-0.8 * rain, f"rain likely ({rain}%)"))

    temp = round(w.temp_c)
    if w.temp_c < 15:
        factors.append((-3 * (15 - w.temp_c), f"chilly ({temp}°C)"))
    elif w.temp_c > 24:
        factors.append((-3 * (w.temp_c - 24), f"hot ({temp}°C)"))
    else:
        factors.append((0, f"comfortable {temp}°C"))

    if w.wind_kmh > 20:
        factors.append((-2 * (w.wind_kmh - 20), f"windy ({round(w.wind_kmh)} km/h)"))

    if w.uv > 6:
        factors.append((-5 * (w.uv - 6), f"strong sun (UV {round(w.uv)})"))

    # Bonus if the window overlaps the last hour before sunset.
    golden_start = sunset - timedelta(minutes=60)
    if start < sunset and end > golden_start:
        factors.append((15, "golden hour"))

    raw_score = initial_score + sum(effect for effect, _ in factors)
    final_score = max(0, min(100, round(raw_score)))
    # Biggest effect first (good or bad); ties keep rule order. Max 3 reasons.
    ranked = sorted(factors, key=lambda f: abs(f[0]), reverse=True)
    reasons = [reason for _, reason in ranked[:3]]

    return final_score, reasons


def candidate_windows(
    free: list[TimeRange], forecast: Forecast, day: date, now: datetime
) -> list[Window]:
    """All quarter-hour-aligned 20-40 min windows inside the free ranges and daylight on `day`."""
    light = _daylight(forecast, day)
    if light is None:
        return []
    earliest = max(_ceil_quarter(now), _ceil_quarter(light.sunrise))
    latest_end = light.sunset + AFTER_SUNSET
    label = "today" if day == now.date() else "tomorrow"

    windows = []
    for r in free:
        start = max(_ceil_quarter(datetime.combine(day, r.start)), earliest)
        limit = min(datetime.combine(day, r.end), latest_end)
        while limit - start >= MIN_WINDOW:
            end = start + min(MAX_WINDOW, limit - start)
            try:
                weather = weather_for(forecast, start, end)
            except ValueError:
                break  # past the end of the forecast
            score, reasons = score_window(weather, start, end, light.sunset)
            windows.append(
                Window(
                    start=start,
                    end=end,
                    duration_min=int((end - start).total_seconds() // 60),
                    day=label,
                    score=score,
                    reasons=reasons,
                    weather=weather,
                )
            )
            start += QUARTER
    return windows


def pick_windows(candidates: list[Window], k: int = 3) -> list[Window]:
    """Up to k non-overlapping windows, best score first.

    Ties prefer golden hour (its +15 bonus can be lost to the 100 cap), then the earlier start.
    """
    picked: list[Window] = []
    for c in sorted(candidates, key=lambda w: (-w.score, "golden hour" not in w.reasons, w.start)):
        if all(not _overlaps(c, p) for p in picked):
            picked.append(c)
            if len(picked) == k:
                break
    return picked


def plan_day(free: list[TimeRange], forecast: Forecast, now: datetime) -> Plan:
    """Best window + alternates for today, falling back to tomorrow (R2.2, R2.3)."""
    today = now.date()
    today_light = _daylight(forecast, today)
    if today_light is None:
        raise ValueError(f"forecast has no daylight data for {today}")

    if not free:  # R2.2: free from now until sunset
        free = _range_or_empty(now, today_light.sunset)
    picks = pick_windows(candidate_windows(free, forecast, today, now))
    if picks:
        return _plan(forecast, today_light, picks, note=None)

    # R2.3: nothing left today, so offer tomorrow's whole daylight.
    tomorrow_light = _daylight(forecast, today + timedelta(days=1))
    if tomorrow_light is not None:
        whole_day = _range_or_empty(tomorrow_light.sunrise, tomorrow_light.sunset)
        picks = pick_windows(candidate_windows(whole_day, forecast, tomorrow_light.date, now))
        if picks:
            note = "No 20-minute gap left today, so here's tomorrow's best window."
            return _plan(forecast, tomorrow_light, picks, note)
    return _plan(forecast, today_light, [], note="No good window found today or tomorrow.")


def _plan(forecast: Forecast, light: DayLight, picks: list[Window], note: str | None) -> Plan:
    return Plan(
        timezone=forecast.timezone,
        sunrise=light.sunrise,
        sunset=light.sunset,
        best=picks[0] if picks else None,
        alternates=picks[1:],
        note=note,
    )


def _daylight(forecast: Forecast, day: date) -> DayLight | None:
    return next((d for d in forecast.days if d.date == day), None)


def _range_or_empty(start: datetime, end: datetime) -> list[TimeRange]:
    if end.time() <= start.time() or end.date() != start.date():
        return []
    return [TimeRange(start=start.time(), end=end.time())]


def _ceil_quarter(dt: datetime) -> datetime:
    floored = dt.replace(minute=dt.minute - dt.minute % 15, second=0, microsecond=0)
    return floored if floored == dt else floored + QUARTER


def _overlaps(a: Window, b: Window) -> bool:
    return a.start < b.end and b.start < a.end
