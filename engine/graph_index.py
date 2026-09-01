"""Schema contract and runtime loader for artifacts/graph.json.

This is the boundary between scripts/build_graph.py (which extracts triples
offline and writes the artifact) and engine/architectures/graph.py (which
reads it at query time) — the two are decoupled through this JSON schema
rather than sharing Python code, mirroring how scripts/build_index.py and
engine/index.py relate for chunks/vectors.

## artifacts/graph.json schema

    {
      "entities": [
        {"id": "chunking", "chunk_ids": ["note::0", ...], "community": 2}
      ],
      "edges": [
        {"src": "chunking", "rel": "affects", "dst": "recall", "chunk_id": "note::0"}
      ],
      "communities": [
        {"id": 2, "entity_ids": ["chunking", "chunk overlap"], "summary": "..."}
      ]
    }

`entity.id` and edge `src`/`dst` are normalized entity strings (see
`normalize_entity`). An entity with no edges (degree 0) must not appear in
the "entities" list — it's useless for 2-hop traversal and would fail the
"no orphan entities" acceptance check, so scripts/build_graph.py filters
those out before writing rather than this loader having to cope with them.
`edge.chunk_id` is the chunk the triple was extracted from (evidence).
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache

from engine.artifacts import ArtifactIntegrityError, read_chunks_artifact
from engine.config import CHUNKS_PATH, GRAPH_MAX_HOP_CHUNKS, GRAPH_PATH
from engine.index import load_index


def normalize_entity(name: str) -> str:
    """Lowercase, trim, and collapse internal whitespace. Corpus frontmatter
    entities are already written in this canonical form (see
    corpus/README.md's design contract) — this exists mainly to defend
    against LLM-extracted entity strings varying in casing/whitespace so
    they still match the corpus vocabulary they were constrained to."""
    return re.sub(r"\s+", " ", name.strip().lower())


@dataclass
class GraphEntity:
    id: str
    chunk_ids: list[str]
    community: int | None


@dataclass
class GraphEdge:
    src: str
    rel: str
    dst: str
    chunk_id: str


@dataclass
class Community:
    id: int
    entity_ids: list[str]
    summary: str


@dataclass
class GraphData:
    entities: dict[str, GraphEntity]
    edges: list[GraphEdge]
    communities: dict[int, Community]
    adjacency: dict[str, set[str]]  # entity id -> neighbor entity ids, both directions


@lru_cache(maxsize=1)
def load_graph() -> GraphData:
    if not GRAPH_PATH.exists():
        raise FileNotFoundError(
            f"Knowledge graph not built: {GRAPH_PATH} doesn't exist. "
            "Run this first: python scripts/build_graph.py"
        )

    raw = json.loads(GRAPH_PATH.read_text())
    graph_build_id = raw.get("build_id") if isinstance(raw, dict) else None
    if not isinstance(graph_build_id, str):
        raise ArtifactIntegrityError(
            f"{GRAPH_PATH} is missing its retrieval build id; rebuild with "
            "python scripts/build_graph.py"
        )
    # Loading the index checks chunks/vectors/bm25 against one another before
    # the graph can hand any of its chunk ids to the retrieval layer.
    index_build_id, _ = read_chunks_artifact(CHUNKS_PATH)
    load_index()
    if graph_build_id != index_build_id:
        raise ArtifactIntegrityError(
            "Knowledge graph and retrieval index are out of sync: graph.json and chunks.json "
            "have different build ids. Rebuild with python scripts/build_index.py and "
            "python scripts/build_graph.py"
        )

    entities = {
        e["id"]: GraphEntity(
            id=e["id"], chunk_ids=list(e["chunk_ids"]), community=e.get("community")
        )
        for e in raw["entities"]
    }
    edges = [
        GraphEdge(src=e["src"], rel=e["rel"], dst=e["dst"], chunk_id=e["chunk_id"])
        for e in raw["edges"]
    ]
    communities = {
        c["id"]: Community(id=c["id"], entity_ids=list(c["entity_ids"]), summary=c["summary"])
        for c in raw["communities"]
    }

    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        adjacency[edge.src].add(edge.dst)
        adjacency[edge.dst].add(edge.src)

    return GraphData(
        entities=entities, edges=edges, communities=communities, adjacency=dict(adjacency)
    )


def seed_entities(query: str, graph: GraphData) -> list[str]:
    """Heuristic (non-LLM) entity matching: find which known entities are
    mentioned in the query text. Must stay non-LLM — the Graph architecture's
    online budget is exactly one LLM call (the final generate), per §3.3.

    Candidates are checked longest-first, but this returns every matching
    entity rather than only the longest — a query containing "embedding
    dimension" also matches the shorter entity "embedding" if that's a
    separate vocabulary entry, since a broader seed set is harmless here
    (expand_hops's degree-based capping tolerates it fine). The
    longest-first order only matters for readability of the returned list,
    not exclusivity. Matching is word-boundary-aware so e.g. the entity
    "trace" doesn't spuriously match inside an unrelated word, and spaces
    and hyphens are treated as equivalent word separators on both sides, so
    a spaced entity ("needle in a haystack") still matches a hyphenated
    mention in the query ("needle-in-a-haystack") and vice versa.
    """
    query_lower = query.lower()
    candidates = sorted(graph.entities.keys(), key=len, reverse=True)
    matched = []
    for entity_id in candidates:
        parts = re.split(r"[\s-]+", entity_id)
        pattern = r"\b" + r"[\s-]+".join(re.escape(p) for p in parts) + r"\b"
        if re.search(pattern, query_lower):
            matched.append(entity_id)
    return matched


def expand_hops(
    seed_ids: list[str],
    graph: GraphData,
    hops: int = 2,
    max_chunks: int = GRAPH_MAX_HOP_CHUNKS,
) -> tuple[list[str], list[GraphEdge]]:
    """BFS outward from the seed entities up to `hops` steps, returning the
    chunk ids to use as retrieved context (capped at `max_chunks`, preferring
    chunks belonging to higher-degree/higher-centrality entities when
    truncation is needed) and the subgraph edges connecting visited entities
    (for the graph_expand node's payload)."""
    visited = set(seed_ids)
    frontier = set(seed_ids)
    for _ in range(hops):
        next_frontier: set[str] = set()
        for entity_id in frontier:
            next_frontier |= graph.adjacency.get(entity_id, set())
        next_frontier -= visited
        if not next_frontier:
            break
        visited |= next_frontier
        frontier = next_frontier

    edges_used = [e for e in graph.edges if e.src in visited and e.dst in visited]

    degree = {entity_id: len(graph.adjacency.get(entity_id, ())) for entity_id in visited}
    # Secondary sort key (entity_id, alphabetical) is required, not
    # cosmetic: `sorted()` is stable, so without it, ties on degree (common
    # in this graph) fall back to `visited`'s set iteration order, which
    # CPython randomizes per-process -- making which chunks survive the
    # max_chunks truncation nondeterministic across separate runs of the
    # identical question against the identical graph.
    ordered_entities = sorted(visited, key=lambda e: (-degree.get(e, 0), e))

    chunk_ids: list[str] = []
    seen_chunks: set[str] = set()
    for entity_id in ordered_entities:
        entity = graph.entities.get(entity_id)
        if entity is None:
            continue
        for chunk_id in entity.chunk_ids:
            if chunk_id in seen_chunks:
                continue
            seen_chunks.add(chunk_id)
            chunk_ids.append(chunk_id)
            if len(chunk_ids) >= max_chunks:
                return chunk_ids, edges_used

    return chunk_ids, edges_used
