"""Adaptive RAG: an LLM router classifies the question and delegates the
whole run to whichever of the other six architectures it judges fits best,
then that delegate's trace is spliced in as a nested subtree.

This is the one place in the whole project where an LLM -- not a heuristic
-- picks which *entire architecture* to run. Contrast this with Agentic's
`route` node: same node *kind* (`route`), completely different mechanism.
Agentic's `route` is a zero-cost deterministic heuristic (regex/entity
matching) that picks a retrieval *tool* for one sub-question, specifically
so its LLM-call budget stays provably bounded. Adaptive's `route` spends a
real LLM call to make a genuine judgment call about which whole *pipeline*
best suits the question -- there is no heuristic fallback for the choice
itself, only a safe-default fallback (`naive`) for when the LLM's answer is
unusable.
"""

from __future__ import annotations

import time

from engine.llm import complete, safe_json_dict
from engine.trace import Metrics, Trace, TraceBuilder

from .agentic import AgenticArchitecture
from .base import Architecture
from .corrective import CorrectiveArchitecture
from .graph import GraphArchitecture
from .hybrid import HybridArchitecture
from .hyde import HyDEArchitecture
from .naive import NaiveArchitecture

_ARCHITECTURES: dict[str, type[Architecture]] = {
    "naive": NaiveArchitecture,
    "hybrid": HybridArchitecture,
    "hyde": HyDEArchitecture,
    "corrective": CorrectiveArchitecture,
    "graph": GraphArchitecture,
    "agentic": AgenticArchitecture,
}

_FALLBACK_CHOICE = "naive"

ROUTE_JSON_SCHEMA = {
    "chosen": "string",
    "scores": {
        "naive": 0.0,
        "hybrid": 0.0,
        "hyde": 0.0,
        "corrective": 0.0,
        "graph": 0.0,
        "agentic": 0.0,
    },
    "reason": "string",
}


def _build_route_prompt(question: str) -> str:
    return (
        "You are routing a question to exactly one of six RAG architectures "
        "based on which one is best suited to answer it well:\n\n"
        "- naive: a single dense-retrieval pass, no reranking or rewriting. "
        "Best for simple, direct factual questions that ask for one concept "
        "or one piece of general understanding -- even about a technical "
        "subject, as long as only a single fact is needed.\n"
        "- hybrid: dense + BM25 retrieval fused and reranked. Best whenever "
        "the question is asking to recall a precise, verbatim detail -- an "
        "exact config value, flag, constant name, model identifier, error "
        "message, status code, or similarly specific string. Watch for "
        "phrases like 'what is the exact...', 'exact wording', 'named "
        "constant', or 'identifier string' -- these signal that the *answer* "
        "is an exact term even when the *question itself* is phrased in "
        "plain language and doesn't repeat that term. This case is easy to "
        "under-route to naive; don't.\n"
        "- hyde: generates a hypothetical answer first and retrieves using "
        "that. Best for questions phrased very differently from how the "
        "answer would be phrased in the corpus.\n"
        "- corrective: retrieves, grades the retrieved chunks for "
        "relevance, and rewrites the query and retries if the chunks are "
        "graded poor. Best for questions where retrieval might easily miss "
        "or where the question might be unanswerable from the corpus.\n"
        "- graph: seeds entities from the question and expands over a "
        "knowledge graph. Best for questions about relationships between "
        "named entities/concepts.\n"
        "- agentic: decomposes the question into sub-questions and routes "
        "each to the best tool, reflecting on sufficiency. Reserve this for "
        "questions that genuinely require combining multiple independent "
        "pieces of evidence to answer -- not just because the subject "
        "matter sounds technical or advanced. A single-fact question about "
        "a complex topic is still naive/hybrid territory, not agentic.\n\n"
        f"Question: {question}\n\n"
        "Choose exactly one architecture name from "
        f"{sorted(_ARCHITECTURES)} as `chosen`, give a 0-1 confidence score "
        "for every one of the six options in `scores` (not just the chosen "
        "one), and give a short `reason` for your choice."
    )


def _route(question: str) -> tuple[str, dict, dict]:
    """Returns (chosen_architecture_name, judgement_payload, llm_result)."""
    prompt = _build_route_prompt(question)
    result = complete(prompt, json_schema=ROUTE_JSON_SCHEMA)
    parsed = safe_json_dict(result)

    chosen = parsed.get("chosen")
    scores = parsed.get("scores")
    reason = parsed.get("reason")

    if not isinstance(scores, dict):
        scores = {}
    if not isinstance(reason, str):
        reason = ""

    if not isinstance(chosen, str) or chosen not in _ARCHITECTURES:
        reason = (
            f"{reason} (fell back to naive: router returned an "
            "invalid/missing choice)"
        ).strip()
        chosen = _FALLBACK_CHOICE

    judgement = {"chosen": chosen, "scores": scores, "reason": reason}
    return chosen, judgement, result


class AdaptiveArchitecture(Architecture):
    name = "adaptive"
    description = (
        "An LLM router classifies the question and delegates the entire "
        "run to whichever of the other six architectures it judges fits "
        "best, then splices that delegate's trace in as a nested subtree "
        "under the routing decision. The only place in the project where "
        "an LLM (not a heuristic) picks which whole architecture to run."
    )

    def run(self, question: str, trace_id: str | None = None) -> Trace:
        start = time.perf_counter()
        builder = TraceBuilder(architecture=self.name, question=question, trace_id=trace_id)

        t0 = time.perf_counter()
        chosen, judgement, route_result = _route(question)
        route_duration_ms = (time.perf_counter() - t0) * 1000

        route_node = builder.node(
            "route",
            f"Route question to {chosen}",
            parents=[],
            explain=(
                "This is the one genuinely LLM-driven routing decision in "
                "the whole project: the LLM classifies the question and "
                "picks which entire architecture -- not which retrieval "
                "tool -- is best suited to answer it, weighing tradeoffs "
                "like keyword-sensitivity, multi-hop complexity, or "
                "likely-unanswerability. Contrast this with Agentic's "
                "`route` node, which shares this node kind but is a "
                "zero-cost deterministic heuristic picking a retrieval tool "
                "for one sub-question, not an LLM judgment picking a "
                "pipeline. If the router's response was malformed, missing, "
                "or named an architecture that doesn't exist, this falls "
                "back to naive as the safe default rather than crashing or "
                "guessing."
            ),
            duration_ms=route_duration_ms,
            **judgement,
        )

        delegate = _ARCHITECTURES[chosen]()
        delegated_trace = delegate.run(question)

        builder.splice(delegated_trace.nodes, prefix=chosen, parent_id=route_node)

        answer = delegated_trace.answer

        latency_ms = (time.perf_counter() - start) * 1000
        metrics = Metrics(
            latency_ms=latency_ms,
            llm_calls=1 + delegated_trace.metrics.llm_calls,
            prompt_tokens=route_result["prompt_tokens"]
            + delegated_trace.metrics.prompt_tokens,
            completion_tokens=route_result["completion_tokens"]
            + delegated_trace.metrics.completion_tokens,
        )
        return builder.build(answer=answer, metrics=metrics)
