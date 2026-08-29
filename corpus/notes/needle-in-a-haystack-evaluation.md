---
title: "Needle in a Haystack Evaluation"
tags: [evaluation]
entities: [needle in a haystack, evaluation harness, retrieval metrics, context window, chunking]
created: 2026-01-07
---

A needle in a haystack evaluation tests whether a retrieval system can find one small, specific piece of information when the corpus also contains many other notes that are topically similar but do not actually contain the answer. This is a precision test, not a recall test: the failure mode it catches is a retriever that reliably surfaces "something relevant" without surfacing the one chunk that actually answers the question, because several near-duplicate decoys are competing for the same ranked slots.

This is different from testing raw retrieval accuracy on an easy factual question, because an easy question usually has only one obviously relevant note in the whole corpus — there is no real competition for top rank. A needle in a haystack test is deliberately constructed so that competition exists: several notes share vocabulary, cluster, and surface framing, and only one of them actually contains the specific detail the question asks for. This is exactly the situation decoy notes in a corpus are designed to create, and it is why documenting decoy pairs explicitly matters when building an evaluation set.

A second, related variant tests context window placement rather than corpus-level distraction: given a long context window stuffed with retrieved chunks, does the model's answer quality depend on whether the correct chunk sits near the start, the end, or buried in the middle of that context? Many models show measurably worse recall for facts placed in the middle of a long context compared to facts near either edge — a pattern sometimes called "lost in the middle." This means even correct retrieval can still produce a wrong answer if the retrieved chunks are ordered carelessly before being inserted into the prompt.

Needle in a haystack results are worth tracking separately from overall evaluation accuracy, because a system can score well in aggregate while still failing badly whenever a query's answer happens to live in a crowded region of the corpus — exactly the queries a real user is most likely to ask as a personal knowledge base grows and topics start to overlap.
