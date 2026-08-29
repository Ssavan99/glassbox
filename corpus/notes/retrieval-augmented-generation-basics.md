---
title: "Retrieval-Augmented Generation Basics"
tags: [retrieval, rag, architecture]
entities: [retrieval-augmented generation, chunking, embedding model, vector database, hallucination, grounding, citation]
created: 2026-01-05
---

Retrieval-augmented generation (RAG) improves a language model's answers by giving it relevant external text before it responds, rather than relying only on what the model memorized during training. A typical pipeline has four stages: split source documents into chunks, embed each chunk with an embedding model into a vector, store those vectors in a vector database, and at query time retrieve the chunks most similar to the user's question before passing them into the model's prompt.

The core motivation is that base language models are frozen at training time and have no way to know about private notes, yesterday's incident report, or a fast-moving codebase. Retrieval-augmented generation sidesteps this by treating the model as a reasoning engine over supplied evidence rather than a database of facts. This also makes answers auditable: if a chunk is wrong or missing, you can trace the failure back to a specific document instead of debugging opaque model weights.

RAG is most valuable when answers should depend on information that is private, recent, or narrow enough that a general-purpose model was unlikely to have seen much of it. It is a poor fit for questions that require broad world knowledge already well represented in training data, or for tasks needing multi-step arithmetic or code execution rather than fact lookup — those are better served by tools or fine-tuning than by stuffing more text into the prompt.

The quality of a RAG system is bounded by its weakest stage. Poor chunking can split a fact across two chunks so neither one is retrievable alone. A mismatched embedding model can miss a semantically relevant passage that uses different wording than the query. And even with perfect retrieval, a model that ignores its context and answers from memory produces hallucination — a fluent but ungrounded claim — instead of grounding its answer in the retrieved evidence.

Because the failure surface is wide, evaluation has to check more than "does the answer sound right." A trustworthy RAG system should be tested on whether it retrieves the correct evidence, whether its answer is actually grounded in that evidence, whether it produces an accurate citation back to the source, and whether it correctly refuses when the corpus does not contain enough information to answer at all. Each of those is a separate failure mode with a separate fix, and conflating them is one of the most common mistakes in RAG evaluation.
