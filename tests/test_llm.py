import pytest

import engine.llm as llm


@pytest.fixture(autouse=True)
def isolate_cache(tmp_path, monkeypatch):
    # Each test gets its own empty cache dir so tests can't leak into each other
    # or into the real .llm_cache/ on disk.
    monkeypatch.setattr(llm, "LLM_CACHE_DIR", tmp_path / "llm_cache")


def _ollama_response(text="ollama answer", pt=8, ct=4):
    return {"text": text, "prompt_tokens": pt, "completion_tokens": ct}


class TestSafeJsonDict:
    """complete(json_schema=...) only guarantees the response parses as
    *some* JSON on success, never that it matches the schema's shape --
    safe_json_dict() is the single shared guard every architecture that
    passes json_schema= relies on before calling .get() on the result."""

    def test_returns_the_dict_when_json_is_a_dict(self):
        assert llm.safe_json_dict({"json": {"a": 1}}) == {"a": 1}

    def test_returns_empty_dict_when_json_is_a_list(self):
        assert llm.safe_json_dict({"json": ["not", "a", "dict"]}) == {}

    def test_returns_empty_dict_when_json_is_a_string(self):
        assert llm.safe_json_dict({"json": "not a dict"}) == {}

    def test_returns_empty_dict_when_json_key_is_missing(self):
        assert llm.safe_json_dict({"text": "no json key at all"}) == {}

    def test_returns_empty_dict_when_json_is_none(self):
        assert llm.safe_json_dict({"json": None}) == {}


def test_fallback_engages_when_groq_unreachable(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-present")

    def _fail_groq(prompt, params):
        raise RuntimeError("groq unreachable")

    ollama_calls = []

    def _ok_ollama(prompt, params):
        ollama_calls.append((prompt, params))
        return _ollama_response()

    monkeypatch.setattr(llm, "_call_groq", _fail_groq)
    monkeypatch.setattr(llm, "_call_ollama", _ok_ollama)

    result = llm.complete("hello world")

    assert len(ollama_calls) == 1
    assert result["text"] == "ollama answer"


def test_missing_api_key_falls_back(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    groq_calls = []

    def _groq_should_not_run(prompt, params):
        groq_calls.append((prompt, params))
        raise AssertionError("groq should not be called without an api key")

    ollama_calls = []

    def _ok_ollama(prompt, params):
        ollama_calls.append((prompt, params))
        return _ollama_response()

    monkeypatch.setattr(llm, "_call_groq", _groq_should_not_run)
    monkeypatch.setattr(llm, "_call_ollama", _ok_ollama)

    result = llm.complete("no key here")

    assert groq_calls == []
    assert len(ollama_calls) == 1
    assert result["text"] == "ollama answer"


def test_cache_hit_skips_both_backends(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    groq_calls = []
    ollama_calls = []

    def _fail_groq(prompt, params):
        groq_calls.append(1)
        raise RuntimeError("no key")

    def _ok_ollama(prompt, params):
        ollama_calls.append(1)
        return _ollama_response()

    monkeypatch.setattr(llm, "_call_groq", _fail_groq)
    monkeypatch.setattr(llm, "_call_ollama", _ok_ollama)

    first = llm.complete("cache me", temperature=0.0)
    second = llm.complete("cache me", temperature=0.0)

    assert second == first
    assert len(ollama_calls) == 1
    assert len(groq_calls) == 0  # never reached: no GROQ_API_KEY set


def test_backend_field_reflects_actual_serving_backend_live_call(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-present")

    def _fail_groq(prompt, params):
        raise RuntimeError("groq unreachable")

    def _ok_ollama(prompt, params):
        return _ollama_response()

    monkeypatch.setattr(llm, "_call_groq", _fail_groq)
    monkeypatch.setattr(llm, "_call_ollama", _ok_ollama)

    result = llm.complete("which backend")
    assert result["backend"] == llm.OLLAMA_BACKEND


def test_backend_field_present_on_cache_hit_even_for_pre_existing_cache_files(monkeypatch):
    # Simulates a cache file written before the "backend" field existed
    # (~600 real entries from Phases 3-5 are in exactly this shape) --
    # complete() must still report the correct backend on a hit by using
    # which (backend, model) cache slot matched, not by trusting the
    # stored response to carry its own "backend" key.
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    prompt = "old-format cache entry"
    params: dict = {}

    old_style_response = _ollama_response()  # no "backend" key inside
    llm._write_cache(llm.OLLAMA_BACKEND, llm.OLLAMA_MODEL, prompt, params, old_style_response)

    def _groq_should_not_run(prompt, params):
        raise AssertionError("should be a cache hit, never reach a live backend")

    monkeypatch.setattr(llm, "_call_groq", _groq_should_not_run)
    monkeypatch.setattr(llm, "_call_ollama", _groq_should_not_run)

    result = llm.complete(prompt, **params)
    assert result["backend"] == llm.OLLAMA_BACKEND


def test_malformed_json_triggers_one_repair_attempt(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    responses = iter(
        [
            {"text": "not json at all", "prompt_tokens": 5, "completion_tokens": 5},
            {"text": '{"answer": "ok"}', "prompt_tokens": 6, "completion_tokens": 3},
        ]
    )
    calls = []

    def _ollama_side_effect(prompt, params):
        calls.append(prompt)
        return next(responses)

    def _fail_groq(prompt, params):
        raise RuntimeError("no key")

    monkeypatch.setattr(llm, "_call_groq", _fail_groq)
    monkeypatch.setattr(llm, "_call_ollama", _ollama_side_effect)

    result = llm.complete("give me json", json_schema={"answer": "string"})

    assert len(calls) == 2
    assert result["json"] == {"answer": "ok"}
    assert result["prompt_tokens"] == 11
    assert result["completion_tokens"] == 8


def test_json_repair_falls_back_to_ollama_when_groq_repair_fails(monkeypatch):
    # Groq serves the initial call but returns malformed JSON; the repair
    # attempt against Groq then fails too (rate limit, etc) — the repair
    # itself must fall back to Ollama rather than propagating the exception,
    # since Ollama fallback is meant to be core correctness, not just for
    # the first call.
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-present")

    groq_calls = []
    ollama_calls = []

    def _groq_side_effect(prompt, params):
        groq_calls.append(prompt)
        if len(groq_calls) == 1:
            return {"text": "not json at all", "prompt_tokens": 5, "completion_tokens": 5}
        raise RuntimeError("groq rate limited on repair")

    def _ollama_side_effect(prompt, params):
        ollama_calls.append(prompt)
        return {"text": '{"answer": "ok"}', "prompt_tokens": 6, "completion_tokens": 3}

    monkeypatch.setattr(llm, "_call_groq", _groq_side_effect)
    monkeypatch.setattr(llm, "_call_ollama", _ollama_side_effect)

    result = llm.complete("give me json", json_schema={"answer": "string"})

    assert len(groq_calls) == 2  # initial + failed repair attempt
    assert len(ollama_calls) == 1  # repair fell back here instead of raising
    assert result["json"] == {"answer": "ok"}
