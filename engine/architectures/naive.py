"""Naive RAG: chunk -> embed -> cosine top-k -> stuff prompt -> generate.

This is the baseline every other architecture in the atlas is measured
against. It is intentionally the simplest thing that could work: one dense
retrieval pass with no reranking, no query rewriting, no fusion, and a single
LLM call to produce the final answer.
"""

from __future__ import annotations

import time

from engine.config import TOP_K
from engine.embedding import embed_texts
from engine.index import load_index
from engine.llm import complete
from engine.prompts import build_answer_prompt
from engine.trace import Metrics, Trace, TraceBuilder

from .base import Architecture


class NaiveArchitecture(Architecture):
    name = "naive"
    description = (
        "The baseline RAG pipeline: embed the question, take the top-k chunks "
        "by raw cosine similarity, stuff them into a prompt, and generate."
    )

    def run(self, question: str, trace_id: str | None = None) -> Trace:
        start = time.perf_counter()
        index = load_index()
        builder = TraceBuilder(architecture=self.name, question=question, trace_id=trace_id)

        query_vector = embed_texts([question])[0]
        n1 = builder.node(
            "embed_query",
            "Embed the question",
            parents=[],
            explain=(
                "The question is embedded once, up front, into the same vector "
                "space as the corpus chunks — naive RAG never rewrites or "
                "decomposes the query, so this single embedding is all the "
                "retrieval step has to work with."
            ),
            dims=len(query_vector),
            preview=[float(x) for x in query_vector[:8]],
        )

        results = index.dense.search(query_vector, k=TOP_K)
        n2 = builder.node(
            "retrieve_dense",
            f"Top-{TOP_K} dense retrieval",
            parents=[n1],
            explain=(
                "Naive RAG retrieves the top-k chunks by raw cosine similarity "
                "to the question — no reranking, no query rewriting, no fusion; "
                "this is the simplest possible retrieval step and everything "
                "else in the project is a deliberate improvement on it."
            ),
            results=[
                {"chunk_id": chunk_id, "score": score, "rank": rank}
                for rank, (chunk_id, score) in enumerate(results, start=1)
            ],
            k=TOP_K,
        )

        retrieved_chunks = [index.chunk_by_id[chunk_id] for chunk_id, _ in results]
        prompt = build_answer_prompt(question, retrieved_chunks)
        llm_result = complete(prompt)
        answer = llm_result["text"]
        tokens = llm_result["prompt_tokens"] + llm_result["completion_tokens"]
        builder.node(
            "generate",
            "Generate answer",
            parents=[n2],
            explain=(
                "The retrieved chunks are stuffed directly into a single prompt "
                "and handed to the LLM in one shot — naive RAG trusts that "
                "whatever the top-k retrieval found is sufficient context, with "
                "no verification or correction step before generating."
            ),
            output=answer,
            prompt_preview=prompt[:200],
            tokens=tokens,
        )

        latency_ms = (time.perf_counter() - start) * 1000
        metrics = Metrics(
            latency_ms=latency_ms,
            llm_calls=1,
            prompt_tokens=llm_result["prompt_tokens"],
            completion_tokens=llm_result["completion_tokens"],
        )
        return builder.build(answer=answer, metrics=metrics)
