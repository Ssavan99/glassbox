---
title: "LLM-as-Judge Evaluation Pitfalls"
tags: [evaluation]
entities: [evaluation harness, golden dataset, hallucination, grounding, temperature]
created: 2026-01-07
---

Using a language model to grade another model's answers — LLM-as-judge — is an appealing shortcut when a golden dataset has grown too large to score by hand, but it inherits its own set of systematic failure modes that a raw accuracy number will not reveal on its own.

The best-documented pitfall is position bias: when a judge model is shown two candidate answers side by side and asked which is better, it tends to favor whichever answer appears first in the prompt, independent of actual quality. Swapping the order of the two answers and averaging the judgment, rather than trusting a single ordering, is a cheap and necessary mitigation that many quick evaluation setups skip.

A second pitfall is verbosity bias: judge models tend to rate longer, more elaborated answers as better even when a shorter answer is equally correct and more appropriately concise for the question asked. This actively rewards models that pad their responses, which is the opposite of what a grounded, citation-disciplined RAG system should be optimizing for — a system that hedges and over-explains to game a verbose-favoring judge is not actually more trustworthy.

A third, more subtle pitfall is that an LLM judge can be fooled by the same fluent hallucination it is supposed to catch. A confidently worded but ungrounded answer often reads, to another model, as more convincing than a correctly hedged answer that admits uncertainty — the exact quality a grounded system should reward gets penalized by a judge that is itself just pattern-matching on fluency. This is why LLM-as-judge scoring works best as a scalable complement to a smaller set of hand-checked golden dataset entries, not a full replacement for them — the hand-checked subset is what lets you notice when the judge itself has drifted from what a careful human would actually conclude.

Running the judge model at a low temperature and giving it an explicit rubric — specific criteria to check off rather than an open-ended "rate this answer" — measurably reduces both position and verbosity bias, though it does not eliminate either one.
