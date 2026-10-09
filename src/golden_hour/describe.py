"""One line per place from Gemma, with a template for anything it misses (spec 002, R9)."""

import logging

from golden_hour.hobbies import CATEGORIES
from golden_hour.llm import LLMError, OllamaClient
from golden_hour.models import Hobby, PlaceLines, Spot, Window
from golden_hour.prompts import build_place_messages

log = logging.getLogger(__name__)

MAX_LINE_CHARS = 140


def lines_schema(n: int) -> dict:
    return {
        "type": "object",
        "properties": {
            "lines": {
                "type": "array",
                "minItems": n,
                "maxItems": n,
                "items": {
                    "type": "object",
                    # Echoing the name anchors each line to its place (see _belongs).
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                        "line": {"type": "string"},
                    },
                    "required": ["id", "name", "line"],
                },
            }
        },
        "required": ["lines"],
    }


def _trim(line: str) -> str:
    line = " ".join(line.split())
    if len(line) <= MAX_LINE_CHARS:
        return line
    cut = line[: MAX_LINE_CHARS - 1].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


def _key(text: str) -> str:
    return "".join(ch for ch in text.casefold() if ch.isalnum())


def _belongs(echoed: object, line: str, spot: Spot, others: list[Spot]) -> bool:
    """Reject lines the model attached to the wrong place (seen with gemma3:1b, design §4.4)."""
    want, got = _key(spot.name), _key(echoed) if isinstance(echoed, str) else ""
    if not got or not (got in want or want in got):
        return False
    text = _key(line)
    if any(len(k := _key(o.name)) >= 5 and k != want and k in text for o in others):
        return False
    # Facts borrowed from another place ("the blue plaque" on a statue that has none).
    own = {k for f in spot.facts for k in _fact_keys(f)}
    borrowed = {k for o in others if o is not spot for f in o.facts for k in _fact_keys(f)} - own
    return not any(k in text for k in borrowed)


def _fact_keys(fact: str) -> list[str]:
    """Distinctive pieces of a fact: its label ("inscription") and a short value ("blue_plaque")."""
    label, _, value = fact.partition(": ")
    keys = [_key(label)]
    if len(value) <= 30:
        keys.append(_key(value))
    return [k for k in keys if len(k) >= 6]


def describe(
    window: Window, spots: list[Spot], hobbies: list[Hobby], client: OllamaClient
) -> PlaceLines:
    # The prompt numbers places 1..n (the spike showed small models handle short ids reliably),
    # and only carries names, kinds, walking times and OSM facts: never coordinates.
    model_lines: dict[int, str] = {}
    try:
        data = client.chat_json(
            build_place_messages(window, spots, hobbies), lines_schema(len(spots)), temperature=0.3
        )
        for item in data.get("lines") or []:
            if not isinstance(item, dict):
                continue
            idx, line = item.get("id"), item.get("line")
            if not (isinstance(idx, int) and 1 <= idx <= len(spots) and isinstance(line, str)):
                continue
            if line.strip() and _belongs(item.get("name"), line, spots[idx - 1], spots):
                model_lines.setdefault(idx, _trim(line))
    except (LLMError, AttributeError, TypeError) as e:
        log.warning("place lines fell back to templates: %s: %.200s", type(e).__name__, e)

    lines, source = {}, {}
    for i, s in enumerate(spots, start=1):
        if i in model_lines:
            lines[s.id], source[s.id] = model_lines[i], "model"
        else:
            lines[s.id], source[s.id] = CATEGORIES[s.category].template, "template"
    return PlaceLines(lines=lines, source=source)
