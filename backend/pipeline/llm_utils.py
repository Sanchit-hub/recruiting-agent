"""Shared helpers for LLM calls: retry/backoff, JSON extraction, token logging.

Used by jd_parser.py, filter_tier.py, and deep_research.py (all three call
the LLM) to avoid duplicating client setup and the retry-once-with-backoff
behavior required by the PRD's error handling section.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Callable, TypeVar

from groq import Groq

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Switched from Gemini to Groq (2026-07-13): the Gemini free-tier quota was
# exhausted mid-project. llama-3.3-70b-versatile is Groq's current
# general-purpose model, confirmed working for the JSON-extraction/scoring
# prompts this pipeline uses.
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


class _Usage:
    def __init__(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.prompt_token_count = prompt_tokens
        self.candidates_token_count = completion_tokens


class _GroqResponse:
    def __init__(self, text: str, prompt_tokens: int, completion_tokens: int) -> None:
        self.text = text
        self.usage_metadata = _Usage(prompt_tokens, completion_tokens)


class GroqModel:
    """Thin wrapper matching the subset of the Gemini SDK's interface this
    codebase relies on (`.generate_content(...)` -> object with `.text` and
    `.usage_metadata`), so callers didn't need to change beyond the import.
    """

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._client = Groq(api_key=os.environ["GROQ_API_KEY"])

    def generate_content(self, prompt: str, generation_config: dict | None = None) -> _GroqResponse:
        wants_json = bool(generation_config and generation_config.get("response_mime_type") == "application/json")
        response = self._client.chat.completions.create(
            model=self._model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"} if wants_json else None,
        )
        text = response.choices[0].message.content or ""
        usage = response.usage
        return _GroqResponse(text, usage.prompt_tokens, usage.completion_tokens)


def get_llm_model(model_name: str = DEFAULT_GROQ_MODEL) -> GroqModel:
    return GroqModel(model_name)

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def strip_code_fences(text: str) -> str:
    """Remove markdown code fences an LLM may wrap JSON output in, despite instructions not to."""
    return _CODE_FENCE_RE.sub("", text.strip()).strip()


def parse_json_response(text: str) -> Any:
    return json.loads(strip_code_fences(text))


def call_with_retry(fn: Callable[[], T], *, retries: int = 1, base_delay: float = 1.0) -> T:
    """Call fn(), retrying on exception with exponential backoff.

    retries=1 means: one initial attempt + one retry, matching the PRD's
    "retry once with exponential backoff" requirement.
    """
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - deliberately broad, re-raised after retries
            last_exc = exc
            if attempt < retries:
                delay = base_delay * (2**attempt)
                logger.warning(
                    "LLM call failed (attempt %d/%d): %s. Retrying in %.1fs.",
                    attempt + 1,
                    retries + 1,
                    exc,
                    delay,
                )
                time.sleep(delay)
            else:
                logger.error("LLM call failed after %d attempts: %s", retries + 1, exc)
    assert last_exc is not None
    raise last_exc


def log_token_usage(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> None:
    total = prompt_tokens + completion_tokens
    logger.info(
        "[token_usage] provider=%s model=%s prompt=%d completion=%d total=%d",
        provider,
        model,
        prompt_tokens,
        completion_tokens,
        total,
    )
