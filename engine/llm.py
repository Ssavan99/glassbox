"""Dual-backend LLM client: Groq (primary, free tier) with local Ollama fallback.

Per plan decision D6, the whole point of glassbox is that it stays free forever,
even if Groq's free tier changes or the user hasn't configured a key yet. So the
Ollama fallback is not an edge case — it is core correctness, and every caller in
later phases goes through the single `complete()` entry point defined here.

Responses are cached to disk (keyed by backend + model + prompt + params) so that
re-running an architecture is near-free and reproducible regardless of which
backend originally served a given call.

Every dict `complete()` returns carries a `"backend"` field (`"groq"` or
`"ollama"`) naming whichever backend actually served that call, live or
cached -- callers (notably `evaluation/run_eval.py`, which reports this per
question in `artifacts/eval.json`) can rely on this without scraping logs.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any

import groq
import ollama
from dotenv import load_dotenv

from engine.config import GROQ_MODEL, LLM_CACHE_DIR, OLLAMA_MODEL

logger = logging.getLogger(__name__)

load_dotenv()

GROQ_BACKEND = "groq"
OLLAMA_BACKEND = "ollama"


class LLMError(Exception):
    """Base class for errors raised by the LLM client."""


class LLMBackendError(LLMError):
    """Raised internally when a backend cannot serve a request (triggers fallback)."""


class LLMJSONError(LLMError):
    """Raised when a backend fails to produce valid JSON even after one repair attempt."""


# --- disk cache -------------------------------------------------------------


def _cache_key(backend: str, model: str, prompt: str, params: dict[str, Any]) -> str:
    payload = "\x1f".join([backend, model, prompt, json.dumps(params, sort_keys=True)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_path(backend: str, model: str, prompt: str, params: dict[str, Any]):
    key = _cache_key(backend, model, prompt, params)
    return LLM_CACHE_DIR / f"{key}.json"


def _read_cache(backend: str, model: str, prompt: str, params: dict[str, Any]) -> dict | None:
    path = _cache_path(backend, model, prompt, params)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    return data.get("response")


def _write_cache(
    backend: str,
    model: str,
    prompt: str,
    params: dict[str, Any],
    response: dict,
) -> None:
    LLM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(backend, model, prompt, params)
    payload = {
        "request": {"backend": backend, "model": model, "prompt": prompt, "params": params},
        "response": response,
    }
    path.write_text(json.dumps(payload, indent=2))


# --- backend calls (SDK boundary) --------------------------------------------


def _call_groq(prompt: str, params: dict[str, Any]) -> dict:
    """Call Groq's chat completions API. Raises on any failure (missing/empty key,
    auth error, rate limit, network error, ...) so callers can fall back to Ollama."""
    client = groq.Groq()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        **params,
    )
    choice = response.choices[0]
    text = choice.message.content or ""
    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
    return {"text": text, "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}


def _call_ollama(prompt: str, params: dict[str, Any]) -> dict:
    """Call local Ollama's chat API."""
    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
        **params,
    )
    if isinstance(response, dict):
        text = response.get("message", {}).get("content", "") or ""
        prompt_tokens = response.get("prompt_eval_count")
        completion_tokens = response.get("eval_count")
    else:
        text = getattr(response.message, "content", "") or ""
        prompt_tokens = getattr(response, "prompt_eval_count", None)
        completion_tokens = getattr(response, "eval_count", None)

    # Ollama doesn't always report usage; fall back to a rough word-count proxy.
    if not prompt_tokens:
        prompt_tokens = len(prompt.split())
    if not completion_tokens:
        completion_tokens = len(text.split())

    return {"text": text, "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}


# --- JSON handling ------------------------------------------------------------


def _augment_prompt_for_json(prompt: str, json_schema: dict) -> str:
    return (
        f"{prompt}\n\n"
        "Respond with ONLY valid JSON matching this shape, no prose and no markdown "
        f"fences:\n{json.dumps(json_schema)}"
    )


def _try_parse_json(text: str) -> Any | None:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def safe_json_dict(result: dict) -> dict:
    """Returns `result["json"]` if it's a dict, else `{}`.

    `complete(prompt, json_schema=...)` only guarantees the response parses
    as *some* JSON value on success -- never that it matches the requested
    schema's shape. A model can return a bare list, string, or number
    instead of the expected object. Every caller that passes `json_schema=`
    needs this exact guard before it can safely call `.get(...)` on the
    parsed value; centralizing it here means it only has to be gotten right
    once instead of independently re-derived at each call site."""
    parsed = result.get("json")
    return parsed if isinstance(parsed, dict) else {}


def _ensure_json(
    result: dict,
    json_schema: dict,
    backend_used: str,
    prompt: str,
    params: dict[str, Any],
) -> tuple[dict, str]:
    """Returns (result, backend_that_served_it) — the repair attempt follows the
    same Groq-then-Ollama fallback as the initial call, so a transient Groq
    failure during repair doesn't defeat the "stays free forever" guarantee."""
    parsed = _try_parse_json(result["text"])
    if parsed is not None:
        return {**result, "json": parsed}, backend_used

    logger.warning("backend=%s returned invalid JSON, attempting one repair", backend_used)
    repair_prompt = (
        f"{prompt}\n\nThe previous response was not valid JSON:\n{result['text']}\n\n"
        "Fix it. Respond with ONLY valid JSON, no prose and no markdown fences."
    )
    try:
        if backend_used != GROQ_BACKEND:
            raise LLMBackendError("original call did not use groq")
        repaired = _call_groq(repair_prompt, params)
        repair_backend = GROQ_BACKEND
    except Exception as exc:  # noqa: BLE001 - any Groq failure falls back to ollama
        logger.warning("groq repair unavailable (%s), falling back to ollama", exc)
        repaired = _call_ollama(repair_prompt, params)
        repair_backend = OLLAMA_BACKEND

    parsed = _try_parse_json(repaired["text"])
    if parsed is None:
        raise LLMJSONError(
            f"backend={repair_backend} failed to produce valid JSON after one repair attempt"
        )
    return (
        {
            "text": repaired["text"],
            "json": parsed,
            "prompt_tokens": result["prompt_tokens"] + repaired["prompt_tokens"],
            "completion_tokens": result["completion_tokens"] + repaired["completion_tokens"],
        },
        repair_backend,
    )


# --- public entry point -------------------------------------------------------


def complete(prompt: str, json_schema: dict | None = None, **params: Any) -> dict:
    """Get a completion, trying Groq first and falling back to local Ollama.

    Returns a dict with at least `text`, `prompt_tokens`, `completion_tokens`, and
    (when `json_schema` is passed and parsing succeeds) `json`.
    """
    effective_prompt = prompt
    if json_schema is not None:
        effective_prompt = _augment_prompt_for_json(prompt, json_schema)

    # Cache lookup happens before any live call, in the same priority order
    # backends are tried in, so a cache hit never touches either backend.
    for backend, model in ((GROQ_BACKEND, GROQ_MODEL), (OLLAMA_BACKEND, OLLAMA_MODEL)):
        cached = _read_cache(backend, model, effective_prompt, params)
        if cached is not None:
            logger.info("llm cache hit: backend=%s", backend)
            # `backend` here is which (backend, model) pair's cache file
            # matched -- patched into the returned dict regardless of
            # whether the cached response itself already carries it, so
            # callers (e.g. the eval harness) can always tell which
            # backend actually served a call, cache hit or not.
            return {**cached, "backend": backend}

    backend_used: str
    try:
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            raise LLMBackendError("GROQ_API_KEY not set")
        result = _call_groq(effective_prompt, params)
        backend_used = GROQ_BACKEND
    except Exception as exc:  # noqa: BLE001 - any Groq failure triggers fallback
        logger.warning("groq backend unavailable (%s), falling back to ollama", exc)
        result = _call_ollama(effective_prompt, params)
        backend_used = OLLAMA_BACKEND

    logger.info("llm request served by backend=%s", backend_used)

    if json_schema is not None:
        result, backend_used = _ensure_json(
            result, json_schema, backend_used, effective_prompt, params
        )

    model = GROQ_MODEL if backend_used == GROQ_BACKEND else OLLAMA_MODEL
    result = {**result, "backend": backend_used}
    _write_cache(backend_used, model, effective_prompt, params, result)
    return result
