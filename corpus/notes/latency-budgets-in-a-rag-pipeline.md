---
title: "Latency Budgets in a RAG Pipeline"
tags: [serving, latency]
entities: [latency, reranking, cross-encoder, embedding model, throughput, kv cache]
created: 2026-01-10
---

A latency budget is the total time an interactive request is allowed to take, broken down across every stage that contributes to it, so a system's end-to-end responsiveness can be reasoned about stage by stage rather than as one opaque number. For a retrieval-augmented pipeline, a typical budget spans embedding the query, running dense and sparse retrieval, fusing the results, optionally reranking, assembling the prompt, and generating the answer — and each of those stages has a very different cost profile worth tracking separately.

Embedding a single query with a small embedding model is fast, typically single-digit milliseconds. Retrieval over a moderate-sized corpus, whether brute-force or index-based, is also fast at personal-corpus scale, usually well under 50 milliseconds. These stages are rarely where a RAG pipeline's latency actually goes; they are cheap relative to what comes after.

Reranking is the stage that most commonly breaks a tight latency budget. Because a cross-encoder requires one full forward pass per query-candidate pair rather than a single cheap vector comparison, reranking even a modest shortlist of 20 to 50 candidates can add on the order of 100 to 300 milliseconds, depending on the cross-encoder's size and the hardware it runs on — this is the concrete cost side of the accuracy-versus-latency tradeoff introduced in the note on reranking with cross-encoders, which explains why reranking exists but not what it actually costs. A system with a strict sub-200-millisecond interactive latency target may need to skip reranking entirely, rerank a smaller shortlist, or use a lighter cross-encoder to fit inside its budget.

Generation is usually the single largest contributor to end-to-end latency by far, since it is proportional to the number of output tokens and dominates everything upstream of it combined for anything beyond a short answer — which is why techniques that reduce per-token generation cost, like quantization and an efficient KV cache, tend to have outsized impact on overall pipeline latency compared to further optimizing retrieval or reranking. Treating the latency budget as a single number rather than a per-stage breakdown makes it very easy to over-optimize an already-cheap stage while ignoring the one actually eating the budget.
