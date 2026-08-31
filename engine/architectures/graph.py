"""Graph RAG: seed entities from the query -> 2-hop expansion over a
pre-built knowledge graph -> gather chunks + community summaries -> generate.

All the expensive extraction work (pulling entities/relations out of the
corpus and clustering them into communities) already happened offline in
scripts/build_graph.py, so the online budget for this architecture is
exactly one LLM call: the final `generate` step. `graph_seed` and
`graph_expand` are pure heuristic/graph-traversal steps over the already-built
artifacts/graph.json — no LLM involved.
"""

from __future__ import annotations

import time

from engine.graph_index import expand_hops, load_graph, seed_entities
from engine.index import load_index
from engine.llm import complete
from engine.prompts import build_answer_prompt
from engine.trace import Metrics, Trace, TraceBuilder

from .base import Architecture


class GraphArchitecture(Architecture):
    name = "graph"
    description = (
        "Seed entities are matched against a pre-built knowledge graph, "
        "2-hop expansion pulls in connected chunks and community summaries, "
        "and a single generate call answers from that gathered context."
    )

    # region: run
    def run(self, question: str, trace_id: str | None = None) -> Trace:
        start = time.perf_counter()
        graph = load_graph()
        index = load_index()
        builder = TraceBuilder(architecture=self.name, question=question, trace_id=trace_id)

        seeds = seed_entities(question, graph)
        n_seed = builder.node(
            "graph_seed",
            f"Seed entities ({len(seeds)} matched)",
            parents=[],
            explain=(
                "Graph RAG finds a completely different entry point than "
                "embedding-based retrieval: instead of measuring semantic "
                "similarity between a query vector and chunk vectors, it "
                "matches literal entity mentions in the question against the "
                "pre-built knowledge graph's vocabulary to jump straight to a "
                "set of graph nodes. This is a pure string-matching heuristic "
                "with no LLM call — the corpus was already mined for entities "
                "and relations offline when the graph was built."
            ),
            entities=list(seeds),
        )

        chunk_ids, edges = expand_hops(seeds, graph)
        # Resolve to real ChunkRecords *before* building the graph_expand
        # node, and record that same resolved list in the node's payload --
        # not expand_hops's raw output -- so the trace can never claim a
        # chunk_id was part of this run's context when it wasn't actually
        # looked up and handed to generate (e.g. if artifacts/graph.json and
        # artifacts/chunks.json have drifted out of sync).
        retrieved_chunks = [
            index.chunk_by_id[cid] for cid in chunk_ids if cid in index.chunk_by_id
        ]
        used_chunk_ids = [c.chunk_id for c in retrieved_chunks]

        n_expand = builder.node(
            "graph_expand",
            f"2-hop expansion ({len(used_chunk_ids)} chunks)",
            parents=[n_seed],
            explain=(
                "Two-hop traversal from the seed entities can surface facts "
                "connected to the question's topic that never share a chunk "
                "with it at all — a fact only reachable by walking src -> rel "
                "-> dst -> rel -> dst through the graph. This is the opposite "
                "failure mode from embedding-based retrieval, which can only "
                "find chunks that are textually or semantically close to the "
                "query itself, not ones connected to it only through an "
                "intermediate entity."
            ),
            hops=2,
            edges=[{"src": e.src, "rel": e.rel, "dst": e.dst} for e in edges],
            chunk_ids=used_chunk_ids,
        )

        touched_entities = set(seeds) | {e.src for e in edges} | {e.dst for e in edges}
        # Sorted, not just deduped: `touched_entities` is a set, whose
        # iteration order varies across process runs (CPython string-hash
        # randomization) -- an unsorted community_ids list would make the
        # community-summary block order in the generate prompt (and
        # therefore engine/llm.py's cache key, which hashes the literal
        # prompt text) nondeterministic across reruns of the same question.
        touched_community_ids: set[int] = {
            graph.entities[entity_id].community
            for entity_id in touched_entities
            if entity_id in graph.entities and graph.entities[entity_id].community is not None
        }
        community_ids = sorted(touched_community_ids)

        summaries = []
        for community_id in community_ids:
            community = graph.communities.get(community_id)
            if community is None:
                continue
            summaries.append(f"Community {community_id}: {community.summary}")
        extra_context = "\n\n".join(summaries) if summaries else None

        prompt = build_answer_prompt(question, retrieved_chunks, extra_context=extra_context)
        llm_result = complete(prompt)
        answer = llm_result["text"]
        tokens = llm_result["prompt_tokens"] + llm_result["completion_tokens"]
        builder.node(
            "generate",
            "Generate answer",
            parents=[n_expand],
            explain=(
                "The chunks gathered from graph expansion, plus the community "
                "summaries for any communities the touched entities belong to, "
                "are stuffed into a single prompt and handed to the LLM in one "
                "shot — the only LLM call this architecture makes online, since "
                "seeding and expansion are both pure graph traversal."
            ),
            output=answer,
            prompt_preview=prompt[:200],
            tokens=tokens,
        )

        latency_ms = (time.perf_counter() - start) * 1000
        metrics = Metrics(
            latency_ms=latency_ms,
            llm_calls=1,
            prompt_tokens=llm_result["prompt_tokens"],
            completion_tokens=llm_result["completion_tokens"],
        )
        return builder.build(answer=answer, metrics=metrics)
    # endregion
