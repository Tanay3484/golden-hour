from datetime import datetime, timedelta

import pytest

from golden_hour.describe import MAX_LINE_CHARS, describe, lines_schema
from golden_hour.hobbies import CATEGORIES
from golden_hour.llm import LLMError
from golden_hour.models import Spot, Window, WindowWeather
from golden_hour.prompts import build_place_messages

START = datetime(2026, 10, 9, 17, 30)
WINDOW = Window(
    start=START,
    end=START + timedelta(minutes=40),
    duration_min=40,
    day="today",
    score=90,
    reasons=["golden hour", "dry (0% rain)"],
    weather=WindowWeather(temp_c=24, precip_prob=0, wind_kmh=5, uv=2, cloud_cover=10),
)


def spot(i, name, category, facts=()):
    return Spot(
        id=f"node/{i}",
        name=name,
        category=category,
        kind=category,
        lat=18.52 + i / 1000,
        lon=73.85,
        walk_min=i + 1,
        covered=CATEGORIES[category].covered,
        facts=list(facts),
        osm_url=f"https://www.openstreetmap.org/node/{i}",
    )


SPOTS = [
    spot(1, "Jijamata Udyan", "park"),
    spot(2, "Bajirao I statue", "art", ["artwork type: sculpture"]),
    spot(3, "Shaniwarwada", "history"),
]


class FakeLLM:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, []

    def chat_json(self, messages, schema, temperature=0.7):
        self.calls.append((messages, schema))
        if self.error:
            raise self.error
        return self.reply


def test_prompt_lists_places_and_facts_but_no_coordinates():
    system, user = build_place_messages(WINDOW, SPOTS, ["photography"])
    assert "Only use the facts given" in system["content"]
    text = user["content"]
    assert "1. Jijamata Udyan (park, 2 min walk). Facts: none." in text
    assert "2. Bajirao I statue (art, 3 min walk). Facts: artwork type: sculpture." in text
    assert "Hobbies: photography." in text
    assert "golden hour" in text
    assert "18.5" not in text and "73.85" not in text  # model never sees coordinates


def test_schema_demands_one_line_per_place():
    s = lines_schema(3)["properties"]["lines"]
    assert s["minItems"] == s["maxItems"] == 3


def test_model_lines_mapped_back_to_place_ids():
    llm = FakeLLM(
        {"lines": [{"id": i, "name": SPOTS[i - 1].name, "line": f"Line {i}."} for i in (1, 2, 3)]}
    )
    out = describe(WINDOW, SPOTS, ["photography"], llm)
    assert out.lines == {"node/1": "Line 1.", "node/2": "Line 2.", "node/3": "Line 3."}
    assert set(out.source.values()) == {"model"}


def test_missing_unknown_and_empty_lines_get_templates():
    reply = {
        "lines": [
            {"id": 1, "name": "Jijamata Udyan", "line": "Good."},
            {"id": 9, "name": "Ghost", "line": "Ghost."},
            {"id": 3, "name": "Shaniwarwada", "line": "  "},
        ]
    }
    out = describe(WINDOW, SPOTS, [], FakeLLM(reply))
    assert out.lines["node/1"] == "Good."
    assert out.lines["node/2"] == CATEGORIES["art"].template
    assert out.lines["node/3"] == CATEGORIES["history"].template
    assert out.source == {"node/1": "model", "node/2": "template", "node/3": "template"}


def test_long_lines_trimmed_on_a_word():
    out = describe(
        WINDOW,
        SPOTS[:1],
        [],
        FakeLLM({"lines": [{"id": 1, "name": "Jijamata Udyan", "line": "word " * 60}]}),
    )
    line = out.lines["node/1"]
    assert len(line) <= MAX_LINE_CHARS and line.endswith("…") and "  " not in line


@pytest.mark.parametrize(
    "llm",
    [
        FakeLLM(error=LLMError("timeout")),
        FakeLLM({"lines": "nope"}),
        FakeLLM({"lines": [1, 2]}),
        FakeLLM([]),
    ],
)
def test_model_failures_mean_all_templates(llm):
    out = describe(WINDOW, SPOTS, [], llm)
    assert set(out.source.values()) == {"template"}
    assert len(out.lines) == 3


def test_lines_attached_to_the_wrong_place_are_rejected():
    reply = {
        "lines": [
            # name echo doesn't match id 1
            {"id": 1, "name": "Shaniwarwada", "line": "See the fort walls."},
            # right name, but describes another listed place
            {"id": 2, "name": "Bajirao I statue", "line": "Relax on the lawns of Jijamata Udyan."},
            # loose name echo is fine
            {"id": 3, "name": "Shaniwar Wada", "line": "Walk the length of the outer wall."},
        ]
    }
    out = describe(WINDOW, SPOTS, [], FakeLLM(reply))
    assert out.source == {"node/1": "template", "node/2": "template", "node/3": "model"}


def test_schema_requires_name_echo():
    assert lines_schema(2)["properties"]["lines"]["items"]["required"] == ["id", "name", "line"]


def test_facts_borrowed_from_another_place_are_rejected():
    plaque = spot(4, "Krushnarao Gangurde", "history", ["memorial: blue_plaque", "inscription: x"])
    spots = [SPOTS[1], plaque]  # the statue has only "artwork type: sculpture"
    reply = {
        "lines": [
            {"id": 1, "name": "Bajirao I statue", "line": "Note the blue plaque by the statue."},
            {
                "id": 2,
                "name": "Krushnarao Gangurde",
                "line": "Read the inscription on the blue plaque.",
            },
        ]
    }
    out = describe(WINDOW, spots, [], FakeLLM(reply))
    assert out.source == {"node/2": "template", "node/4": "model"}
