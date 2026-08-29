---
title: "Few-Shot Prompting for Grounded Answers"
tags: [prompting]
entities: [few-shot prompting, prompt template, grounding, citation, token budget]
created: 2026-01-08
---

Few-shot prompting means including a small number of complete example input-output pairs directly in the prompt, so the model can infer the desired format and behavior from demonstration rather than from instructions alone. For a retrieval-augmented system, this typically means showing one or two examples of a question, some retrieved context, and a correctly grounded answer with proper citations, before presenting the model with the real question.

The mechanism behind why this works is pattern completion: a language model is very good at continuing a pattern it can see, and often much better at that than at correctly interpreting an abstract instruction like "cite your sources properly." A single well-chosen example showing exactly what a properly cited, appropriately hedged answer looks like tends to shift the model's output format more reliably than a paragraph of prose describing the same requirement.

The cost of few-shot prompting is token budget: each example consumes real space in the context window, competing directly with the retrieved evidence the model actually needs to answer the current question. This creates a genuine tradeoff in a RAG prompt specifically, where context window space is already contested between instructions, retrieved chunks, and the answer itself — a prompt with three verbose few-shot examples has measurably less room for retrieved evidence than one with a single tight example or none at all.

Few-shot examples are most valuable for behaviors that are hard to specify precisely in words: the exact tone of an appropriate refusal, the exact format for interleaving a claim with its citation, or how to handle a partially-answerable question gracefully. For behaviors that are simple to state directly — "always answer in English," "keep answers under 200 words" — a plain instruction in the system prompt is usually just as effective and costs far fewer tokens than a demonstration.

Few-shot prompting should not be confused with chain-of-thought prompting, covered separately: few-shot changes what the model sees as example output shape, while chain-of-thought changes how the model is asked to reason before producing that output — the two are frequently combined but solve different problems.
