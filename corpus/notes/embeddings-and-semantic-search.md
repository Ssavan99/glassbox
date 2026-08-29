---
title: "Embeddings and Semantic Search"
tags: [retrieval, embeddings, architecture]
entities: [embedding model, semantic search, cosine similarity, dense retrieval, embedding dimension, chunking, hybrid search]
created: 2026-01-05
---

An embedding model converts a piece of text into a fixed-length numerical vector that represents its meaning, positioning texts with similar meaning near each other in vector space. This is what makes semantic search possible: a query like "how do I keep AI answers grounded" can retrieve notes about citation discipline or evaluation harnesses even when none of those exact words appear in the query, because the vectors land close together regardless of surface wording.

Similarity between two vectors is usually measured with cosine similarity, which compares the angle between vectors rather than their raw magnitude. This matters because it makes the comparison insensitive to text length — a short precise chunk and a longer chunk covering the same idea can still score as highly similar. Dense retrieval is the general name for this family of techniques: retrieving by vector similarity over dense embeddings, as opposed to sparse, keyword-based methods.

Embedding quality depends on more than the model itself. The embedding dimension — the length of the output vector — trades off representational capacity against storage and compute cost; a 384-dimension model is far cheaper to store and search than a 1536-dimension one, though it may separate fine-grained meanings less cleanly. Chunking strategy matters just as much: an embedding computed over a chunk that mixes two unrelated ideas produces a blurry vector that matches neither well.

Dense retrieval is not a universal solution. It tends to struggle with exact identifiers, acronyms, version numbers, and rare proper nouns, because embedding models are trained to generalize over meaning and often smooth over precise tokens that a keyword match would catch instantly. This is the central reason hybrid search — combining a dense embedding search with a sparse keyword search — consistently outperforms either method alone in practice, especially in corpora that mix conceptual prose with exact technical terms.

When debugging a retrieval system that "feels dumb," it is worth separating two very different failure causes: the embedding model may be too coarse to distinguish nearby concepts, or the chunking may be splitting a coherent idea across boundaries so no single vector represents it well. Testing the embedding model on a fixed chunking strategy, and vice versa, is the only reliable way to tell which stage is actually responsible.
