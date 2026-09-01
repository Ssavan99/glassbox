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
    "Each chunk in the Context section below begins with its own real id in square "
    "brackets. When you use a chunk, cite it by copying that exact bracketed id "
    "verbatim from that chunk's own label -- never invent an id, and never write a "
    "citation you have not copied from one of the chunk labels actually shown to you. "
    "If the context does not contain the answer, say so plainly instead of guessing."
)


def build_context_block(chunks: list[ChunkRecord]) -> str:
    """Format retrieved chunks into labeled blocks for stuffing into a prompt."""
    parts = []
    for chunk in chunks:
        heading = f" ({chunk.heading})" if chunk.heading else ""
        parts.append(f"[{chunk.chunk_id}]{heading}\n{chunk.text}")
    return "\n\n".join(parts)


def build_answer_prompt(
    question: str, chunks: list[ChunkRecord], extra_context: str | None = None
) -> str:
    """The shared "stuff the retrieved chunks and ask" prompt every
    architecture's final `generate` node uses.

    `extra_context` is optional supplementary context that isn't chunk-backed
    (e.g. Graph's community summaries) — it isn't citable by chunk id, so it's
    kept visually separate from the citable chunk context below it.
    """
    context = build_context_block(chunks)
    parts = [SYSTEM_PREAMBLE, ""]
    if extra_context:
        parts.append(f"Additional context (not individually citable):\n{extra_context}\n")
    parts.append(f"Context:\n{context}\n")
    parts.append(f"Question: {question}\n")
    parts.append("Answer, citing chunk ids as instructed:")
    return "\n".join(parts)


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
