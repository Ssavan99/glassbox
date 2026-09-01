"""The Architecture ABC every RAG pipeline implements."""

from __future__ import annotations

from abc import ABC, abstractmethod

from engine.trace import Trace


class Architecture(ABC):
    name: str
    description: str

    @abstractmethod
    def run(self, question: str, trace_id: str | None = None) -> Trace:
        """Run the pipeline on `question` and return a validated Trace.

        `trace_id` is passed straight through to `TraceBuilder`'s own
        `trace_id` parameter (unchanged since the Phase 2 schema freeze) --
        when omitted, `TraceBuilder.build()` falls back to its default
        `f"{architecture}::{sha256(question)[:10]}"`. Callers that need a
        stable, human-readable id (e.g. `scripts/record_traces.py`, which
        wants `"naive::q01"` rather than a hash) should pass one explicitly.
        """
        raise NotImplementedError
