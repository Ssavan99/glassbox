---
title: "KV Cache and Why It Matters for Serving"
tags: [serving, latency]
entities: [kv cache, latency, context window, throughput, batching]
created: 2026-01-10
---

The KV cache — short for key-value cache — stores the intermediate attention keys and values computed for every token already generated in a request, so that generating the next token does not require recomputing attention over the entire preceding sequence from scratch. Without it, an autoregressive model generating a 500-token response would redo work proportional to the square of the sequence length, recomputing attention over tokens it has already processed dozens of times over.

This matters enormously for latency on long-context requests. A retrieval-augmented prompt that stuffs several retrieved chunks into the context window can easily run to a few thousand tokens before the model generates a single word of its answer — the KV cache is what makes generating the response, token by token, roughly linear in cost rather than quadratic, and its absence would make long-context RAG prompts prohibitively slow to serve interactively.

The cost of the KV cache is memory, not compute — it has to be stored for the full duration of a request, and it grows linearly with context length and with the number of concurrent requests being served. This is a major reason context window size is not a free lever: doubling how many retrieved chunks get included in a prompt does not just cost more prompt-processing time, it also doubles the KV cache memory that request consumes for its entire duration, directly limiting how many concurrent requests a fixed amount of GPU memory can serve at once.

KV cache memory pressure is precisely why continuous batching, discussed separately, needs careful per-request cache management: a serving system juggling many concurrent requests with different context lengths has to allocate and free KV cache memory per request as they join and leave the batch, and a system that handles this poorly runs out of usable memory and starts rejecting or delaying requests well before raw compute becomes the bottleneck. Techniques like KV cache quantization — storing the cached keys and values at lower precision — are an increasingly common way to stretch available memory further without touching the model's own weights.
