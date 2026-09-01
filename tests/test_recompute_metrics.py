import json
import unittest.mock as mock

import pytest

import scripts.recompute_metrics as recompute_mod
from engine.trace import Metrics, TraceBuilder


def _metrics(**overrides):
    base = dict(latency_ms=1.0, llm_calls=1, prompt_tokens=10, completion_tokens=4)
    base.update(overrides)
    return Metrics(**base)


def _trace(trace_id="naive::q01", answer="the answer", chunk_ids=("gold1",)):
    b = TraceBuilder(architecture="naive", question="q", trace_id=trace_id)
    n1 = b.node("embed_query", "embed", parents=[], explain="e")
    n2 = b.node(
        "retrieve_dense",
        "retrieve",
        parents=[n1],
        explain="e",
        results=[{"chunk_id": cid, "score": 1.0, "rank": i + 1} for i, cid in enumerate(chunk_ids)],
        k=5,
    )
    b.node("generate", "gen", parents=[n2], explain="e", output=answer)
    return b.build(answer=answer, metrics=_metrics())


def _old_row(**overrides):
    row = {
        "architecture": "naive",
        "question_id": "q01",
        "question_type": "factual",
        "trace_id": "naive::q01",
        "answer": "the answer",
        "retrieved_chunk_ids": ["gold1"],
        "gold_chunk_ids": ["gold1"],
        "recall_at_5": 1.0,
        "mrr_at_10": 1.0,
        "ndcg_at_10": 1.0,
        "faithfulness": 0.5,
        "reads_as_refusal": False,
        "refusal_correctness": None,
        "judge_reasoning": "looks fine",
        "latency_ms": 1.0,
        "llm_calls": 1,
        "prompt_tokens": 12,  # trace's 10 + judge's own 2
        "completion_tokens": 6,  # trace's 4 + judge's own 2
        "backend_calls": ["ollama"],
        "judge_backend": "groq",
    }
    row.update(overrides)
    return row


def _write_fixture(tmp_path, monkeypatch, old_rows, trace_by_key):
    eval_path = tmp_path / "eval.json"
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()

    eval_path.write_text(json.dumps({"rows": old_rows}))
    for (arch, qid), trace in trace_by_key.items():
        (traces_dir / f"{arch}__{qid}.json").write_text(json.dumps(trace.to_dict()))

    monkeypatch.setattr(recompute_mod, "EVAL_PATH", eval_path)
    monkeypatch.setattr(recompute_mod, "TRACES_DIR", traces_dir)
    monkeypatch.setattr(recompute_mod, "ARCHITECTURES", {"naive": object()})
    monkeypatch.setattr(
        recompute_mod,
        "load_questions",
        lambda: [
            {
                "id": "q01",
                "question": "q",
                "type": "factual",
                "gold_chunk_ids": ["gold1"],
                "gold_answer_points": ["p1"],
            }
        ],
    )
    return eval_path


def test_main_recomputes_recall_full_and_graph_tool_involved_with_zero_judge_calls(
    tmp_path, monkeypatch
):
    eval_path = _write_fixture(
        tmp_path,
        monkeypatch,
        old_rows=[_old_row()],
        trace_by_key={("naive", "q01"): _trace()},
    )

    def _boom(*args, **kwargs):
        raise AssertionError("judge_answer must not be called by the recompute script")

    with mock.patch.object(recompute_mod, "eval_one", wraps=recompute_mod.eval_one) as spy:
        with mock.patch("evaluation.metrics.judge_answer", _boom):
            recompute_mod.main()
        # judge= was passed explicitly on every call, never left to default
        # to a fresh judge_answer() call
        for call in spy.call_args_list:
            assert call.kwargs.get("judge") is not None

    new_report = json.loads(eval_path.read_text())
    row = new_report["rows"][0]
    assert row["recall_full"] == 1.0
    assert row["graph_tool_involved"] is False
    # judge fields carried over verbatim from the old row, not re-derived
    assert row["faithfulness"] == 0.5
    assert row["judge_backend"] == "groq"
    # token totals reproduce the old combined totals exactly (10+2=12, 4+2=6)
    assert row["prompt_tokens"] == 12
    assert row["completion_tokens"] == 6


def test_main_refuses_to_write_when_trace_answer_disagrees_with_old_judged_answer(
    tmp_path, monkeypatch
):
    # Simulates a partial re-run of only record_traces.py: the trace on disk
    # now reflects a different answer than the one the old eval.json row's
    # judge fields were computed against.
    eval_path = _write_fixture(
        tmp_path,
        monkeypatch,
        old_rows=[_old_row(answer="the OLD answer")],
        trace_by_key={("naive", "q01"): _trace(answer="a DIFFERENT new answer")},
    )
    before = eval_path.read_text()

    with pytest.raises(SystemExit, match="trace/judge mismatch"):
        recompute_mod.main()

    # refused to write a partial/inconsistent file
    assert eval_path.read_text() == before


def test_main_refuses_to_write_when_a_trace_file_is_missing(tmp_path, monkeypatch):
    eval_path = _write_fixture(
        tmp_path, monkeypatch, old_rows=[_old_row()], trace_by_key={}  # no trace file written
    )
    before = eval_path.read_text()

    with pytest.raises(SystemExit, match="missing trace or eval row"):
        recompute_mod.main()

    assert eval_path.read_text() == before


def test_main_refuses_to_write_when_old_eval_json_has_a_stale_row(tmp_path, monkeypatch):
    # An old row for a question that no longer exists in questions.yaml /
    # ARCHITECTURES -- should be caught, not silently dropped.
    eval_path = _write_fixture(
        tmp_path,
        monkeypatch,
        old_rows=[_old_row(), _old_row(question_id="q99", trace_id="naive::q99")],
        trace_by_key={("naive", "q01"): _trace()},
    )
    before = eval_path.read_text()

    with pytest.raises(SystemExit, match="stale rows"):
        recompute_mod.main()

    assert eval_path.read_text() == before
