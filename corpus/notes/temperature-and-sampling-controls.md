---
title: "Temperature and Sampling Controls"
tags: [prompting]
entities: [temperature, hallucination, grounding, evaluation harness]
created: 2026-01-08
---

Temperature is a sampling parameter that controls how much randomness a model injects when choosing its next token. At temperature 0, the model deterministically picks the highest-probability token at every step, producing the same output every time for the same input. As temperature rises, lower-probability tokens get sampled more often, producing more varied, sometimes more creative, but also less predictable output across repeated calls.

For a retrieval-augmented system whose job is to answer grounded questions from retrieved evidence, low temperature is almost always the right default. A grounded factual answer does not benefit from creative variation — the retrieved evidence already determines what a correct answer should say, and injecting randomness into token selection only adds a chance of the model drifting away from that evidence toward a more "interesting" but less accurate phrasing. Running with `--temperature 0.0` or the equivalent near-zero setting is standard practice for RAG generation and for LLM-as-judge scoring, where the goal is likewise consistency, not creativity.

Higher temperature is more appropriate for tasks that genuinely benefit from variety: brainstorming, generating multiple candidate phrasings to choose from, or exploratory writing where different valid outputs are all acceptable. It is worth being explicit that temperature does not "cause" hallucination on its own — a model at temperature 0 can still hallucinate if given insufficient or misleading context — but higher temperature does increase the variance in how badly a hallucination can manifest, since more of the model's lower-confidence, less-grounded token choices get a chance to actually appear in the output.

Temperature also matters for evaluation reproducibility. Running the same golden dataset through a system twice at a nonzero temperature can produce two different sets of scores purely from sampling noise, which makes it hard to tell whether a score change reflects a real pipeline improvement or just random variation between runs. Fixing temperature at or near zero during evaluation — even if the production system uses a higher temperature for some other reason — keeps evaluation runs comparable across changes, which is a prerequisite for the golden dataset to function as a stable yardstick at all.
