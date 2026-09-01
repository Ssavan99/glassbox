"""After fixing engine/prompts.py's SYSTEM_PREAMBLE (the old "e.g.
[chunk-id::0]" example was sometimes echoed verbatim by the model as a fake
citation instead of a real chunk id), regenerate the final `generate` node for every
trace whose currently-recorded answer still exhibits the bug (contains the
literal string "chunk-id::").

This is a *targeted* re-run, not a full resweep. SYSTEM_PREAMBLE feeds every
architecture's final `generate` prompt, so its cache key changed for all 189
recorded traces -- but only the traces that actually echoed the fake
citation need a corrected answer; the other ~150 already cite real ids and
don't need to burn a fresh LLM call just because the prompt's wording
changed.

Re-running each affected (architecture, question) pair through the real
`Architecture.run()` -- via evaluation.run_eval.run_one(), the same helper
record_traces.py/run_eval.py already use -- naturally reuses
engine/llm.py's disk cache for every LLM call whose prompt is unchanged
(retrieve/grade/reflect/plan/route/graph_expand/generate_hypothetical/...),
so only the final `generate` call (new prompt) makes a real new LLM call.
This is chosen over hand-reconstructing each architecture's upstream
chunk-gathering logic and splicing a new generate node in by hand: Corrective's
grade-filter fallback, Agentic's per-sub-question aggregation, Graph's
extra_context (community summaries), and Adaptive's trace-splicing each have
real subtlety that would be risky to duplicate outside the actual
architecture code. Re-running through run_one() gets the same "only the
generate node actually changes" result with much less engineering risk.

Because the answer text changes, each affected row's LLM-judged faithfulness
must be recomputed for real too (a fresh judge_answer() call) -- unlike
scripts/recompute_metrics.py, which deliberately reuses old judge output
because nothing about what was actually generated changed there.

All disk writes (every regenerated trace file plus artifacts/eval.json) are
buffered in memory and only committed after every affected row has been
successfully regenerated. This closes an inconsistency window a first
version of this script had: writing each trace file inside the loop but
artifacts/eval.json only once at the end meant a mid-batch failure (a later
row still buggy, or a real exception) would leave earlier rows' trace files
already fixed on disk while eval.json still reported the old buggy answer
for them -- self-healing on a retry thanks to the LLM cache, but a real,
silent desync window in the meantime. Buffering means either every affected
row's trace + eval.json update lands together, or nothing does.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.config import EVAL_PATH, TRACES_DIR
from evaluation.run_eval import build_report, eval_one, load_questions, run_one

BUG_MARKER = "chunk-id::"


def main() -> None:
    old_report = json.loads(EVAL_PATH.read_text())
    old_rows_by_key = {(r["architecture"], r["question_id"]): r for r in old_report["rows"]}
    questions_by_id = {q["id"]: q for q in load_questions()}

    affected = sorted(
        key for key, row in old_rows_by_key.items() if BUG_MARKER in row["answer"]
    )
    print(f"found {len(affected)} traces with the literal {BUG_MARKER!r} bug:")
    for arch_name, question_id in affected:
        print(f"  {arch_name}::{question_id}")

    rows_by_key = dict(old_rows_by_key)  # start from old rows; only the affected keys change
    # buffered, not written to disk until the whole batch succeeds
    pending_trace_writes: dict[Path, str] = {}

    for arch_name, question_id in affected:
        question = questions_by_id[question_id]
        trace, backend_calls = run_one(arch_name, question)
        trace.validate()

        if BUG_MARKER in trace.answer:
            raise SystemExit(
                f"refresh_broken_citations: {arch_name}::{question_id} still contains "
                f"{BUG_MARKER!r} after the SYSTEM_PREAMBLE fix -- the fix did not resolve "
                "this trace. Refusing to write any artifacts from this batch; investigate first."
            )

        trace_path = TRACES_DIR / f"{arch_name}__{question_id}.json"
        pending_trace_writes[trace_path] = json.dumps(trace.to_dict(), indent=2)

        old_faithfulness = old_rows_by_key[(arch_name, question_id)]["faithfulness"]
        row = eval_one(arch_name, question, trace, backend_calls)  # judge=None -> real re-judge
        rows_by_key[(arch_name, question_id)] = row
        print(
            f"refreshed {arch_name}::{question_id}: "
            f"faithfulness {old_faithfulness} -> {row['faithfulness']}"
        )

    # Every affected row succeeded -- commit trace files and eval.json together
    # so a crash partway through the loop above can never leave them
    # disagreeing about which rows are actually fixed.
    report = build_report(list(rows_by_key.values()))
    for trace_path, contents in pending_trace_writes.items():
        trace_path.write_text(contents)
    EVAL_PATH.write_text(json.dumps(report, indent=2))
    print(
        f"\nwrote {EVAL_PATH} "
        f"({len(affected)} rows refreshed, {len(rows_by_key) - len(affected)} unchanged)"
    )


if __name__ == "__main__":
    main()
