---
title: "Retrieval Failures: Lost in the Middle"
tags: [failure-modes, retrieval]
entities: [context window, needle in a haystack, prompt template, retrieval metrics]
created: 2026-01-13
---

"Lost in the middle" describes a well-documented pattern where a model's ability to correctly use information degrades based on where that information sits within a long context, independent of whether retrieval itself found the right chunk. Information placed near the very start or the very end of the context window tends to be used reliably; the same information placed in the middle of a long context is used measurably less reliably, even though it is technically present and available to the model the entire time.

This makes lost-in-the-middle a genuinely distinct failure from a retrieval miss, and it is worth being precise about the difference: retrieval metrics like recall@k only measure whether the correct chunk was retrieved at all, and would score a lost-in-the-middle failure as a full success, since the right chunk was in fact present in the retrieved set. The actual failure happens one stage later, in how the prompt template orders that retrieved evidence before handing it to the model — a correctly retrieved fact sitting at position 8 of 10 chunks in the assembled prompt can still fail to influence the answer, not because retrieval failed, but because of where it landed.

This is exactly why a needle in a haystack evaluation needs to test more than raw retrieval: a full test should also vary where the correct chunk lands within the assembled context and check whether answer quality holds up regardless of position, since a system that only ever tests with the correct chunk conveniently placed first will never catch this failure mode at all, and will look deceptively strong in evaluation right up until a real query places the answer-bearing chunk in an unlucky spot.

The mitigating fix belongs in the prompt template, not in retrieval: ordering chunks by relevance rather than by retrieval order (which is not always the same thing once reranking is involved), and, for a small number of high-priority chunks, deliberately placing the single highest-confidence chunk near the start or end of the context rather than trusting that its rank alone guarantees it will be used correctly regardless of position.
