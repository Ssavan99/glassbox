"""HyDE (Hypothetical Document Embeddings): draft a hypothetical answer ->
embed *that* -> dense retrieve -> generate.

The premise of HyDE is that a plausible answer sits closer in embedding
space to real answer-shaped passages than a bare question does. So instead
of embedding the question directly (as naive RAG does), this architecture
asks the LLM to draft a short hypothetical passage first, and embeds the
hypothetical passage for retrieval. The final generation step still grounds
itself in the original question against whatever got retrieved — the
hypothetical passage is only ever a retrieval aid, never shown to the user
and never used as context for the final answer.
"""

from __future__ import annotations

import time

from engine.config import TOP_K
from engine.embedding import embed_texts
from engine.index import load_index
from engine.llm import complete
from engine.prompts import build_answer_prompt, build_hyde_prompt
from engine.trace import Metrics, Trace, TraceBuilder

from .base import Architecture


class HyDEArchitecture(Architecture):
    name = "hyde"
    description = (
        "Drafts a hypothetical answer to the question with the LLM, embeds "
        "that hypothetical passage instead of the question, retrieves the "
        "top-k chunks against it, then generates the real answer from the "
        "original question and the retrieved chunks."
    )

    def run(self, question: str) -> Trace:
        start = time.perf_counter()
        index = load_index()
        builder = TraceBuilder(architecture=self.name, question=question)

        hyde_prompt = build_hyde_prompt(question)
        hyde_result = complete(hyde_prompt)
        hypothetical = hyde_result["text"]
        hyde_tokens = hyde_result["prompt_tokens"] + hyde_result["completion_tokens"]
        n1 = builder.node(
            "generate_hypothetical",
            "Draft hypothetical passage",
            parents=[],
            explain=(
                "HyDE drafts a fake answer first and embeds *that* instead of "
                "the question, because a plausible answer sits closer in "
                "embedding space to real answer-shaped passages than a "
                "question does — this can retrieve differently than embedding "
                "the question directly, for better or worse depending on how "
                "good the hypothetical draft is."
            ),
            output=hypothetical,
            prompt_preview=hyde_prompt[:200],
            tokens=hyde_tokens,
        )

        query_vector = embed_texts([hypothetical])[0]
        n2 = builder.node(
            "embed_query",
            "Embed the hypothetical passage",
            parents=[n1],
            explain=(
                "The hypothetical passage drafted in the previous step is what "
                "gets embedded here — not the original question. This is the "
                "entire mechanism HyDE relies on: retrieval happens in "
                "answer-shaped embedding space instead of question-shaped "
                "embedding space."
            ),
            dims=len(query_vector),
            preview=[float(x) for x in query_vector[:8]],
        )

        results = index.dense.search(query_vector, k=TOP_K)
        n3 = builder.node(
            "retrieve_dense",
            f"Top-{TOP_K} dense retrieval",
            parents=[n2],
            explain=(
                "The hypothetical passage's embedding is used to retrieve the "
                "top-k chunks by cosine similarity — so retrieval quality here "
                "depends entirely on how well the hypothetical passage's "
                "vocabulary and phrasing match real corpus passages."
            ),
            results=[
                {"chunk_id": chunk_id, "score": score, "rank": rank}
                for rank, (chunk_id, score) in enumerate(results, start=1)
            ],
            k=TOP_K,
        )

        retrieved_chunks = [index.chunk_by_id[chunk_id] for chunk_id, _ in results]
        answer_prompt = build_answer_prompt(question, retrieved_chunks)
        answer_result = complete(answer_prompt)
        answer = answer_result["text"]
        answer_tokens = answer_result["prompt_tokens"] + answer_result["completion_tokens"]
        builder.node(
            "generate",
            "Generate answer",
            parents=[n3],
            explain=(
                "The final answer is generated from the *original* question "
                "and the retrieved chunks — the hypothetical passage was only "
                "ever a retrieval aid and never becomes part of the grounding "
                "context handed to the LLM here."
            ),
            output=answer,
            prompt_preview=answer_prompt[:200],
            tokens=answer_tokens,
        )

        latency_ms = (time.perf_counter() - start) * 1000
        metrics = Metrics(
            latency_ms=latency_ms,
            llm_calls=2,
            prompt_tokens=hyde_result["prompt_tokens"] + answer_result["prompt_tokens"],
            completion_tokens=hyde_result["completion_tokens"] + answer_result["completion_tokens"],
        )
        return builder.build(answer=answer, metrics=metrics)
