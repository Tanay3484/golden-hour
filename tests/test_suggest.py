import logging

import pytest
from fastapi.testclient import TestClient

from golden_hour.llm import LLMError
from golden_hour.main import app, get_llm
from golden_hour.suggest import SUGGESTION_SCHEMA, suggest

GOOD = {
    "title": "Chase the sunset to the canal",
    "steps": ["Walk to the canal.", "Sit on the steps.", "Walk back along the water."],
    "what_to_notice": "The light on the water.",
    "bring": ["jacket"],
}


class FakeLLM:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, []

    def chat_json(self, messages, schema):
        self.calls.append((messages, schema))
        if self.error:
            raise self.error
        return self.reply


def test_schema_excludes_source():
    assert "source" not in SUGGESTION_SCHEMA["properties"]
    assert set(SUGGESTION_SCHEMA["required"]) == {"title", "steps", "what_to_notice", "bring"}


def test_valid_model_output(ctx):
    llm = FakeLLM(GOOD)
    s = suggest(ctx, llm)
    assert s.source == "model"
    assert s.title == GOOD["title"]
    assert llm.calls[0][1] is SUGGESTION_SCHEMA


def test_none_placeholders_removed_from_bring(ctx):
    s = suggest(ctx, FakeLLM(GOOD | {"bring": ["None", "nothing.", "jacket"]}))
    assert s.bring == ["jacket"]


def test_overlong_output_is_trimmed_not_rejected(ctx):
    reply = GOOD | {"title": "x" * 80, "steps": ["a", "b", "c", "d", " "], "bring": list("abcde")}
    s = suggest(ctx, FakeLLM(reply))
    assert s.source == "model"
    assert len(s.title) <= 60
    assert s.steps == ["a", "b", "c"]
    assert len(s.bring) == 3


@pytest.mark.parametrize(
    "llm",
    [
        FakeLLM(error=LLMError("timeout")),
        FakeLLM({"title": "No steps", "steps": [], "what_to_notice": "x", "bring": []}),
        FakeLLM({"steps": "not a list"}),
    ],
)
def test_failures_fall_back(ctx, llm, caplog):
    with caplog.at_level(logging.WARNING):
        s = suggest(ctx, llm)
    assert s.source == "fallback"
    assert "Berlin" not in caplog.text  # never log the context


def test_api_suggest(ctx):
    app.dependency_overrides[get_llm] = lambda: FakeLLM(GOOD)
    try:
        resp = TestClient(app).post("/api/suggest", json=ctx.model_dump(mode="json"))
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["source"] == "model"
