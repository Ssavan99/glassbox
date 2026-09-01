import json
import unittest.mock as mock

import pytest

import engine.architectures.naive as naive_mod
import scripts.record_traces as record_traces_mod
from engine.trace import Trace


@pytest.fixture(autouse=True)
def _no_real_calls_allowed():
    def _boom(*args, **kwargs):
        raise AssertionError("a real (unmocked) complete() call was attempted")

    with mock.patch("engine.llm._call_groq", _boom), mock.patch("engine.llm._call_ollama", _boom):
        yield


def _fake_complete(prompt, json_schema=None, **params):
    return {
        "text": "a fake answer",
        "prompt_tokens": 5,
        "completion_tokens": 3,
        "backend": "ollama",
    }


def test_main_writes_one_trace_file_per_architecture_per_question(tmp_path, monkeypatch):
    two_questions = record_traces_mod.load_questions()[:2]

    monkeypatch.setattr(record_traces_mod, "TRACES_DIR", tmp_path)
    monkeypatch.setattr(
        record_traces_mod,
        "ARCHITECTURES",
        {"naive": record_traces_mod.ARCHITECTURES["naive"]},
    )
    monkeypatch.setattr(record_traces_mod, "load_questions", lambda: two_questions)

    with mock.patch.object(naive_mod, "complete", _fake_complete):
        record_traces_mod.main()

    written = sorted(p.name for p in tmp_path.glob("*.json"))
    assert len(written) == 2
    assert all(name.startswith("naive__q") for name in written)

    first = json.loads((tmp_path / written[0]).read_text())
    assert first["trace_id"].startswith("naive::")
    # round-trips through Trace.from_dict cleanly
    trace = Trace.from_dict(first)
    trace.validate()
