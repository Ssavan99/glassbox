---
title: "When Fine-Tuning Is the Wrong Tool"
tags: [fine-tuning]
entities: [fine-tuning, retrieval-augmented generation, prompt template, hallucination]
created: 2026-01-09
---

Fine-tuning is expensive to iterate on relative to prompting or retrieval changes: every adjustment requires a new training run, a new evaluation pass, and a real risk of catastrophic forgetting, compared to editing a prompt template and re-running the golden dataset in seconds. This asymmetry means fine-tuning should be the tool reached for last, once cheaper interventions have genuinely been exhausted, not the first instinct when a system underperforms.

A frequent misapplication is fine-tuning a model to memorize facts that would be far better served by retrieval-augmented generation — a knowledge base, a changing set of prices, a company's current policies. Baking facts into weights through fine-tuning makes them expensive to update, impossible to audit at inference time, and prone to the model hallucinating a plausible-sounding but subtly wrong version of a fact it only partially memorized, whereas retrieval-augmented generation keeps the same facts in an editable, inspectable corpus and lets the model quote them directly.

A second common misapplication is fine-tuning to fix a behavior that a prompt template change would have solved just as well. If a model is not citing sources correctly, the first thing worth trying is a clearer instruction and a demonstration in the prompt — not committing to a training run — because the prompt change is reversible in seconds and testable immediately against the golden dataset, while a fine-tuning run commits real time and risks introducing a new problem (catastrophic forgetting) to solve an old one.

Fine-tuning earns its cost when the target behavior genuinely cannot be reached through prompting or retrieval: a highly specific output format that a model reliably fails to follow no matter how the prompt is worded, a domain-specific skill like a rare notation or code dialect the base model barely saw in pretraining, or a latency requirement where even a well-crafted long prompt costs too many tokens per request compared to a model that has the behavior fine-tuned directly in and needs a much shorter prompt to invoke it.

The practical rule of thumb: exhaust prompt template iteration and retrieval-augmented generation first, measure the remaining gap against the golden dataset, and only fine-tune once that gap is real, specific, and something no amount of prompting has closed.
