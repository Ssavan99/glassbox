import subprocess
import sys
from pathlib import Path

import pytest

from engine.trace import Metrics, TraceBuilder, TraceValidationError


def _metrics(**overrides):
    base = dict(latency_ms=100.0, llm_calls=1, prompt_tokens=10, completion_tokens=5)
    base.update(overrides)
    return Metrics(**base)


def test_trace_id_is_stable_across_processes():
    # Python's built-in hash() is randomized per-process (PYTHONHASHSEED) by
    # default, so trace_id must not be derived from it. Verify by generating
    # the same trace_id in two fresh interpreter subprocesses.
    script = (
        "from engine.trace import TraceBuilder, Metrics\n"
        "b = TraceBuilder(architecture='naive', question='what is chunking?')\n"
        "b.node('embed_query', 'Embed', parents=[], explain='e')\n"
        "t = b.build(answer='a', metrics=Metrics(1.0, 1, 1, 1))\n"
        "print(t.trace_id)\n"
    )
    root = Path(__file__).resolve().parent.parent
    ids = set()
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, "-c", script], cwd=root, capture_output=True, text=True, check=True
        )
        ids.add(result.stdout.strip())
    assert len(ids) == 1


def test_trace_id_differs_for_different_questions():
    b1 = TraceBuilder(architecture="naive", question="what is chunking?")
    b1.node("embed_query", "Embed", parents=[], explain="e")
    t1 = b1.build(answer="a", metrics=_metrics())

    b2 = TraceBuilder(architecture="naive", question="what is reranking?")
    b2.node("embed_query", "Embed", parents=[], explain="e")
    t2 = b2.build(answer="a", metrics=_metrics())

    assert t1.trace_id != t2.trace_id


def test_linear_trace_builds_and_round_trips():
    b = TraceBuilder(architecture="naive", question="what is chunking?")
    n1 = b.node("embed_query", "Embed the question", parents=[], explain="why", dims=384)
    n2 = b.node(
        "retrieve_dense", "Top-5 dense", parents=[n1], explain="why", results=[], k=5
    )
    b.node("generate", "Generate answer", parents=[n2], explain="why", output="answer")
    trace = b.build(answer="answer", metrics=_metrics())

    trace.validate()
    round_tripped = trace.from_dict(trace.to_dict())
    round_tripped.validate()
    assert round_tripped.nodes[0].kind == "embed_query"


def test_branching_fuse_node_has_two_parents():
    b = TraceBuilder(architecture="hybrid", question="q")
    n1 = b.node("embed_query", "Embed", parents=[], explain="e")
    n2 = b.node("retrieve_dense", "Dense", parents=[n1], explain="e", results=[])
    n3 = b.node("retrieve_sparse", "Sparse", parents=[n1], explain="e", results=[])
    n4 = b.node("fuse", "RRF fuse", parents=[n2, n3], explain="e", method="rrf")
    b.node("generate", "Generate", parents=[n4], explain="e", output="a")
    trace = b.build(answer="a", metrics=_metrics())
    trace.validate()
    fuse_node = next(n for n in trace.nodes if n.kind == "fuse")
    assert fuse_node.parent_ids == [n2, n3]


def test_unknown_kind_rejected():
    b = TraceBuilder(architecture="naive", question="q")
    with pytest.raises(TraceValidationError):
        b.node("not_a_real_kind", "bad", parents=[], explain="e")


def test_dangling_parent_rejected():
    b = TraceBuilder(architecture="naive", question="q")
    b.node("embed_query", "Embed", parents=["ghost"], explain="e")
    with pytest.raises(TraceValidationError):
        b.build(answer="a", metrics=_metrics())


def test_cycle_rejected():
    b = TraceBuilder(architecture="naive", question="q")
    b.node("embed_query", "n1", parents=[], explain="e", node_id="n1")
    b.node("retrieve_dense", "n2", parents=["n1"], explain="e", node_id="n2", results=[])
    # Manually forge a cycle by editing parent_ids after construction.
    b._nodes[0].parent_ids = ["n2"]
    with pytest.raises(TraceValidationError):
        trace = b.build(answer="a", metrics=_metrics())
        trace.validate()


def test_empty_trace_rejected():
    b = TraceBuilder(architecture="naive", question="q")
    with pytest.raises(TraceValidationError):
        b.build(answer="a", metrics=_metrics())


def test_duplicate_node_id_rejected():
    b = TraceBuilder(architecture="naive", question="q")
    b.node("embed_query", "n1", parents=[], explain="e", node_id="dup")
    b.node("generate", "n2", parents=[], explain="e", node_id="dup", output="a")
    with pytest.raises(TraceValidationError):
        b.build(answer="a", metrics=_metrics())


def test_splice_prefixes_ids_and_attaches_root():
    delegate = TraceBuilder(architecture="hybrid", question="sub-question")
    d1 = delegate.node("embed_query", "Embed", parents=[], explain="e")
    delegate.node("retrieve_dense", "Dense", parents=[d1], explain="e", results=[])
    delegate.node("generate", "Generate", parents=[d1], explain="e", output="a")
    delegated_trace = delegate.build(answer="a", metrics=_metrics())

    parent = TraceBuilder(architecture="adaptive", question="q")
    route_id = parent.node("route", "Route", parents=[], explain="e", chosen="hybrid")
    spliced = parent.splice(delegated_trace.nodes, prefix="hybrid_0", parent_id=route_id)
    final_id = spliced[-1].id
    parent.node("generate", "Synth", parents=[final_id], explain="e", output="a")
    trace = parent.build(answer="a", metrics=_metrics())

    trace.validate()
    root_spliced = next(n for n in trace.nodes if n.id == "hybrid_0::" + d1)
    assert root_spliced.parent_ids == [route_id]
