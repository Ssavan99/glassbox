---
title: "Reciprocal Rank Fusion Explained"
tags: [retrieval, search]
entities: [reciprocal rank fusion, hybrid search, bm25, dense retrieval, retrieval metrics]
created: 2026-01-06
---

Reciprocal rank fusion is the merge step that turns two separate ranked lists — a dense retrieval ranking and a sparse bm25 ranking — into a single combined ranking for hybrid search. Rather than trying to normalize and compare raw similarity scores from two different scoring systems, which is unreliable because cosine similarity and bm25 scores live on completely different, non-comparable scales, reciprocal rank fusion only looks at each document's *position* in each list.

The formula scores each document by summing `1 / (k + rank)` across every ranked list it appears in, where rank is its position (1st, 2nd, 3rd, ...) in that particular list and `k` is a constant. A document that ranks highly in both the dense and sparse lists accumulates a high combined score; a document that appears only in one list still gets a moderate boost rather than being ignored outright, which is exactly the graceful behavior hybrid search wants — reward agreement, but do not require it.

The constant `k` controls how sharply the fusion favors top-ranked results over lower-ranked ones. This engine's implementation uses `RRF_K = 60`, a widely used default from the original reciprocal rank fusion literature: a larger k flattens the score differences between rank 1 and rank 10, giving more weight to documents that show up broadly across both lists even at a modest rank, while a smaller k makes the top one or two positions dominate the combined score almost completely. Tuning k up or down is a legitimate way to bias hybrid search toward either "trust broad agreement" or "trust whichever method was most confident," and is one of the few genuinely cheap knobs available for adjusting retrieval behavior without retraining or re-embedding anything.

Reciprocal rank fusion is deliberately simple and requires no score calibration between retrieval methods, which is a large part of why it remains the default fusion approach in most hybrid search systems rather than more elaborate learned combination methods — the complexity of a fancier fusion model rarely earns its keep against how well rank-based fusion already performs.
