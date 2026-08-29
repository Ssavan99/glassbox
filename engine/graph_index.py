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

from engine.config import GRAPH_PATH


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
    raw = json.loads(GRAPH_PATH.read_text())

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
