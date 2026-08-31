"""Build the knowledge graph artifact (artifacts/graph.json) from the corpus + chunks.

Pipeline:
  1. Build a deterministic, sorted entity vocabulary from every note's hand-curated
     `entities` frontmatter (via engine.corpus.load_corpus + normalize_entity).
  2. For each chunk (artifacts/chunks.json, sorted by chunk_id), ask the LLM to extract
     (subject, relation, object) triples constrained to that vocabulary, and defensively
     drop any triple whose normalized subject/object isn't actually in the vocabulary.
  3. Project the accepted triples into an undirected networkx.Graph, run Louvain
     community detection, and ask the LLM for a short grounded summary of each community.
  4. Write artifacts/graph.json matching the schema documented in engine/graph_index.py
     (entities, edges, communities) -- entities with zero accepted edges are excluded.

This is the expensive step of Phase 4: one triple-extraction LLM call per chunk (127
chunks) plus one summary call per community. engine.llm.complete() disk-caches by
sha256(backend+model+prompt+params), so as long as every prompt built here is fully
deterministic (sorted vocabulary, sorted chunk order, sorted community entity lists,
no randomness/timestamps in prompt text) a second run is served entirely from cache.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

# Ensure the repo root is importable when this script is invoked directly
# (e.g. `python scripts/build_graph.py`) regardless of how the environment's
# editable install resolves sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import community as community_louvain
import networkx as nx

from engine.artifacts import read_chunks_artifact
from engine.config import CHUNKS_PATH, CORPUS_DIR, GRAPH_PATH
from engine.corpus import load_corpus
from engine.graph_index import normalize_entity
from engine.llm import complete

TRIPLE_JSON_SCHEMA = {
    "triples": [{"subject": "string", "relation": "string", "object": "string"}]
}


def build_vocabulary(corpus_dir: Path) -> list[str]:
    """Union every note's .entities, normalized, deduped, sorted alphabetically."""
    notes = load_corpus(corpus_dir)
    vocab: set[str] = set()
    for note in notes:
        for entity in note.entities:
            vocab.add(normalize_entity(entity))
    return sorted(vocab)


def load_chunks(chunks_path: Path) -> tuple[str, list[dict]]:
    build_id, chunks = read_chunks_artifact(chunks_path)
    return build_id, sorted(chunks, key=lambda c: c["chunk_id"])


def _extraction_prompt(chunk: dict, vocabulary: list[str]) -> str:
    heading = chunk.get("heading") or "(no heading)"
    vocab_list = "\n".join(f"- {term}" for term in vocabulary)
    return (
        "You are building a knowledge graph over a corpus of AI/ML engineering notes.\n\n"
        f"Note: {chunk['note_id']}\n"
        f"Heading: {heading}\n"
        "Chunk text:\n"
        f'"""\n{chunk["text"]}\n"""\n\n'
        "Extract (subject, relation, object) triples that are explicitly supported by "
        "this chunk text. Both subject and object MUST be chosen verbatim from the "
        "following controlled vocabulary of entities (do not invent, translate, or "
        "abbreviate terms outside this list):\n"
        f"{vocab_list}\n\n"
        "The relation should be a short free-text phrase (1-4 words) describing how "
        "the subject relates to the object, e.g. 'improves', 'requires', 'is an "
        "alternative to', 'measured by', 'contrasts with'. Only extract a triple when "
        "the relationship is actually stated or clearly implied in the chunk text -- "
        "it is fine and expected to return zero triples if nothing in the vocabulary "
        "genuinely relates here. Do not fabricate relationships."
    )


def extract_triples_for_chunk(chunk: dict, vocabulary: list[str], vocab_set: set[str]) -> tuple:
    """Returns (accepted_triples, total_extracted, dropped_count) for one chunk.

    accepted_triples is a list of (subject, relation, object) with subject/object
    already normalized and verified to be in vocab_set.
    """
    prompt = _extraction_prompt(chunk, vocabulary)
    result = complete(prompt, json_schema=TRIPLE_JSON_SCHEMA)
    result_json = result.get("json")
    raw_triples = result_json.get("triples", []) if isinstance(result_json, dict) else []
    if not isinstance(raw_triples, list):
        raw_triples = []

    accepted = []
    dropped = 0
    for triple in raw_triples:
        if not isinstance(triple, dict):
            dropped += 1
            continue
        subject = normalize_entity(str(triple.get("subject", "")))
        relation = str(triple.get("relation", "")).strip()
        obj = normalize_entity(str(triple.get("object", "")))
        if not subject or not obj or not relation:
            dropped += 1
            continue
        if subject not in vocab_set or obj not in vocab_set:
            dropped += 1
            continue
        accepted.append((subject, relation, obj))

    return accepted, len(raw_triples), dropped


def _community_summary_prompt(
    community_id: int, entity_ids: list[str], sample_edges: list[dict], chunk_text_by_id: dict
) -> str:
    entity_list = "\n".join(f"- {e}" for e in entity_ids)
    edge_lines = []
    for edge in sample_edges:
        edge_lines.append(f"- {edge['src']} --[{edge['rel']}]--> {edge['dst']}")
    edges_block = "\n".join(edge_lines) if edge_lines else "(no sample edges)"

    excerpt_lines = []
    for chunk_id in sorted({e["chunk_id"] for e in sample_edges}):
        text = chunk_text_by_id.get(chunk_id, "")
        if text:
            excerpt_lines.append(f"[{chunk_id}]: {text[:300]}")
    excerpts_block = "\n".join(excerpt_lines) if excerpt_lines else "(no excerpts)"

    return (
        "You are summarizing one community (cluster) of a knowledge graph built over "
        "AI/ML engineering notes.\n\n"
        f"Community entities:\n{entity_list}\n\n"
        f"Sample relationships in this community:\n{edges_block}\n\n"
        f"Grounding excerpts from source chunks:\n{excerpts_block}\n\n"
        "Write a 1-3 sentence summary of what this community of entities is about, "
        "grounded in the relationships and excerpts above -- do not just free-associate "
        "from the entity names alone."
    )


def main() -> dict:
    vocabulary = build_vocabulary(CORPUS_DIR)
    vocab_set = set(vocabulary)

    build_id, chunks = load_chunks(CHUNKS_PATH)
    chunk_text_by_id = {c["chunk_id"]: c["text"] for c in chunks}

    total_extracted = 0
    total_dropped = 0
    accepted_edges: list[dict] = []  # {"src","rel","dst","chunk_id"}

    for chunk in chunks:
        accepted, extracted_count, dropped_count = extract_triples_for_chunk(
            chunk, vocabulary, vocab_set
        )
        total_extracted += extracted_count
        total_dropped += dropped_count
        for subject, relation, obj in accepted:
            accepted_edges.append(
                {"src": subject, "rel": relation, "dst": obj, "chunk_id": chunk["chunk_id"]}
            )

    # Undirected projection for community detection: one node per entity with >=1
    # accepted edge, one edge per unique (src, dst) pair (order-independent),
    # weighted by triple count.
    graph = nx.Graph()
    pair_weight: dict[tuple, int] = defaultdict(int)
    for edge in accepted_edges:
        pair = tuple(sorted((edge["src"], edge["dst"])))
        pair_weight[pair] += 1
    for (a, b), weight in pair_weight.items():
        graph.add_edge(a, b, weight=weight)

    partition: dict[str, int] = {}
    if graph.number_of_nodes() > 0:
        partition = community_louvain.best_partition(graph, random_state=0)

    # entities: degree >= 1 (i.e. present in graph, since graph only contains
    # entities that appear in at least one accepted edge)
    entity_chunk_ids: dict[str, set] = defaultdict(set)
    for edge in accepted_edges:
        entity_chunk_ids[edge["src"]].add(edge["chunk_id"])
        entity_chunk_ids[edge["dst"]].add(edge["chunk_id"])

    entities_payload = [
        {
            "id": entity_id,
            "chunk_ids": sorted(chunk_ids),
            "community": partition.get(entity_id),
        }
        for entity_id, chunk_ids in sorted(entity_chunk_ids.items())
    ]

    # communities: group entities by community id, summarize each via LLM.
    community_entities: dict[int, list[str]] = defaultdict(list)
    for entity_id, community_id in partition.items():
        community_entities[community_id].append(entity_id)

    communities_payload = []
    for community_id in sorted(community_entities.keys()):
        entity_ids = sorted(community_entities[community_id])
        entity_id_set = set(entity_ids)
        sample_edges = [
            e for e in accepted_edges if e["src"] in entity_id_set and e["dst"] in entity_id_set
        ][:15]
        prompt = _community_summary_prompt(
            community_id, entity_ids, sample_edges, chunk_text_by_id
        )
        result = complete(prompt)
        summary = result["text"].strip()
        communities_payload.append(
            {"id": community_id, "entity_ids": entity_ids, "summary": summary}
        )

    graph_payload = {
        "build_id": build_id,
        "entities": entities_payload,
        "edges": accepted_edges,
        "communities": communities_payload,
    }

    GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    GRAPH_PATH.write_text(json.dumps(graph_payload, indent=2), encoding="utf-8")

    summary_stats = {
        "chunks_processed": len(chunks),
        "vocabulary_size": len(vocabulary),
        "triples_extracted": total_extracted,
        "triples_dropped": total_dropped,
        "triples_accepted": len(accepted_edges),
        "edge_count": len(accepted_edges),
        "entity_count_before_filter": len(vocabulary),
        "entity_count_after_filter": len(entities_payload),
        "community_count": len(communities_payload),
    }
    return summary_stats


def _print_summary(stats: dict) -> None:
    print(f"chunks processed: {stats['chunks_processed']}")
    print(f"vocabulary size: {stats['vocabulary_size']}")
    print(f"triples extracted: {stats['triples_extracted']}")
    print(f"triples dropped (not in vocab / malformed): {stats['triples_dropped']}")
    print(f"triples accepted / edges: {stats['triples_accepted']}")
    print(
        "entities: "
        f"{stats['entity_count_before_filter']} in vocabulary -> "
        f"{stats['entity_count_after_filter']} with >=1 edge"
    )
    print(f"communities: {stats['community_count']}")
    print(f"wrote: {GRAPH_PATH}")


if __name__ == "__main__":
    stats = main()
    _print_summary(stats)
