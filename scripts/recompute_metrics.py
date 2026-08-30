"""Recomputes evaluation/metrics.py's deterministic metrics for every row in
an already-written artifacts/eval.json -- adding recall_full and
graph_tool_involved, and rebuilding the by_architecture/by_architecture_and_type
summaries to include them -- with ZERO new LLM calls.

This is a pure-computation pass over the already-recorded
artifacts/traces/*.json (re-walked via extract_retrieved_chunk_ids, same as
the original run) and the already-recorded LLM-judge output already sitting
in artifacts/eval.json's rows (faithfulness, reads_as_refusal,
judge_reasoning, judge_backend -- reused as-is, never re-judged). See
repo-plans/glassbox_PLAN.md's Phase 6.1 for why this exists: recall@5's
k-truncation was diagnosed as an unfair lens on Graph's (and partially
Agentic/Adaptive's) unranked retrieval, and this fix should not cost a
second real LLM-judge sweep to apply.

Run scripts/record_traces.py + evaluation/run_eval.py again from scratch
instead of this script only if the traces themselves need to change (e.g. an
actual architecture bug fix) -- this script assumes the traces and judge
output already on disk are correct and only recomputes what's newly added.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.config import EVAL_PATH, TRACES_DIR
from engine.trace import Trace
from evaluation.run_eval import ARCHITECTURES, build_report, eval_one, load_questions


def main() -> None:
    old_report = json.loads(EVAL_PATH.read_text())
    old_rows_by_key = {(r["architecture"], r["question_id"]): r for r in old_report["rows"]}
    expected_keys = {(arch, q["id"]) for arch in ARCHITECTURES for q in load_questions()}

    questions = load_questions()
    rows: list[dict] = []
    missing: list[str] = []
    mismatched: list[str] = []

    for arch_name in ARCHITECTURES:
        for question in questions:
            key = (arch_name, question["id"])
            old_row = old_rows_by_key.get(key)
            trace_path = TRACES_DIR / f"{arch_name}__{question['id']}.json"
            if old_row is None or not trace_path.exists():
                missing.append(f"{arch_name}::{question['id']}")
                continue

            trace = Trace.from_dict(json.loads(trace_path.read_text()))

            # record_traces.py and run_eval.py are two independently-invoked
            # scripts writing two independent artifacts -- nothing else
            # guarantees the trace on disk right now is the same run that
            # produced old_row's judge verdict. trace_id and answer are both
            # already recorded on both sides for free, so check them before
            # reusing old_row's judge fields verbatim: a partial re-run of
            # just one of those two scripts must fail loudly here, not
            # silently pair fresh retrieval data with a stale judge verdict
            # for a different answer.
            if trace.trace_id != old_row["trace_id"] or trace.answer != old_row["answer"]:
                mismatched.append(f"{arch_name}::{question['id']}")
                continue

            # Recover the judge call's own token counts exactly (they were
            # folded into old_row's combined prompt/completion totals
            # alongside the trace's own token usage, not stored separately)
            # so re-summing inside eval_one reproduces the original totals
            # instead of silently losing the judge's share.
            judge = {
                "faithfulness": old_row["faithfulness"],
                "reads_as_refusal": old_row["reads_as_refusal"],
                "reasoning": old_row["judge_reasoning"],
                "backend": old_row["judge_backend"],
                "prompt_tokens": old_row["prompt_tokens"] - trace.metrics.prompt_tokens,
                "completion_tokens": old_row["completion_tokens"] - trace.metrics.completion_tokens,
            }

            row = eval_one(arch_name, question, trace, old_row["backend_calls"], judge=judge)
            if arch_name == "adaptive" and "adaptive_routed_to" in old_row:
                row["adaptive_routed_to"] = old_row["adaptive_routed_to"]
            rows.append(row)

    stale = sorted(
        f"{arch}::{qid}" for arch, qid in old_rows_by_key if (arch, qid) not in expected_keys
    )

    if missing or mismatched or stale:
        raise SystemExit(
            "recompute_metrics: refusing to write a partial/inconsistent eval.json -- "
            f"missing trace or eval row: {missing or 'none'}; "
            f"trace/judge mismatch (trace_id or answer disagree with the old eval row, "
            f"likely a partial re-run of only one of record_traces.py/run_eval.py): "
            f"{mismatched or 'none'}; "
            f"stale rows in the old eval.json with no matching (architecture, question) "
            f"in the current ARCHITECTURES/questions.yaml: {stale or 'none'}"
        )

    report = build_report(rows)
    EVAL_PATH.write_text(json.dumps(report, indent=2))
    print(f"recomputed {len(rows)} rows (0 new LLM calls), wrote {EVAL_PATH}")


if __name__ == "__main__":
    main()
