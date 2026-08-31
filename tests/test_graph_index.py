import json

import pytest

import engine.graph_index as graph_index_mod
from engine.graph_index import Community, GraphData, GraphEdge, GraphEntity, expand_hops


@pytest.fixture(autouse=True)
def _clear_graph_cache():
    graph_index_mod.load_graph.cache_clear()
    yield
    graph_index_mod.load_graph.cache_clear()


def test_load_graph_missing_file_raises_actionable_error(tmp_path, monkeypatch):
    monkeypatch.setattr(graph_index_mod, "GRAPH_PATH", tmp_path / "graph.json")

    with pytest.raises(FileNotFoundError, match="python scripts/build_graph.py"):
        graph_index_mod.load_graph()


def test_load_graph_rejects_a_graph_from_a_different_retrieval_build(tmp_path, monkeypatch):
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(
        json.dumps({"build_id": "0" * 64, "entities": [], "edges": [], "communities": []})
    )
    monkeypatch.setattr(graph_index_mod, "GRAPH_PATH", graph_path)

    with pytest.raises(ValueError, match="Knowledge graph and retrieval index are out of sync"):
        graph_index_mod.load_graph()


def _make_tied_degree_graph() -> GraphData:
    """Three entities (b, a, c -- deliberately not alphabetically inserted)
    all tied at degree 1, each attached to a distinct single chunk. A
    max_chunks cap of 2 forces a tie-break between them."""
    entities = {
        "topic-b": GraphEntity(id="topic-b", chunk_ids=["note::0"], community=0),
        "topic-a": GraphEntity(id="topic-a", chunk_ids=["note::1"], community=0),
        "topic-c": GraphEntity(id="topic-c", chunk_ids=["note::2"], community=0),
        "seed": GraphEntity(id="seed", chunk_ids=[], community=0),
    }
    edges = [
        GraphEdge(src="seed", rel="relates to", dst="topic-b", chunk_id="note::0"),
        GraphEdge(src="seed", rel="relates to", dst="topic-a", chunk_id="note::1"),
        GraphEdge(src="seed", rel="relates to", dst="topic-c", chunk_id="note::2"),
    ]
    adjacency = {
        "seed": {"topic-b", "topic-a", "topic-c"},
        "topic-b": {"seed"},
        "topic-a": {"seed"},
        "topic-c": {"seed"},
    }
    communities = {0: Community(id=0, entity_ids=list(entities), summary="s")}
    return GraphData(entities=entities, edges=edges, communities=communities, adjacency=adjacency)


def test_expand_hops_tie_break_is_deterministic_regardless_of_call_order():
    graph = _make_tied_degree_graph()

    # topic-a/topic-b/topic-c are all tied at degree 1 (each only connects
    # to "seed"). With max_chunks=2, exactly one of them must be excluded --
    # which one must not depend on set iteration order. Run it many times;
    # a real bug here would show up as flaky results across repeated calls
    # in the same process (each call rebuilds `visited` as a fresh set).
    results = {
        tuple(expand_hops(["seed"], graph, hops=1, max_chunks=2)[0]) for _ in range(20)
    }
    assert len(results) == 1, f"expand_hops gave inconsistent tie-break results: {results}"

    # The secondary alphabetical tiebreaker means topic-a and topic-b (the
    # two alphabetically-first of the tied entities) should be the ones
    # kept, dropping topic-c.
    chunk_ids = list(next(iter(results)))
    assert chunk_ids == ["note::1", "note::0"]
