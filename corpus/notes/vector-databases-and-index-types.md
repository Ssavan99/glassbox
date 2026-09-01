---
title: "Vector Databases and Index Types"
tags: [retrieval, infrastructure]
entities: [vector database, embedding model, cosine similarity, dense retrieval, throughput, embedding dimension]
created: 2026-01-06
---

A vector database stores embeddings and answers nearest-neighbor queries: given a query vector, return the k stored vectors most similar to it, usually by cosine similarity or a related distance metric. For a small personal corpus of a few hundred or a few thousand chunks, this can be as simple as a flat array searched with brute-force comparison — every stored vector gets compared against the query, which is exact and trivially correct, and at that scale still fast enough to feel instant.

Brute-force search stops scaling once a corpus reaches millions of vectors, because comparing a query against every stored vector becomes too slow for interactive use. At that scale, vector databases switch to approximate nearest-neighbor indexes — structures like HNSW (hierarchical navigable small world graphs) or IVF (inverted file indexes) that trade a small amount of recall for a large gain in query throughput, by cleverly avoiding comparing the query against most of the corpus.

The practical decision of when to introduce an approximate index is a scale question, not a correctness question: approximate methods are not wrong, they simply accept that the very best match might occasionally rank second or third instead of first, in exchange for search that stays fast as the corpus grows into the millions. A personal knowledge base rarely reaches that scale, which is why many small RAG systems get away with brute-force flat search indefinitely and never need to reach for a dedicated approximate-index vector database at all.

What matters more at small scale is what metadata the vector database stores alongside each embedding — the source note's id, its position within the note, and its frontmatter tags and entities — because that metadata is what lets a retrieval result be traced back to a specific, citable note rather than returning an anonymous blob of text. A vector database that only stores raw vectors without this metadata forces you to reconstruct provenance after the fact, which is exactly the kind of gap that breaks citation quality in evaluation even when raw retrieval accuracy looks fine.

The embedding dimension chosen upstream directly sets the vector database's per-chunk storage cost, since every stored vector is `dimension x 4 bytes` at full precision — a decision made once, when the embedding model is chosen, that the vector database then has to live with for the life of the index.
