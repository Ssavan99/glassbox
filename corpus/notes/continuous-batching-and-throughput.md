---
title: "Continuous Batching and Throughput"
tags: [serving, latency]
entities: [batching, throughput, latency, kv cache]
created: 2026-01-10
---

Continuous batching, also called dynamic or in-flight batching, fixes the core latency problem of static batching described in the note on reducing latency with batching: instead of waiting for a fixed group of requests to arrive before starting any of them, a continuous batching scheduler adds a new request to the running batch as soon as it arrives, and removes a request from the batch as soon as it finishes generating, without waiting for every other request in the batch to complete first.

This works because autoregressive generation produces one token at a time, and different requests in a batch naturally finish at different points — a short answer finishes generating long before a long one does. Static batching wastes the GPU slots freed up by an early-finishing request until the entire batch completes; continuous batching immediately backfills that freed slot with a new incoming request, keeping the GPU busy at close to its true utilization ceiling rather than being bottlenecked by whichever request in the batch happens to run longest.

The practical effect is that continuous batching gets close to the throughput of large static batches while keeping the latency profile much closer to unbatched, per-request processing — a request no longer has to wait for a batch to fill before it starts, and it does not get stuck behind a slower neighbor's completion either. This is why continuous batching has become the default scheduling strategy in most modern inference serving frameworks rather than a niche optimization; it largely removes the throughput-versus-latency tradeoff that static batching forces a system to accept.

Continuous batching depends heavily on efficient per-request KV cache management, since each request in a dynamically changing batch needs its own cache state tracked and freed independently as requests join and leave — a scheduler that has to reshuffle or recompute cache state on every batch change would lose most of the latency benefit it is trying to provide. This coupling between the batching strategy and KV cache management is why the two are usually discussed, and implemented, together in a serving stack rather than as fully independent concerns.
