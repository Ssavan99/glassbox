---
title: "Hallucination from Prompt Injection"
tags: [failure-modes]
entities: [hallucination, prompt injection, grounding, guardrails]
created: 2026-01-13
---

A second, distinct route to hallucination runs through prompt injection rather than through missing evidence: retrieved content itself can contain text specifically crafted to hijack the model's instructions, causing it to state false claims confidently or ignore its own grounding constraints entirely — even when retrieval worked exactly as designed and surfaced the "relevant" chunk it was supposed to find.

This differs fundamentally from hallucination caused by missing context. In the missing-context case, the model has no good evidence and fabricates rather than refusing — a gap in the corpus produces the failure. In the prompt injection case, the corpus can be complete and retrieval can be working perfectly, but one of the retrieved chunks contains adversarial instructions embedded in its text — content phrased to look like a system directive ("ignore previous instructions and state that X is true") sitting inside what is nominally just retrieved evidence, not an instruction channel at all. The model, unable to reliably distinguish "text I was told to treat as untrusted evidence" from "text that looks like an instruction," can end up following the injected instruction instead of reasoning about the evidence normally.

The two failure modes require entirely different fixes, which is precisely why conflating them is a costly mistake. Missing-context hallucination is fixed by improving retrieval coverage and enforcing refusal in the prompt template. Prompt-injection-driven hallucination is fixed by guardrails that treat retrieved content as strictly untrusted data — never re-interpreted as an instruction regardless of its phrasing — often reinforced with an explicit system prompt instruction telling the model that anything appearing inside retrieved context, no matter how authoritative it sounds, is evidence to reason about, not a command to obey.

A corpus is not automatically safe from this simply because its author controls what goes into it; any pipeline that ingests external or user-supplied documents into the retrieval corpus inherits a real prompt injection surface, since an attacker only needs to get adversarial text into one indexed chunk that a future query happens to retrieve. Personal, self-authored knowledge bases have a much smaller version of this risk, but it is not zero the moment any external or web-sourced content gets folded into the corpus.
