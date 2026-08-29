"""Prompt templates for each RAG architecture.

This is a placeholder — Phase 3+ fills in per-architecture prompt templates
(naive, hybrid, HyDE, corrective, graph, agentic, adaptive) as those
architectures are built. Everything here goes through `engine.llm.complete`.
"""

SYSTEM_PREAMBLE = (
    "You are a careful assistant answering from the provided context chunks only. "
    "Cite the chunk id(s) you used for each claim."
)
