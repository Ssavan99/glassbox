---
title: "Retrieval Metrics: Recall@k and MRR"
tags: [evaluation, retrieval]
entities: [retrieval metrics, evaluation harness, golden dataset, dense retrieval, bm25, reranking, cross-encoder]
created: 2026-01-07
---

Retrieval metrics measure whether the right evidence was found, independently of whether the final generated answer was correct — a distinction that matters because retrieval and generation fail for different reasons and need different fixes. Two of the most common retrieval metrics are recall@k and mean reciprocal rank (MRR), and they answer subtly different questions.

Recall@k asks: among the top k retrieved chunks, is the correct supporting chunk present at all? It is a binary, per-query yes/no that gets averaged across the golden dataset. Recall@k is forgiving about ranking order — a correct chunk retrieved at position 1 and one retrieved at position k score identically — which makes it a good fit for measuring whether a downstream reranking or generation step even has a chance of using the right evidence, since both would receive the same candidate set either way.

Mean reciprocal rank cares about order: it scores each query by `1 / rank` of the first correct chunk in the ranked list, then averages across queries. A correct chunk at position 1 scores a full point; at position 2 it scores 0.5; at position 10 it scores 0.1. MRR is the more sensitive metric of the two for judging raw ranking quality, because it directly penalizes a retriever that technically finds the right chunk but buries it low enough that it might get cut before reaching the model's context window, or crowded out during reranking.

These metrics should be tracked separately for dense retrieval and bm25 before any fusion step, not just on the final hybrid ranking. A hybrid system with a good combined score can still be quietly relying on one retrieval method to do almost all the work, with the other contributing little — and that imbalance only becomes visible when recall@k and MRR are broken out per method rather than measured only on the merged result.

Retrieval metrics computed against a golden dataset are also what make it possible to isolate whether a change to chunking or the embedding model actually improved retrieval, as opposed to improving or degrading the downstream generation step for unrelated reasons — the two are easy to conflate without metrics that specifically target the retrieval stage in isolation.

Recall@k and MRR are worth computing again after reranking, not just before it, since a cross-encoder reranking pass is itself a ranking step that can raise or lower these same metrics — a system whose initial retrieval scores poorly on MRR but recovers sharply after reranking is telling you something different from one that scores well on both, even if their final top-1 accuracy ends up identical.
