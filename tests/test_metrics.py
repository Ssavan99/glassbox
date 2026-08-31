import pytest

from engine.trace import Metrics, TraceBuilder
from evaluation.metrics import (
    extract_retrieved_chunk_ids,
    graph_tool_involved,
    judge_answer,
    mrr_at_k,
    ndcg_at_k,
    recall_at_k,
    recall_full,
    refusal_correctness,
)


def _metrics(**overrides):
    base = dict(latency_ms=1.0, llm_calls=1, prompt_tokens=1, completion_tokens=1)
    base.update(overrides)
    return Metrics(**base)


def _ranked(chunk_ids: list[str]) -> list[dict]:
    return [
        {"chunk_id": cid, "score": 1.0 - i * 0.1, "rank": i + 1} for i, cid in enumerate(chunk_ids)
    ]


# --- extract_retrieved_chunk_ids -------------------------------------------


def test_extract_naive_style_single_retrieve_node():
    b = TraceBuilder(architecture="naive", question="q")
    n1 = b.node("embed_query", "embed", parents=[], explain="e")
    n2 = b.node(
        "retrieve_dense",
        "retrieve",
        parents=[n1],
        explain="e",
        results=_ranked(["a", "b", "c"]),
        k=5,
    )
    b.node("generate", "gen", parents=[n2], explain="e", output="ans")
    trace = b.build(answer="ans", metrics=_metrics())

    assert extract_retrieved_chunk_ids(trace) == ["a", "b", "c"]


def test_extract_hybrid_style_uses_rerank_after_not_before():
    b = TraceBuilder(architecture="hybrid", question="q")
    n1 = b.node("embed_query", "embed", parents=[], explain="e")
    n2 = b.node(
        "retrieve_dense", "d", parents=[n1], explain="e", results=_ranked(["a", "b"]), k=5
    )
    n3 = b.node(
        "retrieve_sparse", "s", parents=[n1], explain="e", results=_ranked(["c", "d"]), k=5
    )
    n4 = b.node(
        "fuse", "f", parents=[n2, n3], explain="e", method="rrf", k=60, inputs=[n2, n3], results=[]
    )
    n5 = b.node(
        "rerank",
        "r",
        parents=[n4],
        explain="e",
        model="m",
        before=_ranked(["a", "c", "b", "d"]),
        after=_ranked(["c", "a"]),
    )
    b.node("generate", "gen", parents=[n5], explain="e", output="ans")
    trace = b.build(answer="ans", metrics=_metrics())

    # Must use "after" (final reranked order), not "before" or the raw
    # dense/sparse lists further upstream.
    assert extract_retrieved_chunk_ids(trace) == ["c", "a"]


def test_extract_stops_at_last_corrective_attempt_not_earlier_discarded_ones():
    b = TraceBuilder(architecture="corrective", question="q")
    n1 = b.node("embed_query", "e1", parents=[], explain="e")
    n2 = b.node(
        "retrieve_dense", "d1", parents=[n1], explain="e", results=_ranked(["wrong1"]), k=5
    )
    n3 = b.node("grade", "g1", parents=[n2], explain="e", judgements=[])
    n4 = b.node(
        "rewrite", "rw", parents=[n3], explain="e", **{"from": "q", "to": "q2", "reason": "r"}
    )
    n5 = b.node("embed_query", "e2", parents=[n4], explain="e")
    n6 = b.node(
        "retrieve_dense", "d2", parents=[n5], explain="e", results=_ranked(["right1"]), k=5
    )
    n7 = b.node("grade", "g2", parents=[n6], explain="e", judgements=[])
    b.node("generate", "gen", parents=[n7], explain="e", output="ans")
    trace = b.build(answer="ans", metrics=_metrics())

    # Only the second (final) attempt's chunks should show up.
    assert extract_retrieved_chunk_ids(trace) == ["right1"]


def test_extract_excludes_chunks_graded_incorrect_by_the_final_grade_node():
    # Regression test: corrective.py itself drops any chunk graded
    # "incorrect" from what it actually hands to generate (see its own
    # `filtered_chunks` logic) -- extract_retrieved_chunk_ids must mirror
    # that instead of treating `grade` as a no-op pass-through, or it
    # credits the architecture with "retrieving" a chunk the LLM never
    # actually saw.
    b = TraceBuilder(architecture="corrective", question="q")
    n1 = b.node("embed_query", "e1", parents=[], explain="e")
    n2 = b.node(
        "retrieve_dense",
        "d1",
        parents=[n1],
        explain="e",
        results=_ranked(["keep1", "drop1", "keep2"]),
        k=5,
    )
    n3 = b.node(
        "grade",
        "g1",
        parents=[n2],
        explain="e",
        judgements=[
            {"chunk_id": "keep1", "verdict": "correct", "reason": "r"},
            {"chunk_id": "drop1", "verdict": "incorrect", "reason": "r"},
            {"chunk_id": "keep2", "verdict": "ambiguous", "reason": "r"},
        ],
    )
    b.node("generate", "gen", parents=[n3], explain="e", output="ans")
    trace = b.build(answer="ans", metrics=_metrics())

    assert extract_retrieved_chunk_ids(trace) == ["keep1", "keep2"]


def test_extract_falls_back_to_unfiltered_when_everything_graded_incorrect():
    # Mirrors corrective.py's own fallback: if filtering out "incorrect"
    # chunks would leave nothing, keep the full unfiltered set rather than
    # handing generate (and this extractor) an empty context.
    b = TraceBuilder(architecture="corrective", question="q")
    n1 = b.node("embed_query", "e1", parents=[], explain="e")
    n2 = b.node(
        "retrieve_dense", "d1", parents=[n1], explain="e", results=_ranked(["a", "b"]), k=5
    )
    n3 = b.node(
        "grade",
        "g1",
        parents=[n2],
        explain="e",
        judgements=[
            {"chunk_id": "a", "verdict": "incorrect", "reason": "r"},
            {"chunk_id": "b", "verdict": "incorrect", "reason": "r"},
        ],
    )
    b.node("generate", "gen", parents=[n3], explain="e", output="ans")
    trace = b.build(answer="ans", metrics=_metrics())

    assert extract_retrieved_chunk_ids(trace) == ["a", "b"]


def test_extract_aggregates_across_agentic_multi_subquestion_parents():
    b = TraceBuilder(architecture="agentic", question="q")
    plan = b.node("plan", "p", parents=[], explain="e", sub_questions=["sq1", "sq2"])
    r1 = b.node("route", "r1", parents=[plan], explain="e", chosen="dense", scores={}, reason="x")
    d1 = b.node(
        "retrieve_dense", "d1", parents=[r1], explain="e", results=_ranked(["from-sq1"]), k=5
    )
    ref1 = b.node(
        "reflect",
        "ref1",
        parents=[d1],
        explain="e",
        sufficient=True,
        reason="x",
        next_action="proceed",
    )
    r2 = b.node("route", "r2", parents=[plan], explain="e", chosen="sparse", scores={}, reason="x")
    d2 = b.node(
        "retrieve_sparse", "d2", parents=[r2], explain="e", results=_ranked(["from-sq2"]), k=5
    )
    ref2 = b.node(
        "reflect",
        "ref2",
        parents=[d2],
        explain="e",
        sufficient=True,
        reason="x",
        next_action="proceed",
    )
    b.node("generate", "gen", parents=[ref1, ref2], explain="e", output="ans")
    trace = b.build(answer="ans", metrics=_metrics())

    result = extract_retrieved_chunk_ids(trace)
    assert set(result) == {"from-sq1", "from-sq2"}


def test_extract_raises_if_trace_does_not_end_in_generate():
    b = TraceBuilder(architecture="graph", question="q")
    b.node("graph_seed", "s", parents=[], explain="e", entities=[])
    trace = b.build(answer="ans", metrics=_metrics())

    with pytest.raises(ValueError, match="expected the trace to end in a generate node"):
        extract_retrieved_chunk_ids(trace)


# --- recall / mrr / ndcg ----------------------------------------------------


def test_recall_at_k_full_and_partial_and_zero():
    assert recall_at_k(["a", "b", "c"], ["a"], k=5) == 1.0
    assert recall_at_k(["a", "b", "c"], ["a", "z"], k=5) == 0.5
    assert recall_at_k(["a", "b", "c"], ["z"], k=5) == 0.0
    assert recall_at_k(["a", "b", "c", "d", "e", "f"], ["f"], k=5) == 0.0  # outside top-5


def test_recall_at_k_undefined_for_empty_gold():
    assert recall_at_k(["a", "b"], [], k=5) is None


def test_mrr_at_k_first_hit_rank():
    assert mrr_at_k(["z", "a", "b"], ["a"], k=10) == pytest.approx(0.5)
    assert mrr_at_k(["a", "b"], ["a"], k=10) == pytest.approx(1.0)
    assert mrr_at_k(["z", "y"], ["a"], k=10) == 0.0


def test_mrr_at_k_undefined_for_empty_gold():
    assert mrr_at_k(["a"], [], k=10) is None


def test_ndcg_at_k_perfect_ranking_is_one():
    assert ndcg_at_k(["a", "b"], ["a", "b"], k=10) == pytest.approx(1.0)


def test_ndcg_at_k_worse_ranking_scores_lower_than_perfect():
    perfect = ndcg_at_k(["a", "b"], ["a", "b"], k=10)
    worse = ndcg_at_k(["z", "a", "b"], ["a", "b"], k=10)
    assert 0 < worse < perfect


def test_ndcg_at_k_zero_when_nothing_relevant_found():
    assert ndcg_at_k(["z", "y"], ["a"], k=10) == 0.0


def test_ndcg_at_k_undefined_for_empty_gold():
    assert ndcg_at_k(["a"], [], k=10) is None


def test_recall_full_finds_gold_chunks_regardless_of_position():
    # Both gold chunks are present, but the second is far past where
    # recall_at_5 would ever look -- recall_full has no k cutoff.
    retrieved = ["z"] * 20 + ["a", "b"]
    assert recall_full(retrieved, ["a", "b"]) == 1.0
    assert recall_at_k(retrieved, ["a", "b"], k=5) == 0.0


def test_recall_full_partial_and_zero():
    assert recall_full(["a", "b", "c"], ["a", "z"]) == 0.5
    assert recall_full(["a", "b", "c"], ["z"]) == 0.0


def test_recall_full_undefined_for_empty_gold():
    assert recall_full(["a", "b"], []) is None


# --- graph_tool_involved -----------------------------------------------------


def test_graph_tool_involved_true_when_trace_has_graph_expand_node():
    b = TraceBuilder(architecture="graph", question="q")
    n1 = b.node("graph_seed", "seed", parents=[], explain="e", entities=["x"])
    n2 = b.node(
        "graph_expand", "expand", parents=[n1], explain="e", hops=2, edges=[], chunk_ids=["a"]
    )
    b.node("generate", "gen", parents=[n2], explain="e", output="ans")
    trace = b.build(answer="ans", metrics=_metrics())

    assert graph_tool_involved(trace) is True


def test_graph_tool_involved_false_when_no_graph_expand_node_anywhere():
    b = TraceBuilder(architecture="naive", question="q")
    n1 = b.node("embed_query", "embed", parents=[], explain="e")
    n2 = b.node(
        "retrieve_dense", "retrieve", parents=[n1], explain="e", results=_ranked(["a"]), k=5
    )
    b.node("generate", "gen", parents=[n2], explain="e", output="ans")
    trace = b.build(answer="ans", metrics=_metrics())

    assert graph_tool_involved(trace) is False


# --- judge_answer / refusal_correctness -------------------------------------


def test_judge_answer_computes_faithfulness_from_point_support(monkeypatch):
    import evaluation.metrics as metrics_mod

    def _fake_complete(prompt, json_schema=None, **params):
        return {
            "text": "",
            "json": {
                "point_support": [True, False, True],
                "reads_as_appropriate_refusal": False,
                "reasoning": "two of three points supported",
            },
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "backend": "ollama",
        }

    monkeypatch.setattr(metrics_mod, "complete", _fake_complete)

    result = judge_answer("q", "some answer", ["point a", "point b", "point c"])
    assert result["faithfulness"] == pytest.approx(2 / 3)
    assert result["reads_as_refusal"] is False
    assert result["backend"] == "ollama"


def test_judge_answer_faithfulness_none_when_no_gold_points(monkeypatch):
    import evaluation.metrics as metrics_mod

    def _fake_complete(prompt, json_schema=None, **params):
        return {
            "text": "",
            "json": {"point_support": [], "reads_as_appropriate_refusal": True, "reasoning": "r"},
            "prompt_tokens": 5,
            "completion_tokens": 2,
            "backend": "groq",
        }

    monkeypatch.setattr(metrics_mod, "complete", _fake_complete)

    result = judge_answer("q", "I don't know", [])
    assert result["faithfulness"] is None
    assert result["reads_as_refusal"] is True


def test_judge_answer_treats_string_false_as_unsupported(monkeypatch):
    import evaluation.metrics as metrics_mod

    def _fake_complete(prompt, json_schema=None, **params):
        return {
            "text": "",
            "json": {
                "point_support": ["false"],
                "reads_as_appropriate_refusal": False,
                "reasoning": "schema-violating string",
            },
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "backend": "ollama",
        }

    monkeypatch.setattr(metrics_mod, "complete", _fake_complete)

    result = judge_answer("q", "answer", ["point a"])
    assert result["faithfulness"] == 0.0


def test_judge_answer_survives_malformed_json(monkeypatch):
    import evaluation.metrics as metrics_mod

    def _fake_complete(prompt, json_schema=None, **params):
        return {
            "text": "not json",
            "json": ["not", "a", "dict"],
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "backend": "ollama",
        }

    monkeypatch.setattr(metrics_mod, "complete", _fake_complete)

    result = judge_answer("q", "answer", ["point a"])
    assert result["faithfulness"] == 0.0
    assert result["reads_as_refusal"] is False


def test_refusal_correctness_only_meaningful_for_unanswerable():
    assert refusal_correctness(is_unanswerable=True, reads_as_refusal=True) is True
    assert refusal_correctness(is_unanswerable=True, reads_as_refusal=False) is False
    assert refusal_correctness(is_unanswerable=False, reads_as_refusal=True) is None
