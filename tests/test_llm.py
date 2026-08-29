import pytest

import engine.llm as llm


@pytest.fixture(autouse=True)
def isolate_cache(tmp_path, monkeypatch):
    # Each test gets its own empty cache dir so tests can't leak into each other
    # or into the real .llm_cache/ on disk.
    monkeypatch.setattr(llm, "LLM_CACHE_DIR", tmp_path / "llm_cache")


def _ollama_response(text="ollama answer", pt=8, ct=4):
    return {"text": text, "prompt_tokens": pt, "completion_tokens": ct}


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
