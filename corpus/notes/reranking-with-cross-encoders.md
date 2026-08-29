---
title: "Reranking with Cross-Encoders"
tags: [retrieval, search]
entities: [reranking, cross-encoder, cosine similarity, latency, embedding model]
created: 2026-01-06
---

Reranking is a second retrieval pass applied after an initial fast retrieval step has already narrowed the corpus down to a shortlist of candidates, typically a few dozen chunks pulled by embedding cosine similarity or hybrid search. Its job is to re-score just those candidates more carefully before the final top-k is chosen for the model's prompt.

The reason reranking exists at all is that the embedding model used for initial retrieval scores a query and a document independently — it encodes each into a vector separately and compares them afterward with cosine similarity, a bi-encoder architecture. This is fast and scales to a huge corpus, but it never lets the query and the candidate document actually attend to each other while being scored. A cross-encoder does the opposite: it takes the query and one candidate document together as a single joint input and produces one relevance score directly, letting the model compare specific words and phrases between the two texts rather than comparing two independently-computed summaries. This engine uses `cross-encoder/ms-marco-MiniLM-L-6-v2` as its reranking model.

Cross-encoder scoring is meaningfully more accurate than bi-encoder cosine similarity because it can pick up on fine-grained relevance signals — negation, exact entity matches, whether a passage answers the specific sub-question asked rather than just discussing the same general topic — that get lost when query and document are compressed into separate vectors ahead of time. In practice this catches cases where the top result by cosine similarity is topically close but does not actually answer the question, while a lower-ranked candidate does.

The catch is cost: a cross-encoder requires one full forward pass through the model per query-document pair, so reranking cannot run over an entire corpus the way initial retrieval does — it only makes sense as a second pass over a small shortlist, and even then it adds real, measurable latency compared to the near-instant cosine similarity lookup that produced the shortlist in the first place. The exact size of that latency cost, and why it matters for pipeline design, is covered in a separate note on latency budgets — reranking is a precision improvement that has to be paid for out of the same latency budget as everything else in the request.
