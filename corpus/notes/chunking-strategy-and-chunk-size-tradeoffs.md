---
title: "Chunking Strategy and Chunk Size Tradeoffs"
tags: [retrieval, chunking]
entities: [chunking, embedding model, context window, retrieval-augmented generation, token budget]
created: 2026-01-06
---

Chunking is the step where a source document is split into smaller pieces before each piece is embedded and indexed. It sounds mechanical, but chunk size is one of the highest-leverage decisions in a retrieval-augmented generation pipeline, because it determines what a single retrieved unit can and cannot contain.

Small chunks are precise: an embedding computed over a tight, single-idea chunk produces a sharp vector that matches queries about that specific idea well, and a retriever can afford to pull several small chunks without blowing the token budget. The cost is fragmentation — a fact that naturally spans two or three sentences of surrounding context can get cut in half, so retrieval finds the chunk but the model receives an incomplete picture.

Large chunks preserve context: a paragraph or section stays intact, so a fact and its surrounding qualifiers travel together. The cost is dilution — a large chunk mixes the relevant sentence with several unrelated ones, which blurs its embedding and can push it further from the query vector than a smaller, purer chunk would have been. Large chunks also eat more of the context window per retrieved item, which caps how many distinct pieces of evidence the model can see at once.

There is no universally correct chunk size; it depends on the source material. Heading-aware chunking, which respects a document's own `##` section boundaries rather than cutting at a fixed character count, tends to outperform naive fixed-length splitting because it keeps semantically coherent units — like one architectural explanation, or one failure mode — together rather than slicing mid-thought. A useful default is to target a chunk size in the low hundreds of tokens, since that roughly matches the length of a single coherent paragraph while still leaving room to retrieve several chunks per query without exhausting the token budget.

Chunk size interacts with chunk overlap, a related but separate lever covered in its own note — chunking decides where the boundaries fall, overlap decides how much adjacent chunks share across those boundaries, and getting one right does not fix problems caused by the other.
