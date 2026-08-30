"""Corrective RAG (CRAG): retrieve -> grade each chunk -> if the retrieved
evidence is mostly bad, rewrite the query and re-retrieve (up to a cap) ->
generate.

Deviation from the original CRAG paper (plan decision D7, deliberate and
documented, not a bug): there is **no web-search fallback** here. When the
LLM judge decides retrieval came back mostly wrong, the only correction
available is rewriting the query and re-retrieving against the same local
corpus — never fetching new external evidence. That's an honest limitation
of this project, not an oversight.

Termination is guaranteed by a hard cap (`CORRECTIVE_MAX_CORRECTIONS`) on how
many times the query can be rewritten. Once the cap is hit, the pipeline
proceeds to generate with whatever was last retrieved, rather than looping
forever chasing evidence that may not exist (e.g. for a genuinely
unanswerable question).
"""

from __future__ import annotations

import time

from engine.config import CORRECTIVE_MAX_CORRECTIONS, TOP_K
from engine.embedding import embed_texts
from engine.index import ChunkRecord, load_index
from engine.llm import complete
from engine.prompts import build_answer_prompt
from engine.trace import Metrics, Trace, TraceBuilder

from .base import Architecture

GRADE_JSON_SCHEMA = {
    "judgements": [
        {"chunk_id": "string", "verdict": "correct|ambiguous|incorrect", "reason": "string"}
    ]
}
REWRITE_JSON_SCHEMA = {"to": "string", "reason": "string"}


def _build_grading_prompt(question: str, chunks: list[ChunkRecord]) -> str:
    parts = [
        "You are grading whether each retrieved chunk is relevant, correct "
        "evidence for answering the question below. For each chunk, decide "
        "one of: 'correct' (directly supports answering the question), "
        "'ambiguous' (topically related but not clearly sufficient on its "
        "own), or 'incorrect' (not actually relevant/useful evidence, even "
        "if it superficially resembles the question).",
        "",
        f"Question: {question}",
        "",
        "Chunks:",
    ]
    for chunk in chunks:
        parts.append(f"[{chunk.chunk_id}]\n{chunk.text}")
    return "\n\n".join(parts)


def _build_rewrite_prompt(query: str, incorrect_reasons: list[str]) -> str:
    reasons_block = "\n".join(f"- {r}" for r in incorrect_reasons) or "- (no reasons given)"
    return (
        "The following search query was used to retrieve evidence from a "
        "knowledge base, but grading judged most of what came back as "
        "irrelevant or incorrect. Propose a better search query that is more "
        "likely to retrieve relevant evidence. Note: there is no web search "
        "available here — the rewritten query will only be used to re-search "
        "the same local knowledge base, so focus on rephrasing/refining "
        "rather than assuming new sources will appear.\n\n"
        f"Current query: {query}\n\n"
        f"Reasons the retrieved evidence was judged incorrect:\n{reasons_block}\n\n"
        "Propose a rewritten query and briefly explain why it should retrieve better."
    )


def _grade_chunks(question: str, chunks: list[ChunkRecord]) -> tuple[list[dict], dict]:
    """Calls the LLM to grade `chunks`, defensively repairing the judgement
    list against retrieved chunk ids. Returns (judgements, raw_llm_result)."""
    prompt = _build_grading_prompt(question, chunks)
    result = complete(prompt, json_schema=GRADE_JSON_SCHEMA)

    retrieved_ids = [c.chunk_id for c in chunks]
    parsed = result.get("json")
    raw_judgements = parsed.get("judgements", []) if isinstance(parsed, dict) else []
    if not isinstance(raw_judgements, list):
        raw_judgements = []

    by_id: dict[str, dict] = {}
    for j in raw_judgements:
        if not isinstance(j, dict):
            continue
        cid = j.get("chunk_id")
        if cid not in retrieved_ids:
            continue  # drop phantom chunk_id not in the retrieved set
        verdict = j.get("verdict")
        if verdict not in ("correct", "ambiguous", "incorrect"):
            verdict = "ambiguous"
        by_id[cid] = {
            "chunk_id": cid,
            "verdict": verdict,
            "reason": j.get("reason", ""),
        }

    judgements = []
    for cid in retrieved_ids:
        if cid in by_id:
            judgements.append(by_id[cid])
        else:
            # missing judgement for a retrieved chunk -> default to ambiguous
            judgements.append({"chunk_id": cid, "verdict": "ambiguous", "reason": ""})

    return judgements, result


class CorrectiveArchitecture(Architecture):
    name = "corrective"
    description = (
        "Retrieves top-k chunks, has an LLM judge grade each one as "
        "correct/ambiguous/incorrect evidence, and — if the evidence is "
        "mostly bad — rewrites the query and re-retrieves (up to a cap) "
        "before generating. No web-search fallback: correction is limited "
        "to query rewrite + re-retrieval against the local corpus (D7)."
    )

    def run(self, question: str) -> Trace:
        start = time.perf_counter()
        index = load_index()
        builder = TraceBuilder(architecture=self.name, question=question)

        llm_calls = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0

        query = question
        parent_id: str | None = None
        corrections_used = 0
        retrieved_chunks: list[ChunkRecord] = []
        last_grade_node = None
        last_judgements: list[dict] = []

        attempt = 0
        while True:
            attempt += 1

            query_vector = embed_texts([query])[0]
            embed_node = builder.node(
                "embed_query",
                f"Embed query (attempt {attempt})",
                parents=[parent_id] if parent_id else [],
                explain=(
                    "The current search query (the original question on the "
                    "first attempt, or a rewritten query on a correction "
                    "attempt) is embedded for dense retrieval against the "
                    "corpus."
                ),
                dims=len(query_vector),
                preview=[float(x) for x in query_vector[:8]],
            )

            results = index.dense.search(query_vector, k=TOP_K)
            retrieve_node = builder.node(
                "retrieve_dense",
                f"Top-{TOP_K} dense retrieval (attempt {attempt})",
                parents=[embed_node],
                explain=(
                    "Standard top-k dense retrieval by cosine similarity. "
                    "Corrective RAG doesn't treat this result as final — it's "
                    "handed to a grading step next, which is what makes this "
                    "architecture 'corrective' rather than naive."
                ),
                results=[
                    {"chunk_id": chunk_id, "score": score, "rank": rank}
                    for rank, (chunk_id, score) in enumerate(results, start=1)
                ],
                k=TOP_K,
            )

            retrieved_chunks = [index.chunk_by_id[chunk_id] for chunk_id, _ in results]

            judgements, grade_result = _grade_chunks(question, retrieved_chunks)
            llm_calls += 1
            total_prompt_tokens += grade_result["prompt_tokens"]
            total_completion_tokens += grade_result["completion_tokens"]

            grade_node = builder.node(
                "grade",
                f"Grade retrieved chunks (attempt {attempt})",
                parents=[retrieve_node],
                explain=(
                    "Corrective RAG doesn't trust retrieval blindly — an LLM "
                    "judge checks whether each retrieved chunk actually "
                    "supports answering the question, since a semantically-"
                    "close chunk can still be topically wrong. This is the "
                    "step that decides whether to proceed to generation or "
                    "trigger a correction."
                ),
                judgements=judgements,
            )

            last_grade_node = grade_node
            last_judgements = judgements

            correct_count = sum(1 for j in judgements if j["verdict"] == "correct")
            incorrect_count = sum(1 for j in judgements if j["verdict"] == "incorrect")

            if incorrect_count <= correct_count:
                break  # sufficient evidence (also covers the all-correct case)

            if corrections_used >= CORRECTIVE_MAX_CORRECTIONS:
                break  # cap hit -- proceed to generate anyway (guarantees termination)

            incorrect_reasons = [
                j["reason"] for j in judgements if j["verdict"] == "incorrect" and j["reason"]
            ]
            rewrite_prompt = _build_rewrite_prompt(query, incorrect_reasons)
            rewrite_result = complete(rewrite_prompt, json_schema=REWRITE_JSON_SCHEMA)
            llm_calls += 1
            total_prompt_tokens += rewrite_result["prompt_tokens"]
            total_completion_tokens += rewrite_result["completion_tokens"]

            rewrite_json = rewrite_result.get("json")
            if not isinstance(rewrite_json, dict):
                rewrite_json = {}
            new_query = rewrite_json.get("to") or query
            reason = rewrite_json.get("reason", "")

            rewrite_node = builder.node(
                "rewrite",
                f"Rewrite query (correction {corrections_used + 1})",
                parents=[grade_node],
                explain=(
                    "Most retrieved chunks were graded incorrect, so the query "
                    "is rewritten and retrieval is retried. This project has "
                    "no web-search fallback (D7, deliberate deviation from the "
                    "CRAG paper) -- the only correction available is a better "
                    "search query against the same local corpus, not fetching "
                    "new external evidence. That's an honest, documented "
                    "limitation, not a bug."
                ),
                **{"from": query, "to": new_query, "reason": reason},
            )

            query = new_query
            parent_id = rewrite_node
            corrections_used += 1

        filtered_chunks = [
            c for c in retrieved_chunks
            if next(
                (j["verdict"] for j in last_judgements if j["chunk_id"] == c.chunk_id),
                "ambiguous",
            )
            != "incorrect"
        ]
        if not filtered_chunks:
            filtered_chunks = retrieved_chunks  # fall back to full unfiltered set

        answer_prompt = build_answer_prompt(question, filtered_chunks)
        answer_result = complete(answer_prompt)
        llm_calls += 1
        total_prompt_tokens += answer_result["prompt_tokens"]
        total_completion_tokens += answer_result["completion_tokens"]
        answer = answer_result["text"]

        builder.node(
            "generate",
            "Generate answer",
            parents=[last_grade_node],
            explain=(
                "The final answer is generated from the *original* question "
                "(never a rewritten query -- rewriting was only ever a "
                "retrieval aid) using whichever chunks survived grading: "
                "chunks graded 'incorrect' are dropped from context, and if "
                "that would leave nothing, the full last-retrieved set is "
                "used unfiltered rather than generating from empty context."
            ),
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
