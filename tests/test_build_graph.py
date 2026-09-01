"""Idempotency + acceptance checks for scripts/build_graph.py.

These tests run the real pipeline (real LLM calls, real disk cache under
engine.config.LLM_CACHE_DIR) once, then assert a second run is served
entirely from cache -- i.e. every prompt built by build_graph.py is fully
deterministic across runs.
"""

from __future__ import annotations

import json

import pytest

import engine.llm as llm
import scripts.build_graph as build_graph
from engine.config import GRAPH_PATH
from tests.conftest import live_backend_available


@pytest.fixture(scope="module")
def committed_graph_payload():
    """The versioned release artifact, independent of live backend availability."""
    return json.loads(GRAPH_PATH.read_text())


@pytest.fixture(scope="module")
def build_stats(committed_graph_payload):
    """Run the real build once for the whole module (expensive: ~140 LLM calls).

    A `pytest.mark.skipif` on a fixture doesn't propagate to skip the tests
    that use it (not officially supported by pytest) -- the fixture itself
    must call `pytest.skip()`, which does correctly skip every dependent
    test.
    """
    if not live_backend_available():
        pytest.skip("neither GROQ_API_KEY nor a local Ollama daemon is reachable")
    # The committed graph is the release artifact that must meet the project's
    # published >=150-edge / >=5-community acceptance bar. A clean local
    # Ollama rebuild exercises the same pipeline but can legitimately extract
    # a sparser graph than the Groq-built artifact, so keep the two claims
    # distinct instead of making the fallback path falsely fail its tests.
    try:
        yield build_graph.main()
    finally:
        # Tests exercise a live rebuild but must never leave its provider-specific
        # output in place of the tracked release artifact.
        GRAPH_PATH.write_text(json.dumps(committed_graph_payload, indent=2), encoding="utf-8")


def test_first_run_writes_graph_artifact(build_stats):
    assert GRAPH_PATH.exists()
    payload = json.loads(GRAPH_PATH.read_text())
    assert payload["entities"]
    assert payload["edges"]
    assert payload["communities"]


def test_second_run_is_fully_served_from_cache(build_stats):
    """Re-running build_graph.main() must not touch either live LLM backend."""

    def _explode(*args, **kwargs):
        raise AssertionError("live LLM backend was called on a supposedly cached re-run")

    import unittest.mock as mock

    with (
        mock.patch.object(llm, "_call_groq", side_effect=_explode),
        mock.patch.object(llm, "_call_ollama", side_effect=_explode),
    ):
        # Should complete without raising -- every call must be a cache hit.
        build_graph.main()


def test_live_graph_structure(build_stats):
    payload = json.loads(GRAPH_PATH.read_text())

    assert payload["entities"]
    assert payload["edges"]
    assert payload["communities"]

    for entity in payload["entities"]:
        assert entity["chunk_ids"], f"orphaned entity with no chunk_ids: {entity['id']}"

    entity_ids = {e["id"] for e in payload["entities"]}
    edge_touched_ids = {e["src"] for e in payload["edges"]} | {e["dst"] for e in payload["edges"]}
    # Every entity in the output must have real edges (no zero-degree entities).
    assert entity_ids == edge_touched_ids, "entities list contains ids with no edges, or vice versa"


def test_committed_graph_acceptance_shape(committed_graph_payload):
    payload = committed_graph_payload

    assert len(payload["edges"]) >= 150, f"expected >=150 edges, got {len(payload['edges'])}"
    assert len(payload["communities"]) >= 5, (
        f"expected >=5 communities, got {len(payload['communities'])}"
    )
