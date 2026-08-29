---
title: "Reducing Latency with Batching"
tags: [serving, latency]
entities: [batching, throughput, latency]
created: 2026-01-10
---

Batching groups multiple inference requests together so a GPU processes them in a single forward pass instead of one at a time. The motivation is hardware utilization: a modern GPU is heavily underused running one request through a large model, because most of its compute capacity sits idle while it waits on memory access rather than doing useful arithmetic. Processing several requests together amortizes that overhead across all of them and dramatically raises throughput — the number of requests served per second, aggregated across all users.

The naming here is easy to get backwards, and it matters: static batching primarily improves throughput, not latency for an individual request. In its simplest form, the server waits to accumulate a full batch of requests before running any of them, which means the very first request in a batch has to wait for the last one to arrive before processing even starts. A single request submitted when the server is otherwise idle can end up waiting far longer than it would if processed immediately alone, even though the system as a whole is now serving far more total requests per second.

This creates a genuine tension between per-request latency and system-wide throughput. A larger batch size raises throughput further, since fixed per-batch overhead gets spread across more requests, but it also raises the worst-case wait time for whichever request happened to arrive first and had to wait for the batch to fill. Tuning batch size is fundamentally a decision about which metric matters more for a given workload: an interactive product answering one user's question in real time cares primarily about latency, while a bulk offline job processing thousands of documents overnight cares primarily about throughput and can tolerate a much larger batch size.

Static batching's latency cost is specifically what continuous batching, covered in a separate note, is designed to fix — that note explains a scheduling change that keeps the throughput benefit of batching while largely removing the wait-for-the-batch-to-fill latency penalty described here. Reducing latency through batching alone, without that scheduling change, is the wrong technique to reach for if latency, not raw throughput, is the actual bottleneck.
