"""LLM client. Works with any OpenAI-compatible endpoint, so switching Azure -> Vultr is a .env change."""
from __future__ import annotations

import json
import logging
import re

from openai import BadRequestError, OpenAI

from .config import Settings

log = logging.getLogger(__name__)

_CODE_RE = re.compile(r"```(?:python|py)?[ \t]*\n(.*?)```", re.DOTALL)


def extract_code(text: str) -> str:
    """Return the first fenced code block of a model reply ('' if there is none)."""
    m = _CODE_RE.search(text or "")
    if m:
        return m.group(1).strip()
    # Fallback if code block was not closed due to output length
    m_open = re.search(r"```(?:python|py)?[ \t]*\n(.*)", text or "", re.DOTALL)
    if m_open:
        return m_open.group(1).strip()
    return ""


def extract_json(text: str):
    """Parse JSON from a model reply, tolerating prose, fences, or truncated outputs."""
    text = (text or "").strip()
    if not text:
        return None

    # Strip markdown code blocks if wrapped
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    # Attempt recovery if JSON was cut off/truncated before final closing brace
    start_idx = text.find("{")
    if start_idx != -1:
        snippet = text[start_idx:]
        # Try progressively trimming back to the last complete key-value pair and closing braces
        for cut in range(len(snippet), max(0, len(snippet) - 500), -5):
            candidate = snippet[:cut].rstrip()
            if candidate.endswith(","):
                candidate = candidate[:-1]
            # Balance open braces/brackets
            open_cur = candidate.count("{") - candidate.count("}")
            open_sq = candidate.count("[") - candidate.count("]")
            # If quotes are unbalanced, close the open quote
            if candidate.count('"') % 2 != 0:
                candidate += '"'
            candidate += ("]" * max(0, open_sq)) + ("}" * max(0, open_cur))
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict) and len(parsed) > 0:
                    return parsed
            except json.JSONDecodeError:
                continue

    return None


class LLM:
    def __init__(self, settings: Settings):
        self.model = settings.llm_model
        self.configured = bool(settings.llm_base_url and settings.llm_api_key and settings.llm_model)
        self.client = OpenAI(
            base_url=settings.llm_base_url or None,
            api_key=settings.llm_api_key or "not-configured",
            timeout=90,
            max_retries=2,
        )

    def _complete(self, **kwargs) -> str:
        resp = self.client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    def chat(
        self,
        messages: list[dict],
        json_mode: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = 8192,
    ) -> str:
        kwargs = {"model": self.model, "messages": messages}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            # Newer OpenAI models require max_completion_tokens instead of max_tokens
            if any(p in self.model.lower() for p in ("gpt-5", "o1", "o3", "o4", "gpt-4.1")):
                kwargs["max_completion_tokens"] = max_tokens
            else:
                kwargs["max_tokens"] = max_tokens

        import time
        from openai import APIConnectionError

        for attempt in range(2):
            try:
                if json_mode:
                    try:
                        return self._complete(**kwargs, response_format={"type": "json_object"})
                    except BadRequestError:
                        log.warning("json_object response_format rejected; retrying without it")
                return self._complete(**kwargs)
            except BadRequestError as e:
                log.warning("chat completion failed (%s); retrying with fallback parameters", e)
                kwargs.pop("temperature", None)
                kwargs.pop("max_tokens", None)
                kwargs.pop("max_completion_tokens", None)
                return self._complete(**kwargs)
            except APIConnectionError as e:
                if attempt == 0:
                    log.warning("Connection error to LLM, retrying in 2s... (%s)", e)
                    time.sleep(2)
                    continue
                raise

