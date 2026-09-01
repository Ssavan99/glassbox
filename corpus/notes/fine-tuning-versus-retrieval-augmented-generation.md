---
title: "Fine-Tuning versus Retrieval-Augmented Generation"
tags: [fine-tuning, retrieval]
entities: [fine-tuning, retrieval-augmented generation, hallucination, context window]
created: 2026-01-09
---

Fine-tuning and retrieval-augmented generation are often framed as competing solutions to the same problem — teaching a model things it did not learn during pretraining — but they solve genuinely different problems and are frequently misapplied to each other's strengths.

Retrieval-augmented generation is the right tool when the underlying need is access to specific facts: private documents, information that changes frequently, or a corpus too large or too fast-moving to ever bake into model weights. Its core advantage is that updating knowledge means updating the corpus, not retraining anything — add a note, and the next query can retrieve it immediately. Its core limitation is that it depends entirely on retrieval actually finding the relevant text and fitting it inside the context window; if retrieval misses, the model has no fallback except its own memorized knowledge or an admission of ignorance.

Fine-tuning is the right tool when the need is behavioral, not factual: teaching a model a particular output format, a particular tone, a particular way of using tools, or a domain-specific skill like writing in a specialized notation. It bakes the change directly into the model's weights, so the behavior is available on every call without needing anything retrieved or supplied in context. Its core limitation is the opposite of RAG's: updating knowledge requires retraining, which is slow, costly, and risks catastrophic forgetting of other capabilities the model previously had.

A common and costly mistake is trying to fine-tune a model to "know" a large, frequently changing body of facts — effectively trying to compress a knowledge base into weights — when retrieval-augmented generation would have solved the same problem more cheaply, more transparently, and with far less risk of hallucination, since a fine-tuned fact can silently go stale in the weights with no way to audit or update it short of retraining again.

In practice the two are complementary rather than exclusive: a model can be fine-tuned to reliably follow a citation format and refuse gracefully when evidence is missing — a behavioral change — while still relying entirely on retrieval-augmented generation for the actual facts it answers with. The decision of which technique to reach for should track whether the gap is "the model doesn't know this fact" versus "the model doesn't behave this way," not which technique is more fashionable.
