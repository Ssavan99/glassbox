from __future__ import annotations

import yaml

import engine.architectures.adaptive as adaptive
import engine.architectures.hybrid as hybrid_module
import engine.architectures.naive as naive_module
from engine.architectures.adaptive import AdaptiveArchitecture
from engine.config import QUESTIONS_PATH


def _all_questions() -> list[dict]:
    return yaml.safe_load(QUESTIONS_PATH.read_text())


def _first_question() -> str:
    return _all_questions()[0]["question"]


def _route_mock(chosen: str):
    """Mock for adaptive.complete's route call only."""

    def _fake_complete(prompt, json_schema=None, **params):
        return {
            "text": "",
            "json": {
                "chosen": chosen,
                "scores": {
                    "naive": 0.1,
                    "hybrid": 0.1,
                    "hyde": 0.1,
                    "corrective": 0.1,
                    "graph": 0.1,
                    "agentic": 0.1,
                    chosen: 0.9,
                },
                "reason": f"picked {chosen} for testing",
            },
            "prompt_tokens": 12,
            "completion_tokens": 6,
        }

    return _fake_complete


def _naive_generate_mock(answer_text="mocked naive answer"):
    def _fake_complete(prompt, json_schema=None, **params):
        return {"text": answer_text, "prompt_tokens": 40, "completion_tokens": 20}

    return _fake_complete


def test_adaptive_produces_valid_trace(monkeypatch):
    monkeypatch.setattr(adaptive, "complete", _route_mock("naive"))
    monkeypatch.setattr(naive_module, "complete", _naive_generate_mock("the naive answer"))

    question = _first_question()
    trace = AdaptiveArchitecture().run(question)

    trace.validate()

    kinds = [n.kind for n in trace.nodes]
    assert kinds[0] == "route"
    assert kinds[1:] == ["embed_query", "retrieve_dense", "generate"]

    ids = [n.id for n in trace.nodes]
    assert ids[1:] == ["naive::n1", "naive::n2", "naive::n3"]

    assert trace.answer == "the naive answer"


def test_splice_produces_no_id_collisions_or_dangling_parents_on_real_data(monkeypatch):
    # Mock only the delegates' own `complete()` calls, to keep this fast/free,
    # but run the real delegate flow (real index, real retrieval) for real
    # node ids and a real un-spliced trace to compare against.
    from engine.architectures.hybrid import HybridArchitecture
    from engine.architectures.naive import NaiveArchitecture

    monkeypatch.setattr(naive_module, "complete", _naive_generate_mock("naive real answer"))
    monkeypatch.setattr(hybrid_module, "complete", _naive_generate_mock("hybrid real answer"))

    question = _first_question()

    # Get the un-spliced delegated traces directly for comparison.
    naive_trace = NaiveArchitecture().run(question)
    hybrid_trace = HybridArchitecture().run(question)
    naive_root_ids = {n.id for n in naive_trace.nodes if not n.parent_ids}
    hybrid_root_ids = {n.id for n in hybrid_trace.nodes if not n.parent_ids}
    assert naive_root_ids  # sanity: naive's trace does have a root
    assert hybrid_root_ids

    for chosen, root_ids in (("naive", naive_root_ids), ("hybrid", hybrid_root_ids)):
        monkeypatch.setattr(adaptive, "complete", _route_mock(chosen))
        trace = AdaptiveArchitecture().run(question)

        # (a) no duplicate ids
        all_ids = [n.id for n in trace.nodes]
        assert len(set(all_ids)) == len(all_ids)

        # (b) no dangling parents
        id_set = set(all_ids)
        for node in trace.nodes:
            for parent_id in node.parent_ids:
                assert parent_id in id_set

        # (c) validate() doesn't raise
        trace.validate()

        # (d) delegate's original root nodes now point to the route node
        route_node = next(n for n in trace.nodes if n.kind == "route")
        spliced_root_ids = {f"{chosen}::{rid}" for rid in root_ids}
        for node in trace.nodes:
            if node.id in spliced_root_ids:
                assert node.parent_ids == [route_node.id]


def test_invalid_router_choice_falls_back_to_naive(monkeypatch):
    monkeypatch.setattr(naive_module, "complete", _naive_generate_mock("fallback answer"))

    question = _first_question()

    # Case 1: chosen is a made-up architecture name.
    monkeypatch.setattr(adaptive, "complete", _route_mock("not_a_real_architecture"))
    trace = AdaptiveArchitecture().run(question)
    trace.validate()
    route_node = next(n for n in trace.nodes if n.kind == "route")
    assert route_node.payload["chosen"] == "naive"
    assert "fell back to naive" in route_node.payload["reason"]
    assert any(n.id.startswith("naive::") for n in trace.nodes)

    # Case 2: non-dict JSON returned entirely.
    def _non_dict_route(prompt, json_schema=None, **params):
        return {
            "text": "",
            "json": ["not", "a", "dict"],
            "prompt_tokens": 5,
            "completion_tokens": 2,
        }

    monkeypatch.setattr(adaptive, "complete", _non_dict_route)
    trace2 = AdaptiveArchitecture().run(question)
    trace2.validate()
    route_node2 = next(n for n in trace2.nodes if n.kind == "route")
    assert route_node2.payload["chosen"] == "naive"
    assert "fell back to naive" in route_node2.payload["reason"]

    # Case 3: `chosen` key missing entirely.
    def _missing_chosen_route(prompt, json_schema=None, **params):
        return {
            "text": "",
            "json": {"scores": {}, "reason": "no chosen key here"},
            "prompt_tokens": 5,
            "completion_tokens": 2,
        }

    monkeypatch.setattr(adaptive, "complete", _missing_chosen_route)
    trace3 = AdaptiveArchitecture().run(question)
    trace3.validate()
    route_node3 = next(n for n in trace3.nodes if n.kind == "route")
    assert route_node3.payload["chosen"] == "naive"
    assert "fell back to naive" in route_node3.payload["reason"]


def test_metrics_sum_route_and_delegate_calls(monkeypatch):
    monkeypatch.setattr(adaptive, "complete", _route_mock("naive"))
    monkeypatch.setattr(naive_module, "complete", _naive_generate_mock("naive answer for metrics"))

    question = _first_question()
    trace = AdaptiveArchitecture().run(question)

    # route call: prompt_tokens=12, completion_tokens=6 (from _route_mock)
    # naive's generate call: prompt_tokens=40, completion_tokens=20
    assert trace.metrics.llm_calls == 1 + 1
    assert trace.metrics.prompt_tokens == 12 + 40
    assert trace.metrics.completion_tokens == 6 + 20


def test_duration_ms_is_populated(monkeypatch):
    monkeypatch.setattr(adaptive, "complete", _route_mock("naive"))
    monkeypatch.setattr(naive_module, "complete", _naive_generate_mock("naive answer"))

    question = _first_question()
    trace = AdaptiveArchitecture().run(question)

    route_node = next(n for n in trace.nodes if n.kind == "route")
    assert route_node.duration_ms > 0
