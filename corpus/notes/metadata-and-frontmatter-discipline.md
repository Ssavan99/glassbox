---
title: "Metadata and Frontmatter Discipline"
tags: [data-quality, architecture]
entities: [data quality, citation, chunking, vector database]
created: 2026-01-11
---

Frontmatter is the structured metadata block at the top of a note — title, tags, entities, creation date — separate from the note's prose body. It is easy to treat as bookkeeping, but frontmatter discipline is a data quality concern with direct downstream consequences: everything a retrieval pipeline can filter, cite, or reason about structurally has to come from metadata that was recorded consistently, because none of it can be reliably reconstructed from prose alone after the fact.

The `entities` field is the clearest example of why consistency matters more than completeness. If one note tags a concept as `bm25` and another tags the same concept as `BM25 algorithm`, a downstream process trying to find every note connected to that concept — building a knowledge graph, computing entity co-occurrence, or just filtering search results by topic — will treat them as two unrelated entities and silently miss half the connected notes. This is a pure metadata bug: the prose in both notes may be perfectly accurate, but the connective structure between them breaks because the canonical string was not reused exactly.

Citation depends on frontmatter too, though less obviously. A note's title becomes the human-readable label in a citation, and its filename — derived from the title as a stable identifier — is what a vector database's metadata actually stores alongside each chunk's embedding, so a generated answer can point back to a specific, addressable source rather than an anonymous passage of text. A title that gets renamed after notes have already been chunked and indexed breaks that link unless the index is rebuilt, which is a quiet failure mode worth knowing about before it causes a citation to point at a filename that no longer exists.

The discipline that actually pays off is boring and mechanical: pick canonical entity strings before writing notes, not after, and reuse them verbatim across every note that touches the same concept, rather than letting each note's author — human or model — invent a slightly different phrasing each time. This is exactly the discipline this corpus was built under: a fixed vocabulary of canonical entity terms, reused deliberately across dozens of notes so a future knowledge-graph pass has real, non-fragmented edges to traverse.
