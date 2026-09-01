---
title: "Prompt Engineering as Interface Design"
tags: [prompting, architecture]
entities: [prompt template, system prompt, grounding, citation, hallucination, context window, token budget]
created: 2026-01-05
---

Prompt engineering is best understood as interface design, not incantation. A good prompt tells the model what role to play, what evidence matters, what output shape is expected, and what constraints must hold — the same way a well-designed API tells a caller what inputs are valid and what response shape to expect. Treating a prompt as a contract, rather than a magic phrase, makes it something you can version, test, and debug like any other interface.

A prompt template usually separates three concerns: a system prompt that sets persistent role and constraints ("you are a grounded research assistant, answer only from the provided notes"), a slot for retrieved context, and the user's actual question. Keeping these separate — rather than concatenating everything into one freeform block — makes it much easier to change one piece (say, swapping in stricter grounding language) without breaking the others.

For retrieval-augmented systems specifically, the highest-leverage prompt instruction is usually the one governing what happens when evidence is missing or ambiguous. A prompt that only says "answer the question" invites the model to fill gaps with hallucination — fluent but ungrounded claims — whenever retrieval comes up short. A prompt that explicitly separates "answer," "evidence," and "uncertainty," and instructs the model to say when the retrieved context is insufficient, produces answers that are far more trustworthy even though the underlying model has not changed at all.

Prompt structure also has to respect the context window, the finite span of tokens the model can attend to in one call. Every token spent on boilerplate instructions or verbose retrieved context is a token unavailable for the answer itself, so prompt design is really a token budget allocation problem: how much of the available window goes to instructions, how much to retrieved evidence, and how much is reserved for the model's response. Overstuffing the context window with marginally relevant chunks does not just waste budget — it can actively degrade grounding, because models tend to attend less reliably to information buried in the middle of a long context than to information near the start or end.

Citation instructions deserve their own line in the prompt rather than being assumed. Asking a model to quote or reference the specific note a claim came from turns an unverifiable answer into an auditable one, and is one of the cheapest interventions available for building trust in a personal knowledge system.
