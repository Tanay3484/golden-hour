import json

import httpx
import pytest

from golden_hour.config import Settings
from golden_hour.llm import LLMError, OllamaClient


def client(handler) -> OllamaClient:
    return OllamaClient(
        "http://ollama:11434/",
        "gemma3:1b",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def chat_reply(content: str) -> httpx.Response:
    return httpx.Response(
        200, json={"model": "gemma3:1b", "message": {"role": "assistant", "content": content}}
    )


def test_chat_json_sends_schema_and_parses_content():
    seen = []

    def handler(request):
        seen.append(request)
        return chat_reply('{"title": "Walk"}')

    out = client(handler).chat_json([{"role": "user", "content": "hi"}], {"type": "object"})
    assert out == {"title": "Walk"}
    req = seen[0]
    assert str(req.url) == "http://ollama:11434/api/chat"
    body = json.loads(req.content)
    assert body["model"] == "gemma3:1b"
    assert body["format"] == {"type": "object"}
    assert body["stream"] is False


@pytest.mark.parametrize(
    "handler",
    [
        lambda r: httpx.Response(500, json={"error": "boom"}),
        lambda r: chat_reply("not json"),
        lambda r: chat_reply("[1, 2]"),
        lambda r: httpx.Response(200, json={"unexpected": True}),
    ],
)
def test_chat_json_errors_become_llm_error(handler):
    with pytest.raises(LLMError):
        client(handler).chat_json([], {})


def test_chat_json_timeout_becomes_llm_error():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(LLMError):
        client(handler).chat_json([], {})


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("golden-hour-ollama:11434", "http://golden-hour-ollama:11434"),
        ("http://localhost:11434/", "http://localhost:11434"),
        ("https://example.com", "https://example.com"),
    ],
)
def test_ollama_url_normalized(raw, expected):
    assert Settings(ollama_url=raw).ollama_url == expected
