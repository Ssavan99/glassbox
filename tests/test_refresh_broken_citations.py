import json
import unittest.mock as mock

import pytest

import scripts.refresh_broken_citations as refresh_mod
from engine.trace import Metrics, TraceBuilder


def _metrics(**overrides):
    base = dict(latency_ms=1.0, llm_calls=1, prompt_tokens=10, completion_tokens=4)
    base.update(overrides)
    return Metrics(**base)


def _trace(trace_id, answer, chunk_ids=("gold1",)):
    arch = trace_id.split("::")[0]
    b = TraceBuilder(architecture=arch, question="q", trace_id=trace_id)
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


def _old_row(arch, qid, answer, faithfulness=0.3):
    return {
        "architecture": arch,
        "question_id": qid,
        "question_type": "factual",
        "trace_id": f"{arch}::{qid}",
        "answer": answer,
        "retrieved_chunk_ids": ["gold1"],
        "gold_chunk_ids": ["gold1"],
        "recall_at_5": 1.0,
        "mrr_at_10": 1.0,
        "ndcg_at_10": 1.0,
        "recall_full": 1.0,
        "graph_tool_involved": False,
        "faithfulness": faithfulness,
        "reads_as_refusal": False,
        "refusal_correctness": None,
        "judge_reasoning": "stale",
        "latency_ms": 1.0,
        "llm_calls": 1,
        "prompt_tokens": 10,
        "completion_tokens": 4,
        "backend_calls": ["ollama"],
        "judge_backend": "ollama",
    }


@pytest.fixture(autouse=True)
def _no_real_calls_allowed():
    def _boom(*args, **kwargs):
        raise AssertionError("a real (unmocked) complete() call was attempted")

    with mock.patch("engine.llm._call_groq", _boom), mock.patch("engine.llm._call_ollama", _boom):
        yield


def _write_fixture(tmp_path, monkeypatch, old_rows, question_ids):
    eval_path = tmp_path / "eval.json"
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    eval_path.write_text(json.dumps({"rows": old_rows}))

    monkeypatch.setattr(refresh_mod, "EVAL_PATH", eval_path)
    monkeypatch.setattr(refresh_mod, "TRACES_DIR", traces_dir)
    monkeypatch.setattr(
        refresh_mod,
        "load_questions",
        lambda: [
            {
                "id": qid,
                "question": "q",
                "type": "factual",
                "gold_chunk_ids": ["gold1"],
                "gold_answer_points": ["p1"],
            }
            for qid in question_ids
        ],
    )
    return eval_path, traces_dir


def _fake_judge(**overrides):
    result = {
        "faithfulness": 1.0,
        "reads_as_refusal": False,
        "reasoning": "fresh judge call",
        "backend": "groq",
        "prompt_tokens": 2,
        "completion_tokens": 1,
    }
    result.update(overrides)
    return result


def test_only_rows_containing_the_bug_marker_are_refreshed(tmp_path, monkeypatch):
    eval_path, traces_dir = _write_fixture(
        tmp_path,
        monkeypatch,
        old_rows=[
            _old_row("naive", "q01", "cites [chunk-id::0] literally, a fake id"),
            _old_row("hybrid", "q02", "cites [real-chunk::1] correctly, no bug"),
        ],
        question_ids=["q01", "q02"],
    )

    fixed_trace = _trace("naive::q01", "a corrected answer citing [gold1]")

    def _fake_run_one(arch_name, question):
        assert (arch_name, question["id"]) == ("naive", "q01")  # never called for the clean row
        return fixed_trace, ["groq"]

    with (
        mock.patch.object(refresh_mod, "run_one", side_effect=_fake_run_one) as run_one_spy,
        mock.patch("evaluation.run_eval.judge_answer", return_value=_fake_judge()),
    ):
        refresh_mod.main()

    assert run_one_spy.call_count == 1  # the clean hybrid::q02 row was never re-run

    new_report = json.loads(eval_path.read_text())
    rows_by_key = {(r["architecture"], r["question_id"]): r for r in new_report["rows"]}

    fixed = rows_by_key[("naive", "q01")]
    assert "chunk-id::" not in fixed["answer"]
    assert fixed["faithfulness"] == 1.0  # freshly re-judged, not the stale 0.3

    untouched = rows_by_key[("hybrid", "q02")]
    assert untouched["answer"] == "cites [real-chunk::1] correctly, no bug"
    assert untouched["faithfulness"] == 0.3  # unchanged, no re-judge for a clean row

    # the untouched row's trace file was never written
    assert not (traces_dir / "hybrid__q02.json").exists()
    assert (traces_dir / "naive__q01.json").exists()


def test_refuses_to_write_if_the_fix_did_not_actually_resolve_a_trace(tmp_path, monkeypatch):
    eval_path, traces_dir = _write_fixture(
        tmp_path,
        monkeypatch,
        old_rows=[_old_row("naive", "q01", "cites [chunk-id::0] literally, a fake id")],
        question_ids=["q01"],
    )
    before = eval_path.read_text()

    still_broken_trace = _trace("naive::q01", "still cites [chunk-id::0], the bug persists")

    with (
        mock.patch.object(refresh_mod, "run_one", return_value=(still_broken_trace, ["groq"])),
        mock.patch("evaluation.run_eval.judge_answer", return_value=_fake_judge()),
        pytest.raises(SystemExit, match="still contains"),
    ):
        refresh_mod.main()

    # refused to write a partial/incorrect eval.json, and never overwrote the trace file
    assert eval_path.read_text() == before
    assert not (traces_dir / "naive__q01.json").exists()


def test_a_later_row_still_broken_leaves_no_trace_files_written_even_for_earlier_rows(
    tmp_path, monkeypatch
):
    # Regression test for the buffered-writes fix: trace files must not be
    # written incrementally inside the loop, or a batch of N affected rows
    # where only the LAST one still has the bug would leave the first N-1
    # rows' trace files already fixed on disk while eval.json (only written
    # at the very end) still reports the old buggy answer for all of them --
    # a real trace/eval desync, not just a partial write.
    eval_path, traces_dir = _write_fixture(
        tmp_path,
        monkeypatch,
        old_rows=[
            _old_row("naive", "q01", "cites [chunk-id::0] literally, a fake id"),
            _old_row("hybrid", "q02", "also cites [chunk-id::1] literally, a fake id"),
        ],
        question_ids=["q01", "q02"],
    )
    before = eval_path.read_text()

    fixed_trace = _trace("naive::q01", "a corrected answer citing [gold1]")
    still_broken_trace = _trace("hybrid::q02", "still cites [chunk-id::1], the bug persists")

    def _fake_run_one(arch_name, question):
        return (fixed_trace, ["groq"]) if arch_name == "naive" else (still_broken_trace, ["groq"])

    with (
        mock.patch.object(refresh_mod, "run_one", side_effect=_fake_run_one),
        mock.patch("evaluation.run_eval.judge_answer", return_value=_fake_judge()),
        pytest.raises(SystemExit, match="still contains"),
    ):
        refresh_mod.main()

    assert eval_path.read_text() == before
    # neither trace file was written -- not even naive::q01's, which was
    # genuinely fixed, because the batch as a whole didn't fully succeed
    assert not (traces_dir / "naive__q01.json").exists()
    assert not (traces_dir / "hybrid__q02.json").exists()


def test_noop_when_nothing_is_affected(tmp_path, monkeypatch):
    eval_path, _ = _write_fixture(
        tmp_path,
        monkeypatch,
        old_rows=[_old_row("naive", "q01", "cites [real-chunk::1] correctly, no bug")],
        question_ids=["q01"],
    )

    with mock.patch.object(refresh_mod, "run_one") as run_one_spy:
        refresh_mod.main()

    run_one_spy.assert_not_called()
    new_report = json.loads(eval_path.read_text())
    assert new_report["rows"][0]["answer"] == "cites [real-chunk::1] correctly, no bug"
