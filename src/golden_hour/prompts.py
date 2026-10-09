"""Prompt for the activity suggestion (R4.1–R4.3).

Kept short and literal: it has to work on gemma3:1b.
"""

from golden_hour.models import Hobby, Spot, SuggestionContext, Window

SYSTEM = """You are Golden Hour, a friendly coach who gets people away from screens and outside.
You suggest ONE small, specific outdoor activity for a time window the user already has free.

Rules:
- It must fit inside the window, including walking there and back.
- Walking distance only. No car, no transit, no tickets, no bookings, nothing to buy.
- You do NOT know the person's street. Never name a real street, park, landmark or business.
  Describe the kind of place instead: "the nearest patch of green", "a tree-lined street".
- Match the weather. If rain is 50% or more, the activity must work in rain or under cover,
  and the steps must say so.
- Be specific about what to DO, not generic. "Walk to the nearest tree-lined street and find
  leaves in three colours" is good. "Go for a walk" is bad.
- title: at most 8 words.
- steps: 1 to 3 short imperative sentences.
- what_to_notice: one sentence about something to look, listen or smell for.
- bring: 0 to 3 everyday items the person already owns. Use an empty list if nothing is needed.
Reply with JSON only."""


def time_of_day(hour: int) -> str:
    if hour < 11:
        return "morning"
    if hour < 14:
        return "midday"
    if hour < 17:
        return "afternoon"
    return "evening"


def window_facts(w: Window) -> list[str]:
    """When and what the weather is like; shared by both prompts."""
    weather = w.weather
    facts = [
        f"Window: {w.start:%A %d %B}, {w.start:%H:%M}–{w.end:%H:%M} "
        f"({w.duration_min} minutes, {w.day}, {time_of_day(w.start.hour)}).",
        f"Weather: {round(weather.temp_c)}°C, {weather.precip_prob}% chance of rain, "
        f"wind {round(weather.wind_kmh)} km/h, cloud cover {weather.cloud_cover}%, "
        f"UV {round(weather.uv)}.",
    ]
    if "golden hour" in w.reasons:
        facts.append("This is golden hour: the sun is low and the light is warm before sunset.")
    return facts


def build_messages(ctx: SuggestionContext) -> list[dict]:
    w = ctx.window
    weather = w.weather
    facts = window_facts(w)
    if weather.precip_prob >= 50:
        facts.append(
            "Rain is likely. The first step must say how to stay dry (umbrella, covered spot)."
        )
    if ctx.place_name:
        facts.append(f"Region (for climate only): {ctx.place_name}.")
    facts.append("Suggest one activity.")
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "\n".join(facts)},
    ]


PLACES_SYSTEM = """You help someone pick where to spend a short window outside.
For EACH numbered place, write one sentence (at most 20 words) on what to do or notice there,
right now, given the time and weather.

Rules:
- Only use the facts given for a place. Never state its history, what it looks like, or what is
  inside it unless that is in its facts. You may suggest an action anyone could do there.
- Match the weather. If rain is likely, say how to stay dry or keep it short.
- If it is golden hour, use the light where it fits.
- Connect to the person's hobbies when you can.
- Write a line for every id, using the ids exactly as given.
Reply with JSON only."""


def build_place_messages(window: Window, spots: list[Spot], hobbies: list[Hobby]) -> list[dict]:
    facts = window_facts(window)
    if window.weather.precip_prob >= 50:
        facts.append("Rain is likely.")
    facts.append(f"Hobbies: {', '.join(hobbies) if hobbies else 'not given'}.")
    facts.append("Places:")
    for i, s in enumerate(spots, start=1):
        known = "; ".join(s.facts) if s.facts else "none"
        facts.append(f"{i}. {s.name} ({s.kind}, {s.walk_min} min walk). Facts: {known}.")
    return [
        {"role": "system", "content": PLACES_SYSTEM},
        {"role": "user", "content": "\n".join(facts)},
    ]
