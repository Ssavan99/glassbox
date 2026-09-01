---
title: "Caching Retrieval Results"
tags: [serving, retrieval]
entities: [latency, embedding model, vector database, throughput]
created: 2026-01-10
---

Caching retrieval results means storing the output of a previous query — the retrieved chunks, or even the fully assembled prompt — keyed by the query text, so a repeated or near-identical query can skip embedding and search entirely and return the previous result immediately. For a personal knowledge base, where the same handful of questions tend to get asked repeatedly over time, this can eliminate a meaningful share of total query latency for very little engineering effort.

The most straightforward form is exact-match caching: hash the query string, check whether that exact hash has been seen before, and if so, return the cached retrieval result directly. This is cheap to implement and completely safe from a correctness standpoint, but it only helps for literally repeated queries — a user rephrasing the same question even slightly produces a cache miss and falls all the way through to the full retrieval pipeline again.

A more powerful but riskier form is semantic caching: embed the incoming query, compare it against the embeddings of previously cached queries, and treat a sufficiently close match as a cache hit even if the query text differs. This catches paraphrased repeat queries that exact-match caching misses entirely, but it introduces a genuine correctness risk — two queries can be close in embedding space while actually asking for subtly different information, and serving a stale cached result for a query that only looks similar produces a wrong answer that looks confidently right, which is a much worse failure than a slow cache miss would have been.

Cache invalidation is the other half of the design that is easy to underweight: if the underlying corpus changes — a note is edited or a new note is added — any cached retrieval result computed before that change can silently go stale, returning outdated evidence for a query whose true best answer changed. A cache tied to a corpus version, invalidated wholesale whenever the corpus is re-indexed, is a simpler and safer default than trying to track which cached entries a given corpus edit actually affects. As with most serving optimizations, caching trades a small amount of implementation complexity and staleness risk for a real reduction in typical-case latency and load on the underlying vector database.
