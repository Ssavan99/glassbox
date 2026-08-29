---
title: "Hallucination from Missing Context"
tags: [failure-modes]
entities: [hallucination, grounding, retrieval-augmented generation, refusal]
created: 2026-01-13
---

The most common cause of hallucination in a retrieval-augmented system is simple: retrieval fails to surface the evidence needed to answer the question, and the model, rather than admitting it lacks the necessary information, falls back on its own pretrained knowledge or pattern-completes a plausible-sounding answer anyway. This is a retrieval failure with a generation-layer symptom — the actual bug is upstream, but it only becomes visible once the model fills the gap with an ungrounded claim instead of surfacing the gap itself.

This can happen for several distinct retrieval reasons that are worth distinguishing when diagnosing it: the relevant note genuinely does not exist in the corpus, the note exists but chunking split the needed fact across a boundary so no single chunk contains it whole, or the note and chunk exist and are correctly indexed but the query's phrasing was different enough from the note's wording that dense retrieval missed it and no keyword overlap existed for bm25 to catch it either. Each of these has a different fix — adding the missing note, adjusting chunk overlap, or improving hybrid search — so treating "hallucination happened" as one undifferentiated bug rather than tracing it back to its specific retrieval cause wastes debugging effort on the wrong stage.

The generation-layer half of the fix is independent of the retrieval-layer half: even with retrieval working perfectly, a model still needs an explicit instruction, enforced through the prompt template's citation contract, that missing or insufficient evidence should produce a refusal rather than a confident guess. A model without that instruction will often hallucinate even when retrieval genuinely found nothing relevant, simply because it defaults toward being maximally helpful rather than toward declining.

Distinguishing this failure mode from a different but easily confused one matters: hallucination from missing context is a retrieval-and-refusal problem, whereas hallucination triggered by an adversarial prompt is a fundamentally different attack-surface problem covered separately — the fix for one does nothing to address the other, and conflating the two in a postmortem tends to produce a fix that solves neither.
