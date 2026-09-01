---
title: "Chunk Overlap and Why It Matters"
tags: [retrieval, chunking]
entities: [chunk overlap, chunking, retrieval-augmented generation, vector database]
created: 2026-01-06
---

Chunk overlap is the practice of letting adjacent chunks share a small amount of trailing and leading text instead of splitting a document at hard, non-overlapping boundaries. Without overlap, a sentence that happens to fall right at a chunk boundary can be split so that neither resulting chunk contains the complete thought, and a query about that sentence may fail to retrieve either half convincingly.

Overlap fixes this by duplicating a slice of text into both neighboring chunks, so a fact sitting near a boundary is fully present in at least one chunk regardless of exactly where the cut falls. This is a purely mechanical fix — it does not require smarter chunking logic, just accepting some redundancy in the index in exchange for fewer boundary casualties.

This engine's default chunking configuration uses a target chunk size of `CHUNK_TARGET_TOKENS = 250` tokens with `CHUNK_OVERLAP_TOKENS = 50` tokens of overlap between consecutive chunks — a 20% overlap ratio. That ratio is the actual tradeoff: every token spent on overlap is a token duplicated in the vector database, which means more chunks to store, more vectors to search over, and more redundant near-duplicate hits competing for the same top-k retrieval slots. Push overlap too high and a boundary-spanning fact becomes nearly guaranteed to be retrievable, but the corpus balloons and retrieval quality can actually degrade because several near-identical chunks crowd out other genuinely relevant material in the ranked results.

Push overlap too low — or to zero — and storage stays lean, but you reintroduce the original problem: any fact that happens to straddle a chunk boundary is at risk of being unrecoverable from either side. In practice a modest overlap in the 10-25% range of the target chunk size is a reasonable default; treating overlap as a free correctness improvement rather than a genuine storage-versus-completeness tradeoff is a common mistake when tuning a retrieval-augmented generation pipeline.

Overlap alone does not compensate for a chunk size that is fundamentally wrong for the source material — see the separate note on chunk size tradeoffs for that decision, which is independent of how much adjacent chunks share.
