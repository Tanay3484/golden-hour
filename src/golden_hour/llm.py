"""Minimal Ollama chat client with JSON-schema constrained output. https://docs.ollama.com/api"""

import json

import httpx


class LLMError(Exception):
    """Model unreachable, timed out, or returned something that isn't JSON."""


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_s: float = 60,
        http: httpx.Client | None = None,
        num_thread: int | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.num_thread = num_thread
        self._http = http or httpx.Client(timeout=timeout_s)

    def chat_json(self, messages: list[dict], schema: dict, temperature: float = 0.7) -> dict:
        options: dict = {"temperature": temperature}
        if self.num_thread:
            options["num_thread"] = self.num_thread
        try:
            resp = self._http.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "format": schema,
                    "stream": False,
                    "options": options,
                },
            )
            resp.raise_for_status()
            content = resp.json()["message"]["content"]
            data = json.loads(content)
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as e:
            raise LLMError(f"{type(e).__name__}: {e}") from e
        if not isinstance(data, dict):
            raise LLMError("model returned JSON that is not an object")
        return data
