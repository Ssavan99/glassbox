"""Evaluation metrics: retrieval quality (recall@5, MRR@10, nDCG@10, and the
rank-insensitive recall_full) against gold_chunk_ids, plus LLM-judged
faithfulness and refusal correctness against gold_answer_points.

## LLM-judge caveat (read before trusting the faithfulness/refusal numbers)

`judge_answer()` calls `engine.llm.complete()` -- the same Groq/Ollama backend
that generated the answer being judged. A model judging its own (or a
same-family model's) output is a known weakness: it can be biased toward
rating its own phrasing favorably, and errors the generator is prone to are
exactly the errors the judge is least likely to catch. Treat faithfulness and
refusal_correctness as a directional signal, not a ground truth -- retrieval
metrics (recall/MRR/nDCG), which are computed deterministically against
`gold_chunk_ids` with no LLM involved, are the more trustworthy numbers in
this harness. This caveat is intentionally repeated in
`evaluation/run_eval.py`'s output and belongs in the Phase 11 README too.

## Rank-metrics caveat (Phase 6.1 -- read before trusting recall@5/MRR@10/nDCG@10
   for Graph, and partially for Agentic/Adaptive)

`recall_at_k`/`mrr_at_k`/`ndcg_at_k` all assume `retrieved` is a single
relevance-ordered list and score only its first `k` entries. That assumption
holds for Naive/Hybrid/HyDE/Corrective, whose `retrieve_dense`/
`retrieve_sparse`/`rerank` nodes really do rank by query relevance. It does
NOT hold for Graph: `engine/graph_index.py`'s `expand_hops` orders the chunks
it returns by entity *degree* (a global structural property of the graph,
computed identically regardless of the question), not by relevance to the
query, and then hands up to `GRAPH_MAX_HOP_CHUNKS` (40) of them to `generate`
unranked. Truncating that degree-ordered list to `k=5` for `recall_at_5`
measures an arbitrary truncation, not retrieval quality -- it is not a sign
Graph's generation starves for context (`generate` sees the full up-to-40
gathered set, never the truncated one), it is a metrics artifact. The same
issue partially affects Agentic (whenever a sub-question routes to the graph
tool) and Adaptive (whenever it delegates to Graph, or to an Agentic run that
used the graph tool for a sub-question), since their final aggregated chunk
lists -- built by concatenating each sub-question/delegate's last retrieval
attempt -- are not cross-branch relevance-ranked either.

`recall_full()` below is the rank-insensitive companion metric this motivates:
it checks whether each gold chunk appears *anywhere* in the retrieved set,
with no `k` cutoff, so an unranked or degree-ordered set can still score
fairly. `graph_tool_involved()` flags which rows the caveat actually applies
to. Use `recall_full` (not `recall_at_5`/`mrr_at_10`/`ndcg_at_10`) as the
trustworthy retrieval-quality number for Graph rows, and for Agentic/Adaptive
rows where `graph_tool_involved` is true. This caveat is repeated in
`evaluation/run_eval.py`'s output and belongs in the Phase 11 README too.
"""

from __future__ import annotations

import math

from engine.llm import complete, safe_json_dict
from engine.trace import Node, Trace

RETRIEVAL_KINDS = {"retrieve_dense", "retrieve_sparse", "graph_expand", "rerank"}


def extract_retrieved_chunk_ids(trace: Trace) -> list[str]:
    """The chunk ids that actually fed the trace's final answer, in ranked
    order, deduped.

    Walks backward from the trace's final `generate` node through
    `parent_ids`. As soon as a retrieval-bearing node is found along a given
    branch, its chunk ids are taken and that branch stops (its own ancestors
    are an earlier, superseded retrieval attempt -- e.g. Corrective's
    discarded first attempt, or Agentic's discarded first attempt for a
    sub-question -- and shouldn't count towards what the final answer
    actually used). `rerank`'s `after` list (not `before`) is used, since
    `after` is what's actually handed downstream to `generate`.

    `grade` nodes are NOT simply transparent: Corrective drops any chunk
    graded "incorrect" from what it actually hands to `generate` (falling
    back to the unfiltered set only if that would leave nothing -- see
    `engine/architectures/corrective.py`'s own `filtered_chunks` logic,
    which this mirrors exactly). Each walk branch tracks which chunk ids
    were marked "incorrect" by any `grade` node it passes through, and
    applies that same filter to whichever retrieval node it lands on
    upstream, so a chunk the architecture never actually showed the LLM
    doesn't get credited as "retrieved" here. Every other non-retrieval node
    kind (`reflect`, `route`, `graph_seed`, `fuse`, `embed_query`, `plan`,
    `rewrite`) is transparent and just keeps the walk going.

    This is schema-generic (works for all seven architectures, including
    Adaptive's spliced delegate trace) without any architecture-specific
    branching, since it only relies on the already-fixed §3.2 payload shapes.
    """
    if not trace.nodes:
        return []
    final = trace.nodes[-1]
    if final.kind != "generate":
        raise ValueError(
            f"{trace.trace_id}: expected the trace to end in a generate node, "
            f"got {final.kind!r} -- extract_retrieved_chunk_ids assumes this."
        )

    node_by_id: dict[str, Node] = {n.id: n for n in trace.nodes}
    chunk_ids: list[str] = []
    seen: set[str] = set()

    def _add(cid: str) -> None:
        if cid not in seen:
            seen.add(cid)
            chunk_ids.append(cid)

    def _apply_grade_filter(ids: list[str], graded_incorrect: frozenset[str]) -> list[str]:
        filtered = [cid for cid in ids if cid not in graded_incorrect]
        return filtered if filtered else ids  # same fallback rule corrective.py uses

    # Each frontier item carries the chunk ids graded "incorrect" by any
    # `grade` node already passed through on that branch, so the filter can
    # be applied once a retrieval node further upstream is reached.
    frontier: list[tuple[str, frozenset[str]]] = [
        (parent_id, frozenset()) for parent_id in final.parent_ids
    ]
    visited: set[tuple[str, frozenset[str]]] = set()

    while frontier:
        node_id, graded_incorrect = frontier.pop(0)
        key = (node_id, graded_incorrect)
        if key in visited:
            continue
        visited.add(key)
        node = node_by_id.get(node_id)
        if node is None:
            continue

        if node.kind == "grade":
            judgements = node.payload.get("judgements", [])
            newly_incorrect = {
                j["chunk_id"]
                for j in judgements
                if isinstance(j, dict) and j.get("verdict") == "incorrect"
            }
            frontier.extend(
                (parent_id, graded_incorrect | newly_incorrect) for parent_id in node.parent_ids
            )
            continue

        if node.kind == "rerank":
            ids = [r["chunk_id"] for r in node.payload.get("after", [])]
            for cid in _apply_grade_filter(ids, graded_incorrect):
                _add(cid)
            continue  # don't walk further back past a rerank
        if node.kind in ("retrieve_dense", "retrieve_sparse"):
            ids = [r["chunk_id"] for r in node.payload.get("results", [])]
            for cid in _apply_grade_filter(ids, graded_incorrect):
                _add(cid)
            continue
        if node.kind == "graph_expand":
            ids = list(node.payload.get("chunk_ids", []))
            for cid in _apply_grade_filter(ids, graded_incorrect):
                _add(cid)
            continue

        # Not a retrieval node -- keep walking backward through it.
        frontier.extend((parent_id, graded_incorrect) for parent_id in node.parent_ids)

    return chunk_ids


def recall_at_k(retrieved: list[str], gold: list[str], k: int = 5) -> float | None:
    """Fraction of gold chunks present in the top-k retrieved chunks.
    Returns None (undefined, not zero) when gold is empty -- e.g. an
    unanswerable question, where there's nothing to recall."""
    if not gold:
        return None
    top_k = set(retrieved[:k])
    gold_set = set(gold)
    return len(top_k & gold_set) / len(gold_set)


def mrr_at_k(retrieved: list[str], gold: list[str], k: int = 10) -> float | None:
    """1 / rank of the first gold chunk found within the top-k retrieved
    chunks (1-indexed), or 0.0 if none of the gold chunks appear in the top
    k. None (undefined) when gold is empty."""
    if not gold:
        return None
    gold_set = set(gold)
    for rank, chunk_id in enumerate(retrieved[:k], start=1):
        if chunk_id in gold_set:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: list[str], gold: list[str], k: int = 10) -> float | None:
    """Normalized Discounted Cumulative Gain at k, binary relevance (a
    retrieved chunk is either in `gold` or not). None (undefined) when gold
    is empty."""
    if not gold:
        return None
    gold_set = set(gold)

    dcg = 0.0
    for rank, chunk_id in enumerate(retrieved[:k], start=1):
        relevance = 1.0 if chunk_id in gold_set else 0.0
        if relevance:
            dcg += relevance / math.log2(rank + 1)

    ideal_hits = min(len(gold_set), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    if idcg == 0:
        return 0.0
    return dcg / idcg


def recall_full(retrieved: list[str], gold: list[str]) -> float | None:
    """Fraction of gold chunks present *anywhere* in `retrieved`, with no
    top-k cutoff. Rank-insensitive companion to `recall_at_k` -- see this
    module's docstring section on the rank-metrics caveat for why this
    exists alongside recall@5/MRR@10/nDCG@10 rather than replacing them:
    those three are still the right lens for architectures whose retrieval
    really is relevance-ranked, this one is the fair lens for Graph's
    degree-ordered set and Agentic/Adaptive's unranked aggregation. None
    (undefined, not zero) when gold is empty."""
    if not gold:
        return None
    return len(set(retrieved) & set(gold)) / len(set(gold))


def graph_tool_involved(trace: Trace) -> bool:
    """Whether this trace's execution used the Graph tool anywhere, i.e.
    contains at least one `graph_expand` node. True for every Graph
    architecture trace by construction; also true for an Agentic trace
    where at least one sub-question routed to the graph tool, and for an
    Adaptive trace that delegated to Graph (or to an Agentic run that used
    the graph tool) -- the spliced-in delegate nodes are walked the same
    way as any other node, so this needs no per-architecture branching.
    Used to flag which rows the rank-metrics caveat above actually applies
    to for Agentic/Adaptive specifically."""
    return any(n.kind == "graph_expand" for n in trace.nodes)


JUDGE_JSON_SCHEMA = {
    "point_support": [True, False],
    "reads_as_appropriate_refusal": True,
    "reasoning": "string",
}


def _build_judge_prompt(question: str, answer: str, gold_answer_points: list[str]) -> str:
    points_block = "\n".join(f"{i + 1}. {p}" for i, p in enumerate(gold_answer_points))
    return (
        "You are grading a RAG system's answer against a set of expected "
        "factual points, and separately judging whether the answer reads as "
        "an honest refusal (saying the information isn't available/covered) "
        "rather than a confidently fabricated answer.\n\n"
        f"Question: {question}\n\n"
        f"Answer under evaluation:\n{answer}\n\n"
        f"Expected points (in order):\n{points_block}\n\n"
        "For each expected point, judge whether the answer's content "
        "supports/is consistent with it (true) or not (false) -- return one "
        "boolean per point, in the same order, as `point_support`. "
        "Separately, in `reads_as_appropriate_refusal`, judge whether the "
        "answer reads like an honest 'I don't know / this isn't covered' "
        "response rather than a confident (possibly fabricated) answer -- "
        "this applies regardless of whether refusing was actually correct "
        "for this question."
    )


def judge_answer(question: str, answer: str, gold_answer_points: list[str]) -> dict:
    """Calls `engine.llm.complete()` to judge `answer` against
    `gold_answer_points`. Returns:
      - "faithfulness": float in [0,1], fraction of gold_answer_points the
        judge marked as supported, or None if gold_answer_points is empty.
      - "reads_as_refusal": bool, the judge's read on whether the answer is
        an honest refusal (relevant for refusal_correctness on unanswerable
        questions; ignored for other question types).
      - "reasoning": the judge's stated reasoning (str).
      - "backend": which backend (groq/ollama) served this judge call.
      - "prompt_tokens" / "completion_tokens": the judge call's own token
        usage (separate from the architecture run's own usage).

    See this module's docstring for the LLM-judge caveat -- this call goes
    through the same complete() backend as answer generation itself.
    """
    prompt = _build_judge_prompt(question, answer, gold_answer_points)
    result = complete(prompt, json_schema=JUDGE_JSON_SCHEMA)
    parsed = safe_json_dict(result)

    point_support = parsed.get("point_support")
    if not isinstance(point_support, list):
        point_support = []
    # Defensive: coerce to bool, tolerate a length mismatch from the model
    # by only scoring against however many points it actually judged, up to
    # the number of real gold_answer_points.
    point_support = [bool(x) for x in point_support][: len(gold_answer_points)]

    if not gold_answer_points:
        faithfulness = None
    elif not point_support:
        faithfulness = 0.0
    else:
        faithfulness = sum(point_support) / len(gold_answer_points)

    reads_as_refusal = parsed.get("reads_as_appropriate_refusal")
    if not isinstance(reads_as_refusal, bool):
        reads_as_refusal = False

    reasoning = parsed.get("reasoning", "")
    if not isinstance(reasoning, str):
        reasoning = ""

    return {
        "faithfulness": faithfulness,
        "reads_as_refusal": reads_as_refusal,
        "reasoning": reasoning,
        "backend": result.get("backend"),
        "prompt_tokens": result.get("prompt_tokens", 0),
        "completion_tokens": result.get("completion_tokens", 0),
    }


def refusal_correctness(is_unanswerable: bool, reads_as_refusal: bool) -> bool | None:
    """Whether the answer's refusal behavior was *correct* for this
    question: refusing on an unanswerable question is correct; refusing on
    an answerable one is not (a false refusal). None when the question is
    answerable and the answer didn't refuse (not a refusal-relevant case
    either way -- this metric is only meaningful for unanswerable questions
    per the plan's own framing, so answerable-question rows are excluded
    from aggregation in evaluation/run_eval.py rather than scored here)."""
    if not is_unanswerable:
        return None
    return reads_as_refusal
