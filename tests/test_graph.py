import yaml

import engine.architectures.graph as graph_arch
from engine.config import GRAPH_MAX_HOP_CHUNKS, QUESTIONS_PATH
from engine.graph_index import load_graph, seed_entities


def _questions():
    return yaml.safe_load(QUESTIONS_PATH.read_text())


def _question_by_id(qid: str) -> dict:
    return next(q for q in _questions() if q["id"] == qid)


def _mock_complete(monkeypatch, text="mocked answer"):
    calls = []

    def _fake_complete(prompt, **params):
        calls.append(prompt)
        return {"text": text, "prompt_tokens": 10, "completion_tokens": 5}

    monkeypatch.setattr(graph_arch, "complete", _fake_complete)
    return calls


def test_graph_produces_valid_trace(monkeypatch):
    calls = _mock_complete(monkeypatch)
    q01 = _question_by_id("q01")

    # confirm this question gets a real seed hit before relying on it
    g = load_graph()
    assert seed_entities(q01["question"], g), "expected q01 to have at least one seed match"

    trace = graph_arch.GraphArchitecture().run(q01["question"])

    kinds = [n.kind for n in trace.nodes]
    assert kinds == ["graph_seed", "graph_expand", "generate"]
    trace.validate()
    assert len(calls) == 1


def test_graph_seed_zero_online_llm_calls_before_generate(monkeypatch):
    calls = _mock_complete(monkeypatch)
    q05 = _question_by_id("q05")

    trace = graph_arch.GraphArchitecture().run(q05["question"])

    # exactly one LLM call total across the whole run, made only by generate
    assert len(calls) == 1
    assert trace.metrics.llm_calls == 1


def test_graph_handles_zero_seed_entities_gracefully(monkeypatch):
    _mock_complete(monkeypatch)
    q04 = _question_by_id("q04")

    g = load_graph()
    seeds = seed_entities(q04["question"], g)
    assert seeds == [], "expected q04 to be a known zero-seed miss"

    trace = graph_arch.GraphArchitecture().run(q04["question"])

    trace.validate()
    kinds = [n.kind for n in trace.nodes]
    assert kinds == ["graph_seed", "graph_expand", "generate"]

    seed_node = next(n for n in trace.nodes if n.kind == "graph_seed")
    expand_node = next(n for n in trace.nodes if n.kind == "graph_expand")
    assert seed_node.payload["entities"] == []
    assert expand_node.payload["chunk_ids"] == []
    assert expand_node.payload["edges"] == []


def test_graph_expand_respects_hop_cap(monkeypatch):
    _mock_complete(monkeypatch)
    q11 = _question_by_id("q11")

    trace = graph_arch.GraphArchitecture().run(q11["question"])

    expand_node = next(n for n in trace.nodes if n.kind == "graph_expand")
    assert len(expand_node.payload["chunk_ids"]) <= GRAPH_MAX_HOP_CHUNKS


def test_community_summaries_reach_the_prompt(monkeypatch):
    calls = _mock_complete(monkeypatch)
    q05 = _question_by_id("q05")

    g = load_graph()
    seeds = seed_entities(q05["question"], g)
    assert seeds, "expected q05 to have seed hits"

    trace = graph_arch.GraphArchitecture().run(q05["question"])
    trace.validate()

    assert len(calls) == 1
    prompt = calls[0]

    # at least one community summary's text should appear in the prompt
    found = False
    for community in g.communities.values():
        if community.summary and community.summary in prompt:
            found = True
            break
    assert found, "expected at least one community summary to reach the generate prompt"
