---
title: "Multi-Hop Questions and Why They Break Retrieval"
tags: [evaluation]
entities: [multi-hop question, retrieval-augmented generation, chunking, citation, evaluation harness]
created: 2026-01-07
---

A multi-hop question is one whose answer requires combining facts stated in two or more separate notes, where no single chunk contains the complete answer on its own. This is a fundamentally harder retrieval problem than single-fact lookup, and it is worth understanding exactly why it breaks systems that otherwise look like they are working well.

Standard retrieval scores each chunk against the query independently and returns the top matches. For a single-hop question, this works fine — the one chunk containing the answer scores highest and gets retrieved. For a multi-hop question, the query itself often does not mention the second fact at all, because the question was written before knowing which note holds it; the retriever has no way to know it needs to fetch note B until it has already read note A. A single retrieval pass over the raw question frequently pulls only the more obviously relevant of the two or three needed notes and misses the rest, producing an answer that is confidently half-right.

This is precisely why deliberately splitting facts across notes — planting one part of an answer in one note and a related part in another — is a useful stress test for a retrieval-augmented generation system, not just a corpus-authoring inconvenience. It exposes whether a system's retrieval step and its reasoning step actually cooperate, or whether the system quietly assumes one retrieval pass is always sufficient.

Systems that handle multi-hop questions well typically do one of two things: they retrieve more broadly up front (a larger top-k, or a query rewritten to be more general) so multiple relevant notes have a chance of being pulled together, or they reason iteratively — retrieve, notice the answer is incomplete, formulate a follow-up retrieval based on what's still missing, and repeat. The second approach starts to look like an agent's planning loop rather than a single retrieval call, which is one of the reasons agentic patterns show up in RAG systems that need to reliably answer compound questions.

When evaluating multi-hop performance, citation quality becomes especially informative: a correct-sounding answer that cites only one of the two required notes is a strong signal that the system got lucky or hallucinated the missing half, rather than genuinely having synthesized both sources.
