"""The Architecture ABC every RAG pipeline implements."""

from __future__ import annotations

from abc import ABC, abstractmethod

from engine.trace import Trace


class Architecture(ABC):
    name: str
    description: str

    @abstractmethod
    def run(self, question: str) -> Trace:
        """Run the pipeline on `question` and return a validated Trace."""
        raise NotImplementedError
