---
title: "AI Evaluation for Personal Knowledge Bases"
tags: [evaluation, architecture]
entities: [evaluation harness, golden dataset, multi-hop question, needle in a haystack, citation, grounding, retrieval-augmented generation]
created: 2026-01-05
---

Testing a personal RAG system requires more than checking whether an answer sounds plausible. A useful evaluation harness needs several distinct question types: factual questions with one clear answer, vague questions that test whether the system asks for clarification instead of guessing, multi-hop questions whose answer requires combining facts from two or more separate notes, and impossible questions where the only correct behavior is admitting the corpus does not contain enough information to answer.

These question types are not interchangeable, and scoring them the same way hides real failures. A system can score well on simple factual questions purely because dense retrieval is good at matching obvious keyword overlap, while quietly failing every multi-hop question because no single retrieved chunk ever contains the full answer. Separating scores by question type is what turns an aggregate accuracy number into an actionable debugging signal.

A well-built golden dataset — a fixed set of questions with known correct answers and known supporting evidence — is the backbone of this kind of evaluation. Building one by hand is slow but worth it: it lets you re-run the same fixed test every time you change chunking, the embedding model, or the prompt template, and see whether the change actually helped or just shuffled which questions pass. Without a golden dataset, "we improved retrieval" is an opinion; with one, it is a measurable claim.

One specific and underrated test is the needle in a haystack query, where a small note contains the answer to a question, but many other similar notes exist to distract the retriever. This directly measures precision, not just recall — a system that "finds something relevant" every time is not the same as a system that finds the actual needle when near-duplicate decoys are sitting right next to it in the corpus.

A practical evaluation harness tracks several signals side by side rather than one blended score: retrieval accuracy (did the right chunk get retrieved), answer correctness, citation quality (does the cited source actually support the claim), refusal behavior (does the system decline when it should), and latency. Good evaluation turns a RAG system from something that merely sounds convincing into something whose behavior you can actually predict and trust — which matters more the moment the corpus grows past what one person can eyeball.
