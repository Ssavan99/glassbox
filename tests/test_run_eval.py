import unittest.mock as mock

import pytest

import engine.architectures.naive as naive_mod
import evaluation.run_eval as run_eval_mod


def _fake_generate(text="a fake answer", backend="ollama"):
    def _complete(prompt, json_schema=None, **params):
        if json_schema is not None:
            return {
                "text": "",
                "json": {
                    "point_support": [True],
                    "reads_as_appropriate_refusal": False,
                    "reasoning": "r",
                },
                "prompt_tokens": 2,
                "completion_tokens": 1,
                "backend": backend,
            }
        return {"text": text, "prompt_tokens": 5, "completion_tokens": 3, "backend": backend}

    return _complete


@pytest.fixture(autouse=True)
def _no_real_calls_allowed():
    """Every test in this file must mock complete() explicitly -- fail loudly
    (not silently make a real network call) if one doesn't."""

    def _boom(*args, **kwargs):
        raise AssertionError("a real (unmocked) complete() call was attempted")

    with mock.patch("engine.llm._call_groq", _boom), mock.patch("engine.llm._call_ollama", _boom):
        yield


def test_run_one_uses_explicit_trace_id():
    question = run_eval_mod.load_questions()[0]
    with mock.patch.object(naive_mod, "complete", _fake_generate()):
        trace, backend_calls = run_eval_mod.run_one("naive", question)

    assert trace.trace_id == f"naive::{question['id']}"
    assert backend_calls == ["ollama"]


def test_track_backends_wraps_an_already_mocked_complete_not_the_real_one():
    # Regression test: _track_backends() must wrap whatever `complete` is
    # currently bound on each architecture module (a test's own mock,
    # here), not reach back to import the real engine.llm.complete fresh --
    # doing the latter would silently bypass the mock and make a real call.
    question = run_eval_mod.load_questions()[0]
    with mock.patch.object(naive_mod, "complete", _fake_generate(backend="groq")):
        trace, backend_calls = run_eval_mod.run_one("naive", question)

    assert backend_calls == ["groq"]
    assert trace.answer == "a fake answer"


def test_eval_one_computes_metrics_and_judge_fields():
    question = run_eval_mod.load_questions()[0]
    with (
        mock.patch.object(naive_mod, "complete", _fake_generate()),
        mock.patch("evaluation.metrics.complete", _fake_generate()),
    ):
        trace, backend_calls = run_eval_mod.run_one("naive", question)
        row = run_eval_mod.eval_one("naive", question, trace, backend_calls)

    assert row["architecture"] == "naive"
    assert row["question_id"] == question["id"]
    assert row["trace_id"] == f"naive::{question['id']}"
    assert row["faithfulness"] is not None
    assert row["backend_calls"] == ["ollama"]
    assert row["judge_backend"] == "ollama"
    assert "adaptive_routed_to" not in row


def test_eval_one_persists_adaptive_routing_decision():
    import engine.architectures.adaptive as adaptive_mod

    question = run_eval_mod.load_questions()[0]

    def _fake_route(prompt, json_schema=None, **params):
        return {
            "text": "",
            "json": {"chosen": "naive", "scores": {}, "reason": "simple question"},
            "prompt_tokens": 3,
            "completion_tokens": 2,
            "backend": "groq",
        }

    with (
        mock.patch.object(adaptive_mod, "complete", _fake_route),
        mock.patch.object(naive_mod, "complete", _fake_generate()),
        mock.patch("evaluation.metrics.complete", _fake_generate()),
    ):
        trace, backend_calls = run_eval_mod.run_one("adaptive", question)
        row = run_eval_mod.eval_one("adaptive", question, trace, backend_calls)

    assert row["adaptive_routed_to"] == "naive"


def test_build_report_computes_adaptive_routing_accuracy_against_the_rubric():
    rows = [
        {
            "architecture": "adaptive",
            "question_id": "q01",
            "question_type": "keyword",
            "trace_id": "adaptive::q01",
            "answer": "a",
            "retrieved_chunk_ids": [],
            "gold_chunk_ids": [],
            "recall_at_5": None,
            "mrr_at_10": None,
            "ndcg_at_10": None,
            "faithfulness": None,
            "reads_as_refusal": False,
            "refusal_correctness": None,
            "judge_reasoning": "",
            "latency_ms": 1.0,
            "llm_calls": 1,
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "backend_calls": ["ollama"],
            "judge_backend": "ollama",
            "adaptive_routed_to": "hybrid",  # correct for keyword per the rubric
        },
        {
            "architecture": "adaptive",
            "question_id": "q02",
            "question_type": "keyword",
            "trace_id": "adaptive::q02",
            "answer": "a",
            "retrieved_chunk_ids": [],
            "gold_chunk_ids": [],
            "recall_at_5": None,
            "mrr_at_10": None,
            "ndcg_at_10": None,
            "faithfulness": None,
            "reads_as_refusal": False,
            "refusal_correctness": None,
            "judge_reasoning": "",
            "latency_ms": 1.0,
            "llm_calls": 1,
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "backend_calls": ["ollama"],
            "judge_backend": "ollama",
            "adaptive_routed_to": "naive",  # incorrect for keyword per the rubric
        },
    ]

    report = run_eval_mod.build_report(rows)
    acc = report["adaptive_routing_accuracy"]
    assert acc["correct"] == 1
    assert acc["total"] == 2
    assert acc["accuracy"] == pytest.approx(0.5)
    assert report["adaptive_routing"][0]["correct"] is True
    assert report["adaptive_routing"][1]["correct"] is False


def test_build_report_includes_llm_judge_caveat_text():
    report = run_eval_mod.build_report([])
    assert "same Groq/Ollama backend" in report["llm_judge_caveat"]
