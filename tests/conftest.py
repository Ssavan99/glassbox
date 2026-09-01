"""Shared pytest fixtures/markers.

`requires_live_llm_backend` skips a test when neither Groq nor a local
Ollama daemon is actually reachable. CI never sets `GROQ_API_KEY` by design
(see the Phase 0 decision log: CI only builds/tests, it never regenerates
traces) and has no local Ollama daemon, so the small number of tests that
make real, unmocked `engine.llm.complete()` calls (verifying genuine
end-to-end behavior against a live backend, not a mock) need to skip
gracefully there instead of failing with a raw `ConnectionError` -- this was
never exercised before because this repo's CI had never actually run until
Phase 7 pushed the branch to origin for the first time.
"""

from __future__ import annotations

import os
import socket

import pytest


def _ollama_reachable() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 11434), timeout=0.5):
            return True
    except OSError:
        return False


def live_backend_available() -> bool:
    return bool(os.environ.get("GROQ_API_KEY", "").strip()) or _ollama_reachable()


requires_live_llm_backend = pytest.mark.skipif(
    not live_backend_available(),
    reason="neither GROQ_API_KEY nor a local Ollama daemon is reachable",
)
