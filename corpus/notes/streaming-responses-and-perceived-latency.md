---
title: "Streaming Responses and Perceived Latency"
tags: [serving, latency]
entities: [latency, throughput, token budget]
created: 2026-01-10
---

Streaming sends a model's response to the client token by token as it is generated, rather than waiting for the full answer to finish before returning anything. It does not reduce the actual total time needed to generate a complete response — the model still has to produce every token it would have produced anyway — but it dramatically changes perceived latency, the experience of how long a wait feels to the person waiting.

The relevant number for perceived latency in a streaming setup is time-to-first-token: how long the user waits before anything at all appears, rather than the total time until the full response is complete. A response that takes several seconds to fully generate but starts streaming visible text within a few hundred milliseconds reads as fast and responsive, while an identical response held back until it is fully complete and then displayed all at once reads as sluggish — even though the total wall-clock time to full completion is the same in both cases.

For a retrieval-augmented system specifically, time-to-first-token includes everything upstream of generation: embedding the query, retrieval, fusion, optional reranking, and prompt assembly all have to finish before the model can even start producing its first output token. This means the retrieval-side latency budget, not just generation speed, directly determines how responsive a streaming interface actually feels — a slow retrieval stage delays the first visible token just as much as slow generation would, even though generation is usually the larger contributor to total completion time.

Streaming interacts awkwardly with structured output and citation validation: if citations are meant to be checked against the actual retrieved set before being shown to the user, a naive streaming implementation that displays tokens as they arrive can show an unvalidated or even fabricated citation before that check has had a chance to run. Systems that need both streaming and citation validation typically buffer just the citation-bearing portion of the response, or validate citations against the retrieved set as a fast pre-check before generation starts, rather than trying to validate a citation the user has already seen.
