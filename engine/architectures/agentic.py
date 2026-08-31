"""Agentic RAG: decompose the question into sub-questions -> for each,
route to a retrieval tool with a cheap heuristic -> retrieve -> reflect (an
actual LLM judgement) on whether the evidence is sufficient -> retry once
with a different tool if not -> generate a final answer from everything
gathered.

The "agentic" part is narrow and deliberate: the only genuine agent-style
decision in this pipeline is `reflect` (an LLM judging whether to spend a
second retrieval attempt). `route` looks like a decision but is a pure
heuristic — zero LLM cost — specifically so the LLM-call budget stays
*provably* bounded rather than merely usually-fine.

## Why the LLM-call budget is provably <= 8, never 9

- `plan`: exactly 1 call.
- Per sub-question: attempt 1 always runs (1 `reflect` call). Attempt 2 (the
  retry) runs *only if* attempt 1's `reflect` said insufficient, and there is
  structurally never a 3rd attempt regardless of attempt 2's outcome. So each
  sub-question spends at most 2 `reflect` calls.
- At most `AGENTIC_MAX_SUBQUESTIONS` (3) sub-questions x at most 2 attempts
  each = at most 6 attempts total, i.e. at most 6 `reflect` calls. This is
  also the "6 total steps" cap from the plan: one attempt (route + retrieve +
  reflect) counts as one step, not three.
- `generate`: exactly 1 call.

Worst case: 1 (plan) + 6 (reflect) + 1 (generate) = 8. Never 9 -- the cap of
9 in config.py is a ceiling with headroom, not a target this code tries to
hit. `route`, `retrieve_*`, `graph_seed`, and `graph_expand` are never LLM
calls in this design.

A running attempt counter is checked against `AGENTIC_MAX_STEPS` before
starting any new attempt as an explicit defensive belt-and-suspenders check
(this project's convention, established in corrective.py's termination
logic), even though the loop bounds above make that check structurally
unreachable.
"""

from __future__ import annotations

import re
import time

from engine.config import AGENTIC_MAX_STEPS, AGENTIC_MAX_SUBQUESTIONS, TOP_K
from engine.embedding import embed_texts
from engine.graph_index import expand_hops, load_graph, seed_entities
from engine.index import ChunkRecord, load_index
from engine.llm import complete, safe_json_dict
from engine.prompts import build_answer_prompt
from engine.trace import Metrics, Trace, TraceBuilder

from .base import Architecture

PLAN_JSON_SCHEMA = {"sub_questions": ["string", "..."]}
REFLECT_JSON_SCHEMA = {
    "sufficient": True,
    "reason": "string",
    "next_action": "proceed|retrieve_more",
}

_QUOTED_RE = re.compile(r"\"[^\"]+\"|'[^']+'")
_FLAG_RE = re.compile(r"--\w+")
_ACRONYM_RE = re.compile(r"\b[A-Z]{2,}\b")


def _build_plan_prompt(question: str) -> str:
    return (
        "Decompose the following question into at most "
        f"{AGENTIC_MAX_SUBQUESTIONS} sub-questions that together cover "
        "everything needed to answer it. If the question is already simple "
        "and doesn't need decomposition, return it as the single "
        "sub-question.\n\n"
        f"Question: {question}\n\n"
        "Return the sub-questions as a list, in the order they should be "
        "investigated."
    )


def _plan_sub_questions(question: str) -> tuple[list[str], dict]:
    prompt = _build_plan_prompt(question)
    result = complete(prompt, json_schema=PLAN_JSON_SCHEMA)
    parsed = safe_json_dict(result)
    sub_questions = parsed.get("sub_questions")
    if not isinstance(sub_questions, list) or not sub_questions:
        sub_questions = [question]
    sub_questions = [str(q) for q in sub_questions][:AGENTIC_MAX_SUBQUESTIONS]
    if not sub_questions:
        sub_questions = [question]
    return sub_questions, result


def _has_exact_token(sub_question: str) -> bool:
    return bool(
        _QUOTED_RE.search(sub_question)
        or _FLAG_RE.search(sub_question)
        or _ACRONYM_RE.search(sub_question)
    )


def _choose_tool(sub_question: str, graph) -> tuple[str, str]:
    """Heuristic (non-LLM) tool choice. Returns (tool, reason)."""
    seeds = seed_entities(sub_question, graph)
    if len(seeds) >= 1:
        return "graph", (
            f"heuristic: {len(seeds)} known entit"
            f"{'y' if len(seeds) == 1 else 'ies'} matched in the sub-question "
            "text, so graph traversal is likely to find directly connected "
            "evidence (this is a deterministic string-match rule, not an "
            "LLM judgment)"
        )
    if _has_exact_token(sub_question):
        return "sparse", (
            "heuristic: sub-question contains an exact-looking token (a "
            "quoted string, a --flag-style token, or an ALL-CAPS acronym) "
            "that keyword/BM25 search matches literally better than dense "
            "embedding similarity would (this is a deterministic regex "
            "rule, not an LLM judgment)"
        )
    return "dense", (
        "heuristic: no graph entities matched and no exact-looking token "
        "was found, so semantic similarity search is the default choice "
        "(this is a deterministic fallback rule, not an LLM judgment)"
    )


def _retry_tool(first_tool: str) -> str:
    """Deterministically pick a genuinely different tool for the retry.

    graph is never a valid retry choice regardless of first_tool: _choose_tool
    already tries graph first, ahead of every other rule, so if attempt 1
    wasn't graph it's because seed_entities() found zero matching entities --
    retrying with graph would deterministically find zero again. dense and
    sparse retry into each other (each is the other's clearest contrast);
    graph retries into sparse rather than dense, since if graph's relational
    context wasn't enough, exact keyword matching is a more genuinely
    different signal to try than falling back to the same dense-similarity
    default every time.
    """
    if first_tool == "dense":
        return "sparse"
    if first_tool == "sparse":
        return "dense"
    return "sparse"  # first_tool == "graph"


def _retrieve_dense(sub_question: str, index, route_node: str, builder: TraceBuilder):
    t0 = time.perf_counter()
    query_vector = embed_texts([sub_question])[0]
    embed_node = builder.node(
        "embed_query",
        "Embed sub-question for dense retrieval",
        parents=[route_node],
        explain=(
            "The sub-question is embedded so it can be compared against the "
            "corpus's dense vector store. Same embedding step every other "
            "dense-retrieval architecture in this project uses."
        ),
        duration_ms=(time.perf_counter() - t0) * 1000,
        dims=len(query_vector),
        preview=[float(x) for x in query_vector[:8]],
    )

    t1 = time.perf_counter()
    results = index.dense.search(query_vector, k=TOP_K)
    retrieve_node = builder.node(
        "retrieve_dense",
        f"Top-{TOP_K} dense retrieval",
        parents=[embed_node],
        explain=(
            "Standard top-k dense retrieval by cosine similarity, chosen by "
            "the route heuristic as the default tool when no graph entities "
            "or exact-looking tokens matched this sub-question."
        ),
        duration_ms=(time.perf_counter() - t1) * 1000,
        results=[
            {"chunk_id": chunk_id, "score": score, "rank": rank}
            for rank, (chunk_id, score) in enumerate(results, start=1)
        ],
        k=TOP_K,
    )
    chunk_ids = [chunk_id for chunk_id, _ in results]
    return chunk_ids, retrieve_node


def _retrieve_sparse(sub_question: str, index, route_node: str, builder: TraceBuilder):
    t0 = time.perf_counter()
    results = index.sparse.search(sub_question, k=TOP_K)
    retrieve_node = builder.node(
        "retrieve_sparse",
        f"Top-{TOP_K} sparse (BM25) retrieval",
        parents=[route_node],
        explain=(
            "Keyword/BM25 retrieval, chosen by the route heuristic because "
            "this sub-question contained an exact-looking token (a quoted "
            "string, a --flag, or an ALL-CAPS acronym) that literal keyword "
            "matching handles better than semantic similarity would."
        ),
        duration_ms=(time.perf_counter() - t0) * 1000,
        results=[
            {"chunk_id": chunk_id, "score": score, "rank": rank}
            for rank, (chunk_id, score) in enumerate(results, start=1)
        ],
        k=TOP_K,
    )
    chunk_ids = [chunk_id for chunk_id, _ in results]
    return chunk_ids, retrieve_node


def _retrieve_graph(sub_question: str, graph, index, route_node: str, builder: TraceBuilder):
    t0 = time.perf_counter()
    seeds = seed_entities(sub_question, graph)
    seed_node = builder.node(
        "graph_seed",
        f"Seed entities ({len(seeds)} matched)",
        parents=[route_node],
        explain=(
            "Entity mentions in the sub-question are matched against the "
            "pre-built knowledge graph's vocabulary. The route heuristic "
            "chose this tool because at least one entity matched here."
        ),
        duration_ms=(time.perf_counter() - t0) * 1000,
        entities=list(seeds),
    )

    t1 = time.perf_counter()
    raw_chunk_ids, edges = expand_hops(seeds, graph)
    # Resolve against the loaded index *before* building the node, and
    # record that same resolved list in the payload -- not expand_hops's
    # raw output -- so the trace can't claim a chunk_id was part of this
    # attempt's context when it wasn't actually looked up downstream.
    used_chunk_ids = [cid for cid in raw_chunk_ids if cid in index.chunk_by_id]
    expand_node = builder.node(
        "graph_expand",
        f"2-hop expansion ({len(used_chunk_ids)} chunks)",
        parents=[seed_node],
        explain=(
            "Two-hop traversal from the seed entities pulls in chunks "
            "connected to the sub-question's topic even when they share no "
            "textual or semantic similarity with it directly."
        ),
        duration_ms=(time.perf_counter() - t1) * 1000,
        hops=2,
        edges=[{"src": e.src, "rel": e.rel, "dst": e.dst} for e in edges],
        chunk_ids=used_chunk_ids,
    )
    return used_chunk_ids, expand_node


def _build_reflect_prompt(sub_question: str, chunks: list[ChunkRecord]) -> str:
    if chunks:
        excerpts = "\n\n".join(
            f"[{c.chunk_id}]: {c.text[:200]}" for c in chunks
        )
    else:
        excerpts = "(nothing was retrieved)"
    return (
        "You are judging whether the retrieved evidence below is sufficient "
        "to answer the sub-question. Consider whether the excerpts actually "
        "contain the facts needed, not just whether they're topically "
        "related.\n\n"
        f"Sub-question: {sub_question}\n\n"
        f"Retrieved evidence:\n{excerpts}\n\n"
        "Judge whether this is sufficient to answer the sub-question."
    )


def _reflect(sub_question: str, chunks: list[ChunkRecord]) -> tuple[dict, dict]:
    prompt = _build_reflect_prompt(sub_question, chunks)
    result = complete(prompt, json_schema=REFLECT_JSON_SCHEMA)
    parsed = safe_json_dict(result)
    sufficient = parsed.get("sufficient")
    if not isinstance(sufficient, bool):
        sufficient = False
    next_action = parsed.get("next_action")
    if next_action not in ("proceed", "retrieve_more"):
        next_action = "proceed" if sufficient else "retrieve_more"
    reason = parsed.get("reason", "")
    judgement = {"sufficient": sufficient, "reason": reason, "next_action": next_action}
    return judgement, result


class AgenticArchitecture(Architecture):
    name = "agentic"
    description = (
        "Decomposes the question into up to 3 sub-questions, and for each "
        "one routes to dense/sparse/graph retrieval with a zero-cost "
        "heuristic, then has an LLM reflect on whether the evidence is "
        "sufficient -- retrying once with a different tool if not -- before "
        "generating a final answer from everything gathered. The LLM-call "
        "budget is structurally bounded to at most 8 calls (1 plan + up to "
        "6 reflects + 1 generate), never 9."
    )

    # region: run
    def run(self, question: str, trace_id: str | None = None) -> Trace:
        start = time.perf_counter()
        index = load_index()
        graph = load_graph()
        builder = TraceBuilder(architecture=self.name, question=question, trace_id=trace_id)

        llm_calls = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0

        # --- Step 1: plan ---------------------------------------------------
        t0 = time.perf_counter()
        sub_questions, plan_result = _plan_sub_questions(question)
        llm_calls += 1
        total_prompt_tokens += plan_result["prompt_tokens"]
        total_completion_tokens += plan_result["completion_tokens"]
        plan_node = builder.node(
            "plan",
            f"Plan ({len(sub_questions)} sub-question(s))",
            parents=[],
            explain=(
                "The question is decomposed into up to "
                f"{AGENTIC_MAX_SUBQUESTIONS} sub-questions that together "
                "cover what's needed to answer it. If the LLM's response was "
                "malformed, empty, or not a list, this falls back to "
                "treating the original question as the sole sub-question "
                "rather than proceeding with zero sub-questions."
            ),
            duration_ms=(time.perf_counter() - t0) * 1000,
            sub_questions=sub_questions,
        )

        attempts_used = 0
        # For each sub-question, the chunks from its *last* attempt actually used.
        chunks_by_subquestion: list[list[ChunkRecord]] = []
        # Every sub-question's last node -- generate depends on all of them,
        # not just the final sub-question processed, since its answer draws
        # on chunks gathered from every branch.
        sub_question_last_nodes: list[str] = []

        for sub_question in sub_questions:
            attempt_first_tool = None
            sq_first_reflect_node = None
            sq_chunks: list[ChunkRecord] = []
            sq_last_node = plan_node

            for attempt_num in (1, 2):
                # Attempt 2 only runs when attempt 1's reflect said
                # insufficient -- gated by the `continue`/`break` at the
                # bottom of this loop body, not by a condition here.
                if attempts_used >= AGENTIC_MAX_STEPS:
                    # Defensive belt-and-suspenders check -- structurally
                    # unreachable given the loop bounds above, but required
                    # by this project's termination-check convention.
                    break
                attempts_used += 1

                # --- route (heuristic, 0 LLM calls) -------------------------
                t_route = time.perf_counter()
                if attempt_num == 1:
                    tool, reason = _choose_tool(sub_question, graph)
                    route_parent = plan_node
                else:
                    tool = _retry_tool(attempt_first_tool)
                    reason = (
                        "heuristic: retry attempt after attempt 1 was judged "
                        f"insufficient -- deterministically switching away "
                        f"from the first attempt's tool ({attempt_first_tool}) "
                        f"to {tool} rather than re-running the same search "
                        "(this is a deterministic rule, not an LLM judgment)"
                    )
                    route_parent = sq_first_reflect_node

                if attempt_num == 1:
                    attempt_first_tool = tool

                route_node = builder.node(
                    "route",
                    f"Route sub-question to {tool} (attempt {attempt_num})",
                    parents=[route_parent],
                    explain=(
                        "Tool choice is a cheap deterministic heuristic, not "
                        "an LLM judgment (unlike Adaptive's router) -- this "
                        "is what keeps the LLM-call budget provably bounded "
                        "while still doing three genuinely different kinds "
                        "of retrieval. " + reason
                    ),
                    duration_ms=(time.perf_counter() - t_route) * 1000,
                    chosen=tool,
                    scores={},
                    reason=reason,
                )

                # --- retrieve (0 LLM calls) ---------------------------------
                if tool == "dense":
                    chunk_ids, retrieve_node = _retrieve_dense(
                        sub_question, index, route_node, builder
                    )
                elif tool == "sparse":
                    chunk_ids, retrieve_node = _retrieve_sparse(
                        sub_question, index, route_node, builder
                    )
                else:
                    chunk_ids, retrieve_node = _retrieve_graph(
                        sub_question, graph, index, route_node, builder
                    )

                attempt_chunks = [
                    index.chunk_by_id[cid] for cid in chunk_ids if cid in index.chunk_by_id
                ]

                # --- reflect (1 LLM call) ------------------------------------
                t_reflect = time.perf_counter()
                judgement, reflect_result = _reflect(sub_question, attempt_chunks)
                llm_calls += 1
                total_prompt_tokens += reflect_result["prompt_tokens"]
                total_completion_tokens += reflect_result["completion_tokens"]
                reflect_node = builder.node(
                    "reflect",
                    f"Reflect on sufficiency (attempt {attempt_num})",
                    parents=[retrieve_node],
                    explain=(
                        "This is the actual 'agentic' judgment in this "
                        "architecture: a genuine LLM self-assessment of "
                        "whether the retrieved evidence is enough to answer "
                        "the sub-question, deciding whether a second "
                        "retrieval attempt (with a different tool) is worth "
                        "its cost. This is what separates Agentic from a "
                        "fixed pipeline -- every other decision in this run "
                        "is a zero-cost heuristic."
                    ),
                    duration_ms=(time.perf_counter() - t_reflect) * 1000,
                    **judgement,
                )

                sq_chunks = attempt_chunks
                sq_last_node = reflect_node
                if attempt_num == 1:
                    sq_first_reflect_node = reflect_node

                if attempt_num == 1 and not judgement["sufficient"]:
                    continue  # run the retry attempt
                break  # either sufficient, or this was already the retry

            chunks_by_subquestion.append(sq_chunks)
            sub_question_last_nodes.append(sq_last_node)

        # --- Step 3: generate -------------------------------------------------
        all_chunks: list[ChunkRecord] = []
        seen_ids: set[str] = set()
        for sq_chunks in chunks_by_subquestion:
            for chunk in sq_chunks:
                if chunk.chunk_id in seen_ids:
                    continue
                seen_ids.add(chunk.chunk_id)
                all_chunks.append(chunk)

        t_gen = time.perf_counter()
        answer_prompt = build_answer_prompt(question, all_chunks)
        answer_result = complete(answer_prompt)
        llm_calls += 1
        total_prompt_tokens += answer_result["prompt_tokens"]
        total_completion_tokens += answer_result["completion_tokens"]
        answer = answer_result["text"]

        builder.node(
            "generate",
            "Generate answer",
            parents=sub_question_last_nodes,
            explain=(
                "The final answer is generated from the *original* question "
                "(never a sub-question) using the deduplicated union of "
                "chunks gathered from each sub-question's last attempt -- "
                "attempt 2's results if a retry happened for that "
                "sub-question, otherwise attempt 1's. Parented on every "
                "sub-question's last node, not just the final one processed, "
                "since the answer draws on evidence from all of them."
            ),
            duration_ms=(time.perf_counter() - t_gen) * 1000,
            output=answer,
            prompt_preview=answer_prompt[:200],
            tokens=answer_result["prompt_tokens"] + answer_result["completion_tokens"],
        )

        latency_ms = (time.perf_counter() - start) * 1000
        metrics = Metrics(
            latency_ms=latency_ms,
            llm_calls=llm_calls,
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
        )
        return builder.build(answer=answer, metrics=metrics)
    # endregion
