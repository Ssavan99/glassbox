"""Shared prompt templates for the RAG architectures.

Everything here goes through `engine.llm.complete`. Kept on the main thread
(not delegated) since every architecture in Phase 3+ builds its answer prompt
the same way — a single shared template keeps that consistent instead of each
architecture inventing its own citation convention.
"""

from __future__ import annotations

from engine.index import ChunkRecord

SYSTEM_PREAMBLE = (
    "You are a careful assistant answering from the provided context chunks only. "
    "Cite the chunk id(s) you used for each claim, in square brackets, e.g. [chunk-id::0]. "
    "If the context does not contain the answer, say so plainly instead of guessing."
)


def build_context_block(chunks: list[ChunkRecord]) -> str:
    """Format retrieved chunks into labeled blocks for stuffing into a prompt."""
    parts = []
    for chunk in chunks:
        heading = f" ({chunk.heading})" if chunk.heading else ""
        parts.append(f"[{chunk.chunk_id}]{heading}\n{chunk.text}")
    return "\n\n".join(parts)


def build_answer_prompt(question: str, chunks: list[ChunkRecord]) -> str:
    """The shared "stuff the retrieved chunks and ask" prompt every
    architecture's final `generate` node uses."""
    context = build_context_block(chunks)
    return (
        f"{SYSTEM_PREAMBLE}\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer, citing chunk ids as instructed:"
    )


def build_hyde_prompt(question: str) -> str:
    """HyDE's first step: draft a hypothetical answer to embed instead of the
    raw question, since answer-shaped text sits closer to answer-shaped
    passages in embedding space than a question does."""
    return (
        "Write a short, plausible-sounding passage (2-4 sentences) that would "
        "answer the following question, as if it were an excerpt from a "
        "technical knowledge base. It does not need to be factually verified — "
        "it exists only to be embedded and used for retrieval, not shown to the "
        "user.\n\n"
        f"Question: {question}\n\n"
        "Hypothetical passage:"
    )
