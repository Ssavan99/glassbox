"""Run all 7 architectures over every question in evaluation/questions.yaml,
compute retrieval + LLM-judge metrics for each, and write artifacts/eval.json
with per-architecture and per-question-type breakdowns.

## LLM-judge caveat

`faithfulness` and `refusal_correctness` come from `evaluation.metrics.judge_answer()`,
which uses the SAME Groq/Ollama backend that generated the answer being judged.
A model judging its own (or a same-family model's) output is a known weakness.
Treat these two metrics as directional signal, not ground truth -- `recall_at_5`,
`mrr_at_10`, and `ndcg_at_10` are computed deterministically against
`gold_chunk_ids` with no LLM involved, and are the more trustworthy numbers
here. This exact caveat is repeated in the written `eval.json` itself (see
`LLM_JUDGE_CAVEAT` below) so it travels with the data, not just this docstring.
"""

from __future__ import annotations

import contextlib
import json
import sys
import time
from pathlib import Path
from statistics import mean
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from engine.architectures import adaptive as adaptive_mod
from engine.architectures import agentic as agentic_mod
from engine.architectures import corrective as corrective_mod
from engine.architectures import graph as graph_mod
from engine.architectures import hybrid as hybrid_mod
from engine.architectures import hyde as hyde_mod
from engine.architectures import naive as naive_mod
from engine.architectures.adaptive import AdaptiveArchitecture
from engine.architectures.agentic import AgenticArchitecture
from engine.architectures.base import Architecture
from engine.architectures.corrective import CorrectiveArchitecture
from engine.architectures.graph import GraphArchitecture
from engine.architectures.hybrid import HybridArchitecture
from engine.architectures.hyde import HyDEArchitecture
from engine.architectures.naive import NaiveArchitecture
from engine.config import EVAL_PATH, QUESTIONS_PATH
from engine.trace import Trace
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

ARCHITECTURES: dict[str, type[Architecture]] = {
    "naive": NaiveArchitecture,
    "hybrid": HybridArchitecture,
    "hyde": HyDEArchitecture,
    "corrective": CorrectiveArchitecture,
    "graph": GraphArchitecture,
    "agentic": AgenticArchitecture,
    "adaptive": AdaptiveArchitecture,
}

# The modules whose `complete` reference must be patched to observe every
# live/cached LLM call an architecture run makes -- each module did
# `from engine.llm import complete`, binding its own name, so patching
# engine.llm.complete after the fact wouldn't intercept calls made through
# these. Patching all 7 (not just the one being run) is what lets Adaptive's
# delegate calls (e.g. into naive_mod.complete) get captured too.
_ARCHITECTURE_MODULES = [
    naive_mod,
    hybrid_mod,
    hyde_mod,
    corrective_mod,
    graph_mod,
    agentic_mod,
    adaptive_mod,
]

# Adaptive's routing-accuracy rubric, per repo-plans/glassbox_PLAN.md's
# decision log (2026-08-29) -- kept in sync with that entry, not re-derived
# here. factual/multi_hop/keyword/unanswerable are the four question types
# in evaluation/questions.yaml.
ADAPTIVE_ROUTING_RUBRIC: dict[str, set[str]] = {
    "factual": {"naive", "hybrid"},
    "multi_hop": {"agentic", "graph"},
    "keyword": {"hybrid"},
    "unanswerable": {"naive", "hybrid", "corrective"},
}

LLM_JUDGE_CAVEAT = (
    "faithfulness and refusal_correctness are scored by an LLM judge running "
    "on the same Groq/Ollama backend that generated the answers being judged. "
    "A model judging its own (or a same-family model's) output is a known "
    "weakness -- it can be biased toward its own phrasing and blind to its "
    "own characteristic errors. Treat these two metrics as directional "
    "signal, not ground truth. recall_at_5, mrr_at_10, and ndcg_at_10 are "
    "computed deterministically against gold_chunk_ids with no LLM involved "
    "and are the more trustworthy numbers in this report."
)

RANK_METRICS_CAVEAT = (
    "recall_at_5, mrr_at_10, and ndcg_at_10 assume `retrieved_chunk_ids` is a "
    "single relevance-ranked list and score only its first k entries. That "
    "assumption does NOT hold for Graph: its retrieval is ordered by entity "
    "degree (a global structural property, not query relevance), so "
    "truncating it to k=5 measures an arbitrary cut, not retrieval quality -- "
    "this is a metrics artifact, not evidence that Graph's generation "
    "starves for context (generate sees the full gathered set, never the "
    "truncated one). The same issue partially affects Agentic/Adaptive rows "
    "where graph_tool_involved is true, since their aggregated chunk lists "
    "aren't cross-branch relevance-ranked either. Use recall_full (no k "
    "cutoff) as the trustworthy retrieval number for Graph rows and for "
    "Agentic/Adaptive rows with graph_tool_involved=true; see "
    "evaluation/metrics.py's module docstring for the full explanation."
)


def load_questions() -> list[dict]:
    return yaml.safe_load(QUESTIONS_PATH.read_text())


@contextlib.contextmanager
def _track_backends():
    """Patches every architecture module's `complete` reference to record
    which backend served each call made during the `with` block, without
    changing behavior otherwise -- each wrapper calls through to whatever
    `complete` was *already* bound on that module (the real
    engine.llm.complete in production use, but a test's own mock if one is
    already patched in), rather than reaching back to import the real
    complete() fresh. Reaching past an existing mock would silently make a
    real network call during what's meant to be a mocked test."""
    calls: list[str] = []

    def _make_tracking_wrapper(original):
        def _tracking_complete(*args, **kwargs):
            result = original(*args, **kwargs)
            calls.append(result.get("backend", "unknown"))
            return result

        return _tracking_complete

    with contextlib.ExitStack() as stack:
        for mod in _ARCHITECTURE_MODULES:
            original = mod.complete
            stack.enter_context(patch.object(mod, "complete", _make_tracking_wrapper(original)))
        yield calls


def run_one(arch_name: str, question: dict) -> tuple[Trace, list[str]]:
    """Runs one architecture on one question with an explicit, human-readable
    trace_id (f"{arch_name}::{question_id}", matching §3.2's own documented
    example) and returns (trace, backend_calls)."""
    arch_cls = ARCHITECTURES[arch_name]
    trace_id = f"{arch_name}::{question['id']}"
    with _track_backends() as calls:
        trace = arch_cls().run(question["question"], trace_id=trace_id)
    return trace, calls


def _adaptive_routed_to(trace: Trace) -> str | None:
    if not trace.nodes:
        return None
    route_node = trace.nodes[0]
    if route_node.kind != "route":
        return None
    chosen = route_node.payload.get("chosen")
    return chosen if isinstance(chosen, str) else None


def eval_one(
    arch_name: str,
    question: dict,
    trace: Trace,
    backend_calls: list[str],
    judge: dict | None = None,
) -> dict:
    """Computes one eval row for (arch_name, question, trace). `judge`
    defaults to a fresh `judge_answer()` LLM call (normal full-sweep use);
    pass an already-computed judge dict (matching judge_answer()'s return
    shape) to recompute a row's deterministic metrics -- recall_at_5,
    mrr_at_10, ndcg_at_10, recall_full, graph_tool_involved -- against an
    already-recorded trace with zero new LLM calls, as
    scripts/recompute_metrics.py does."""
    retrieved = extract_retrieved_chunk_ids(trace)
    gold_chunk_ids = question.get("gold_chunk_ids", [])
    gold_answer_points = question.get("gold_answer_points", [])
    is_unanswerable = question["type"] == "unanswerable"

    if judge is None:
        judge = judge_answer(question["question"], trace.answer, gold_answer_points)

    row = {
        "architecture": arch_name,
        "question_id": question["id"],
        "question_type": question["type"],
        "trace_id": trace.trace_id,
        "answer": trace.answer,
        "retrieved_chunk_ids": retrieved,
        "gold_chunk_ids": gold_chunk_ids,
        "recall_at_5": recall_at_k(retrieved, gold_chunk_ids, k=5),
        "mrr_at_10": mrr_at_k(retrieved, gold_chunk_ids, k=10),
        "ndcg_at_10": ndcg_at_k(retrieved, gold_chunk_ids, k=10),
        "recall_full": recall_full(retrieved, gold_chunk_ids),
        "graph_tool_involved": graph_tool_involved(trace),
        "faithfulness": judge["faithfulness"],
        "reads_as_refusal": judge["reads_as_refusal"],
        "refusal_correctness": refusal_correctness(is_unanswerable, judge["reads_as_refusal"]),
        "judge_reasoning": judge["reasoning"],
        "latency_ms": trace.metrics.latency_ms,
        "llm_calls": trace.metrics.llm_calls,
        "prompt_tokens": trace.metrics.prompt_tokens + judge["prompt_tokens"],
        "completion_tokens": trace.metrics.completion_tokens + judge["completion_tokens"],
        "backend_calls": backend_calls,  # one entry per real complete() call this run made
        "judge_backend": judge["backend"],
    }
    if arch_name == "adaptive":
        row["adaptive_routed_to"] = _adaptive_routed_to(trace)
    return row


def _mean_or_none(values: list) -> float | None:
    clean = [v for v in values if v is not None]
    return mean(clean) if clean else None


def _backend_mix(rows: list[dict]) -> dict[str, int]:
    mix: dict[str, int] = {}
    for row in rows:
        for backend in row["backend_calls"]:
            mix[backend] = mix.get(backend, 0) + 1
        mix[row["judge_backend"]] = mix.get(row["judge_backend"], 0) + 1
    return mix


def _rank_metrics_note(rows: list[dict]) -> str:
    """Per-summary explanation of whether recall_at_5/mrr_at_10/ndcg_at_10
    are trustworthy for this row set -- see RANK_METRICS_CAVEAT above and
    evaluation/metrics.py's module docstring for the full reasoning.

    Reads `rows[0]["architecture"]` to decide which branch applies -- every
    caller in this module (`_summarize`, via `by_architecture` and
    `by_architecture_and_type`) only ever passes a single-architecture row
    set, so this holds today, but it's not enforced here. A future caller
    that mixes architectures in one `rows` list would silently get the
    first row's architecture's note applied to the whole set."""
    if not rows:
        return "no rows"
    if rows[0]["architecture"] == "graph":
        return (
            "NOT meaningful -- Graph's retrieval is ordered by entity degree, not "
            "query relevance, so recall_at_5/mrr_at_10/ndcg_at_10 measure an "
            "arbitrary truncation. Use recall_full instead."
        )
    involved = sum(1 for r in rows if r.get("graph_tool_involved"))
    if involved == 0:
        return "reliable -- no graph-tool retrieval involved in this row set."
    return (
        f"reduced meaning for {involved}/{len(rows)} rows where a sub-question or "
        "delegation used the graph tool (same unranked-aggregation issue as Graph "
        "itself). Use recall_full for those rows (see the graph_tool_involved "
        "field on each row)."
    )


def _summarize(rows: list[dict]) -> dict:
    unanswerable_rows = [r for r in rows if r["question_type"] == "unanswerable"]
    return {
        "n_questions": len(rows),
        "recall_at_5_mean": _mean_or_none([r["recall_at_5"] for r in rows]),
        "mrr_at_10_mean": _mean_or_none([r["mrr_at_10"] for r in rows]),
        "ndcg_at_10_mean": _mean_or_none([r["ndcg_at_10"] for r in rows]),
        "recall_full_mean": _mean_or_none([r.get("recall_full") for r in rows]),
        "rank_metrics_note": _rank_metrics_note(rows),
        "faithfulness_mean": _mean_or_none([r["faithfulness"] for r in rows]),
        "refusal_correctness_rate": _mean_or_none(
            [1.0 if r["refusal_correctness"] else 0.0 for r in unanswerable_rows]
        ),
        "latency_ms_mean": _mean_or_none([r["latency_ms"] for r in rows]),
        "llm_calls_mean": _mean_or_none([r["llm_calls"] for r in rows]),
        "prompt_tokens_mean": _mean_or_none([r["prompt_tokens"] for r in rows]),
        "completion_tokens_mean": _mean_or_none([r["completion_tokens"] for r in rows]),
        "backend_mix": _backend_mix(rows),
    }


def build_report(rows: list[dict]) -> dict:
    architectures = sorted({r["architecture"] for r in rows})
    question_types = sorted({r["question_type"] for r in rows})

    by_architecture = {
        arch: _summarize([r for r in rows if r["architecture"] == arch]) for arch in architectures
    }
    by_architecture_and_type = {
        arch: {
            qtype: _summarize(
                [r for r in rows if r["architecture"] == arch and r["question_type"] == qtype]
            )
            for qtype in question_types
        }
        for arch in architectures
    }

    adaptive_rows = [r for r in rows if r["architecture"] == "adaptive"]
    adaptive_routing = [
        {
            "question_id": r["question_id"],
            "question_type": r["question_type"],
            "routed_to": r.get("adaptive_routed_to"),
            "correct": (
                r.get("adaptive_routed_to") in ADAPTIVE_ROUTING_RUBRIC[r["question_type"]]
                if r.get("adaptive_routed_to") is not None
                else None
            ),
        }
        for r in adaptive_rows
    ]
    routing_correct = [r["correct"] for r in adaptive_routing if r["correct"] is not None]
    adaptive_routing_accuracy = {
        "rubric": {qtype: sorted(archs) for qtype, archs in ADAPTIVE_ROUTING_RUBRIC.items()},
        "correct": sum(routing_correct),
        "total": len(routing_correct),
        "accuracy": (sum(routing_correct) / len(routing_correct)) if routing_correct else None,
    }

    return {
        "llm_judge_caveat": LLM_JUDGE_CAVEAT,
        "rank_metrics_caveat": RANK_METRICS_CAVEAT,
        "n_architectures": len(architectures),
        "n_questions": len(rows) // len(architectures) if architectures else 0,
        "rows": rows,
        "by_architecture": by_architecture,
        "by_architecture_and_type": by_architecture_and_type,
        "adaptive_routing": adaptive_routing,
        "adaptive_routing_accuracy": adaptive_routing_accuracy,
    }


def main() -> None:
    questions = load_questions()
    rows: list[dict] = []

    total = len(ARCHITECTURES) * len(questions)
    done = 0
    for arch_name in ARCHITECTURES:
        for question in questions:
            t0 = time.time()
            trace, backend_calls = run_one(arch_name, question)
            row = eval_one(arch_name, question, trace, backend_calls)
            rows.append(row)
            done += 1
            dt = time.time() - t0
            print(
                f"[{done}/{total}] {arch_name:10s} {question['id']:5s} "
                f"recall@5={row['recall_at_5']} recall_full={row['recall_full']} "
                f"faithfulness={row['faithfulness']} ({dt:.1f}s)",
                flush=True,
            )

    report = build_report(rows)
    EVAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVAL_PATH.write_text(json.dumps(report, indent=2))
    print(f"\nwrote: {EVAL_PATH}")
    print(f"rows: {len(rows)} ({len(ARCHITECTURES)} architectures x {len(questions)} questions)")


if __name__ == "__main__":
    main()
