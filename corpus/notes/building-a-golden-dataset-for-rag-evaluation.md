---
title: "Building a Golden Dataset for RAG Evaluation"
tags: [evaluation]
entities: [golden dataset, evaluation harness, retrieval-augmented generation, multi-hop question, citation]
created: 2026-01-07
---

A golden dataset is a fixed set of questions paired with known correct answers and known supporting evidence, built once and reused as the stable yardstick for every future change to a retrieval-augmented generation system. Its entire value comes from being fixed: if the test set drifts every time you evaluate, you cannot tell whether a score change reflects a real improvement or just a different, easier set of questions.

Building one by hand is slow and that slowness is part of the point — a human author writing golden questions is forced to actually read the corpus closely, which surfaces ambiguities, missing coverage, and near-duplicate notes long before any retrieval code runs. A golden dataset assembled by having a model generate questions from the same corpus it will later be tested on tends to be easier than real questions, because model-generated questions often reuse the source text's exact vocabulary, which flatters both bm25 and dense retrieval in ways a genuinely independent question would not.

A useful golden dataset mixes difficulty deliberately rather than skewing toward easy factual lookups: some entries should be answerable from a single obvious chunk, some should require the multi-hop question pattern of combining facts scattered across two or three separate notes, and some should be intentionally unanswerable from the corpus, to test refusal rather than answer quality. Each entry should also record which note or notes contain the supporting evidence, not just the final answer text — this is what lets an evaluation harness separately score "did we retrieve the right evidence" from "did we synthesize it correctly," which are different failure modes with different fixes.

A golden dataset that never grows becomes stale as a corpus expands, but a golden dataset that changes on every run stops being a stable yardstick — the practical resolution is to version it explicitly, add new entries deliberately when the corpus grows, and keep old entries frozen so historical scores stay comparable across changes to chunking, the embedding model, or the prompt template.
