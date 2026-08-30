"""Hybrid RAG: BM25 + dense retrieval in parallel -> reciprocal rank fusion
-> cross-encoder rerank -> generate.

Dense (cosine similarity) and sparse (BM25) retrieval each capture a
different notion of relevance: dense retrieval generalizes across paraphrase
and synonymy, while BM25 rewards exact term overlap and can catch a literal
keyword or identifier a dense embedding smooths over. Fusing their two
ranked lists with reciprocal rank fusion combines both signals without
having to reconcile their incomparable raw score scales, and a cross-encoder
rerank pass over the fused pool spends a more expensive, more accurate
scoring model only on the shortlist that survives fusion, rather than on the
whole corpus.
"""

from __future__ import annotations

import time
from collections import defaultdict

from engine.config import HYBRID_POOL_K, RERANK_MODEL, RRF_K, TOP_K
from engine.embedding import embed_texts
from engine.index import load_index
from engine.llm import complete
from engine.prompts import build_answer_prompt
from engine.rerank import rerank_scores
from engine.trace import Metrics, Trace, TraceBuilder

from .base import Architecture


def _ranked_payload(results: list[tuple[str, float]]) -> list[dict]:
    return [
        {"chunk_id": chunk_id, "score": score, "rank": rank}
        for rank, (chunk_id, score) in enumerate(results, start=1)
    ]


def reciprocal_rank_fusion(
    ranked_lists: list[list[tuple[str, float]]], k: int = RRF_K
) -> list[tuple[str, float]]:
    """Combine multiple ranked (chunk_id, score) lists into one fused ranking
    using reciprocal rank fusion: rrf_score(chunk) = sum(1 / (k + rank)) over
    every list the chunk appears in, rank being 1-indexed within that list.
    A chunk present in only one list still accumulates a nonzero score from
    that single term. Returns chunk_ids sorted descending by fused score."""
    fused: dict[str, float] = defaultdict(float)
    for ranked_list in ranked_lists:
        for rank, (chunk_id, _score) in enumerate(ranked_list, start=1):
            fused[chunk_id] += 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda pair: pair[1], reverse=True)


class HybridArchitecture(Architecture):
    name = "hybrid"
    description = (
        "BM25 and dense retrieval run in parallel, their ranked lists are "
        "combined with reciprocal rank fusion, the fused pool is re-scored "
        "by a cross-encoder, and the top-k survivors are used to generate "
        "the answer."
    )

    def run(self, question: str, trace_id: str | None = None) -> Trace:
        start = time.perf_counter()
        index = load_index()
        builder = TraceBuilder(architecture=self.name, question=question, trace_id=trace_id)

        query_vector = embed_texts([question])[0]
        n_embed = builder.node(
            "embed_query",
            "Embed the question",
            parents=[],
            explain=(
                "The question is embedded once up front so it can be compared "
                "against the corpus in vector space. Hybrid retrieval still "
                "needs this embedding for its dense branch, even though the "
                "sparse BM25 branch below works over raw tokens instead."
            ),
            dims=len(query_vector),
            preview=[float(x) for x in query_vector[:8]],
        )

        dense_results = index.dense.search(query_vector, k=HYBRID_POOL_K)
        n_dense = builder.node(
            "retrieve_dense",
            f"Top-{HYBRID_POOL_K} dense retrieval",
            parents=[n_embed],
            explain=(
                "Dense retrieval ranks chunks by cosine similarity in "
                "embedding space, which generalizes well across paraphrase "
                "and synonymy but can miss a chunk whose relevance hinges on "
                "an exact literal term, identifier, or number that the "
                "embedding model smooths over."
            ),
            results=_ranked_payload(dense_results),
            k=HYBRID_POOL_K,
        )

        sparse_results = index.sparse.search(question, k=HYBRID_POOL_K)
        n_sparse = builder.node(
            "retrieve_sparse",
            f"Top-{HYBRID_POOL_K} sparse (BM25) retrieval",
            parents=[n_embed],
            explain=(
                "BM25 ranks chunks by exact term overlap and term frequency, "
                "which is the mirror-image strength of dense retrieval: it "
                "reliably surfaces a chunk containing a literal keyword or "
                "identifier even when that chunk isn't semantically close to "
                "how the question happens to be phrased. It is structurally "
                "parented to the query embedding step here, even though it "
                "consumes the raw question text rather than the vector, "
                "because both retrieval branches fire off the same query."
            ),
            results=_ranked_payload(sparse_results),
            k=HYBRID_POOL_K,
        )

        fused = reciprocal_rank_fusion([dense_results, sparse_results], k=RRF_K)
        fused_pool = fused[:HYBRID_POOL_K]
        n_fuse = builder.node(
            "fuse",
            "Reciprocal rank fusion",
            parents=[n_dense, n_sparse],
            explain=(
                "RRF combines two independently-ranked lists without needing "
                "to normalize their raw score scales, since it only uses "
                "each result's rank position (1 / (RRF_K + rank)) — this is "
                "why a keyword-exact BM25 hit and a semantically-close dense "
                "hit can be merged fairly, and why a chunk found by only one "
                "branch still earns a nonzero fused score instead of being "
                "dropped."
            ),
            method="rrf",
            k=RRF_K,
            inputs=[n_dense, n_sparse],
            results=_ranked_payload(fused_pool),
        )

        fused_chunks = [index.chunk_by_id[chunk_id] for chunk_id, _ in fused_pool]
        scores = rerank_scores(question, [c.text for c in fused_chunks])
        rerank_order = sorted(
            zip(fused_chunks, scores, strict=True), key=lambda pair: pair[1], reverse=True
        )
        top_chunks = [chunk for chunk, _score in rerank_order[:TOP_K]]
        n_rerank = builder.node(
            "rerank",
            f"Cross-encoder rerank to top-{TOP_K}",
            parents=[n_fuse],
            explain=(
                "A cross-encoder scores the query and each candidate chunk "
                "together in one forward pass, letting the two attend to "
                "each other directly, which catches relevance a bi-encoder's "
                "separately-computed cosine similarity misses. The cost is "
                "one forward pass per candidate, which is why it only runs "
                "over the small fused pool rather than the whole corpus."
            ),
            model=RERANK_MODEL,
            before=_ranked_payload(fused_pool),
            after=[
                {"chunk_id": chunk.chunk_id, "score": score, "rank": rank}
                for rank, (chunk, score) in enumerate(rerank_order[:TOP_K], start=1)
            ],
        )

        prompt = build_answer_prompt(question, top_chunks)
        llm_result = complete(prompt)
        answer = llm_result["text"]
        tokens = llm_result["prompt_tokens"] + llm_result["completion_tokens"]
        builder.node(
            "generate",
            "Generate answer",
            parents=[n_rerank],
            explain=(
                "The reranked top-k chunks are stuffed into a single prompt "
                "and handed to the LLM. By this point the pipeline has "
                "already spent its retrieval effort on getting the best "
                "possible evidence set, so generation itself is a single "
                "one-shot call, same as naive RAG."
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
