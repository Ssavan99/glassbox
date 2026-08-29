---
title: "Embedding Dimension and Model Size Tradeoffs"
tags: [retrieval, embeddings]
entities: [embedding dimension, embedding model, vector database, latency, quantization, semantic search]
created: 2026-01-06
---

Embedding dimension is the length of the vector an embedding model outputs — a small model might output 384 numbers per chunk, a larger one 1536 or more. This engine uses `all-MiniLM-L6-v2`, a compact model with `EMBEDDING_DIM = 384`. Dimension is not a cosmetic detail: it directly sets the storage footprint of the vector database (every stored chunk costs `dimension x 4 bytes` at full float32 precision) and the compute cost of every similarity comparison, since cosine similarity over a longer vector takes proportionally more arithmetic.

This dimension is the same number semantic search relies on for every comparison it makes, so any change to it changes both storage cost and how sharply semantic search can separate nearby meanings. Higher-dimensional embeddings generally carry more representational capacity — more room to separate subtly different meanings that a smaller model would collapse into nearby, harder-to-distinguish points. This mostly shows up as an advantage on large, topically dense corpora where many chunks are about closely related things and fine distinctions matter for ranking. On a smaller, more topically varied personal corpus, the practical difference between a 384-dimension and a 1536-dimension model is often much less noticeable, because there simply are not as many near-duplicate concepts competing for the same region of vector space.

The cost side is concrete and worth internalizing: a 1536-dimension model stores four times the raw vector data per chunk compared to a 384-dimension model, and every similarity search does four times the multiply-accumulate work per comparison. At personal-corpus scale — hundreds to low thousands of chunks — this cost difference is negligible in absolute terms. At larger scale it compounds directly into both storage bills and query latency, which is part of why production systems sometimes choose a smaller embedding model deliberately rather than always reaching for the largest one available.

Dimension reduction is a distinct lever from quantization — dimension changes how much information is captured per vector, while quantization changes how precisely each of those numbers is stored — and the two are frequently confused. A system can quantize a high-dimensional embedding down to lower storage cost while keeping all of its dimensions, or choose a smaller-dimension model outright; they solve overlapping cost problems through different mechanisms and are not substitutes for each other.
