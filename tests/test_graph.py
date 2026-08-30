import os
import subprocess
import sys
from pathlib import Path

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


def test_graph_expand_payload_matches_what_generate_actually_used(monkeypatch):
    # Trace fidelity: if expand_hops (or a desynced artifacts/graph.json)
    # returns a chunk_id that isn't actually in the loaded index, the
    # graph_expand node's recorded chunk_ids must reflect only what was
    # really resolved and handed to generate -- not the raw, unfiltered
    # expand_hops output. Simulates a stale-artifact chunk_id by injecting
    # a fake id that can't resolve against the real index.
    _mock_complete(monkeypatch)
    q05 = _question_by_id("q05")

    g = load_graph()
    real_chunk_ids, real_edges = graph_arch.expand_hops(seed_entities(q05["question"], g), g)
    assert real_chunk_ids, "expected q05's expansion to find at least one real chunk"

    poisoned_chunk_ids = ["stale-note::999", *real_chunk_ids]

    def _fake_expand_hops(seeds, graph, *args, **kwargs):
        return poisoned_chunk_ids, real_edges

    monkeypatch.setattr(graph_arch, "expand_hops", _fake_expand_hops)

    trace = graph_arch.GraphArchitecture().run(q05["question"])
    trace.validate()

    expand_node = next(n for n in trace.nodes if n.kind == "graph_expand")
    assert "stale-note::999" not in expand_node.payload["chunk_ids"]
    assert expand_node.payload["chunk_ids"] == real_chunk_ids


def test_prompt_is_stable_across_process_hash_seeds():
    # Community-summary ordering (and expand_hops's chunk tie-breaking)
    # used to depend on Python set iteration order, which CPython
    # randomizes per-process by default -- verify the fix by running the
    # exact same question through two fresh interpreter subprocesses under
    # deliberately different PYTHONHASHSEED values and confirming the
    # generate prompt (and therefore engine/llm.py's cache key) is
    # byte-identical both times.
    q05_question = _question_by_id("q05")["question"]
    script = (
        "import unittest.mock as mock\n"
        "import engine.architectures.graph as graph_arch\n"
        "captured = {}\n"
        "def _fake_complete(prompt, **params):\n"
        "    captured['prompt'] = prompt\n"
        "    return {'text': 'a', 'prompt_tokens': 1, 'completion_tokens': 1}\n"
        "with mock.patch.object(graph_arch, 'complete', _fake_complete):\n"
        f"    graph_arch.GraphArchitecture().run({q05_question!r})\n"
        "print(captured['prompt'])\n"
    )
    root = Path(__file__).resolve().parent.parent
    prompts = set()
    for seed in ("1", "99999"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=root,
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
        prompts.add(result.stdout)
    assert len(prompts) == 1, "generate prompt differed across PYTHONHASHSEED values"


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
