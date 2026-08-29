---
title: "Context Window Overflow and Truncation"
tags: [failure-modes]
entities: [context window, token budget, prompt template, hallucination]
created: 2026-01-13
---

Context window overflow happens when the total tokens a request needs — system prompt, retrieved chunks, conversation history, and reserved space for the answer — exceeds the model's maximum context length. What happens next depends entirely on how the calling code handles it, and a poorly handled overflow produces some of the most confusing failures in a RAG system, because the resulting bad answer gives no obvious signal that overflow was the actual cause.

The naive failure mode is a hard error: the API call itself fails once the token count exceeds the limit, with an error like `This model's maximum context length is 8192 tokens. However, your messages resulted in 9147 tokens` — at least this failure is loud and immediately traceable to its cause, which makes it the easiest overflow scenario to debug even though it is the one that looks worst to an end user in the moment.

The more dangerous failure mode is silent truncation: some client libraries or custom prompt-assembly code will quietly cut the prompt down to fit, dropping whatever content did not make the cut — often the end of the prompt, which for a naive template can mean the model's actual instructions or the user's question itself get truncated away while the retrieved context survives intact. A model responding to a truncated prompt does not know anything was cut; it answers the truncated version as if it were complete, producing an answer that looks like ordinary hallucination or a strange misunderstanding of the question, when the real cause was a token budget failure several layers upstream of generation.

The practical defense is enforcing the token budget deliberately in the prompt template itself, before assembly, rather than discovering overflow reactively at the API boundary: count tokens for the fixed parts of the prompt (system instructions, question) first, reserve them unconditionally, then fill the remaining budget with retrieved chunks in priority order, dropping the lowest-ranked whole chunks first rather than truncating a partially-included one mid-sentence. This keeps a truncation event, if it happens at all, confined to dropping the least-relevant evidence rather than silently corrupting the parts of the prompt that were supposed to be non-negotiable.
