---
title: "Prompt Templates for Retrieval-Augmented Answers"
tags: [prompting, architecture]
entities: [prompt template, retrieval-augmented generation, context window, citation, token budget]
created: 2026-01-08
---

A prompt template is the reusable skeleton a RAG system fills in on every request: a system prompt section, a slot for retrieved chunks, and a slot for the user's question, assembled the same way every time so behavior stays consistent across queries. Treating this as an actual template — with named, testable slots — rather than string-concatenating pieces ad hoc in application code is what makes prompt changes reviewable and their effects measurable against a golden dataset.

The retrieved-context slot deserves particular care in how it formats each chunk. Including the source note's title and a stable identifier alongside each chunk's text, rather than pasting in raw text with no provenance, is what makes citation possible at all — a model cannot cite a source it was never shown the identity of. A common template pattern numbers each chunk and instructs the model to reference that number directly in its answer, which produces citations that are simple to verify programmatically against the actual retrieved set.

Chunk ordering within the template also matters, not just chunk selection. As covered in the note on needle in a haystack evaluation, models attend less reliably to information buried in the middle of a long context window than to information near the beginning or end, so a template that always places the highest-ranked chunk first — rather than in retrieval order that might not match relevance order after reranking — gets a small but real accuracy improvement for free.

Token budget allocation is the other core design decision baked into a template: how many chunks to include, how long each chunk is allowed to be, and how much room is reserved for the system prompt and the model's own answer. A template that greedily includes every retrieved chunk regardless of the running token count will eventually either truncate mid-chunk in an unpredictable way or exceed the context window outright; a well-designed template enforces a hard budget and drops the lowest-ranked chunks first rather than truncating an included chunk mid-sentence.

Because the template touches grounding, citation, and token budget simultaneously, small wording changes to it should be evaluated the same way any other pipeline change is — against the golden dataset, tracking citation quality and refusal behavior specifically, not just overall answer correctness.
