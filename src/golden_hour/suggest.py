"""Turns a chosen window into one activity: model first, curated fallback on any failure (R4)."""

import logging

from golden_hour.fallbacks import pick_fallback
from golden_hour.llm import LLMError, OllamaClient
from golden_hour.models import Suggestion, SuggestionContext
from golden_hour.prompts import build_messages

log = logging.getLogger(__name__)

# Small models sometimes write "None" instead of an empty list.
NOTHING = {"none", "nothing", "n/a", "na", "-"}


def suggestion_schema() -> dict:
    """JSON schema for the model: Suggestion without the server-set `source` field."""
    schema = Suggestion.model_json_schema()
    schema["properties"].pop("source", None)
    schema["required"] = ["title", "steps", "what_to_notice", "bring"]
    return schema


SUGGESTION_SCHEMA = suggestion_schema()


def suggest(ctx: SuggestionContext, client: OllamaClient) -> Suggestion:
    try:
        data = client.chat_json(build_messages(ctx), SUGGESTION_SCHEMA)
        return coerce(data)
    except (LLMError, ValueError, TypeError) as e:  # ValidationError is a ValueError
        # Log the error only, never the context (N2).
        log.warning("suggestion fell back to curated list: %s: %.200s", type(e).__name__, e)
        return pick_fallback(ctx)


def coerce(data: dict) -> Suggestion:
    """Validate model output, trimming over-long fields instead of failing (design §4.3)."""

    def clean(items) -> list[str]:
        if not isinstance(items, list):
            return []
        out = [s.strip() for s in items if isinstance(s, str)]
        return [s for s in out if s and s.lower().rstrip(".") not in NOTHING]

    title = str(data.get("title", "")).strip()
    notice = str(data.get("what_to_notice", "")).strip()
    if not title or not notice:
        raise ValueError("model output missing title or what_to_notice")
    if len(title) > 60:
        title = title[:59].rstrip() + "…"
    return Suggestion(
        title=title,
        steps=clean(data.get("steps"))[:3],
        what_to_notice=notice,
        bring=clean(data.get("bring"))[:3],
        source="model",
    )
