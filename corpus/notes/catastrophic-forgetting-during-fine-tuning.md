---
title: "Catastrophic Forgetting During Fine-Tuning"
tags: [fine-tuning, failure-modes]
entities: [fine-tuning, lora, drift]
created: 2026-01-09
---

Catastrophic forgetting is what happens when fine-tuning a model on a new, narrow task degrades capabilities it previously had, because the training process pushes the weights away from configurations that supported the old behavior in order to better fit the new one. A model fine-tuned heavily on customer-support tone, for instance, may become noticeably worse at general reasoning or coding tasks it handled fine before fine-tuning even began — capability lost as a side effect, not intentionally traded away.

The risk scales with how narrow and how intensive the fine-tuning is. Training on a small, repetitive dataset for many epochs is the classic recipe for catastrophic forgetting: the model has strong, repeated pressure to specialize toward the narrow distribution of the fine-tuning data, and comparatively little counter-pressure keeping its broader pretrained capabilities intact. Full fine-tuning, which updates every parameter, is generally more prone to this than LoRA and other adapter methods, since freezing the base weights and only training a small added component naturally limits how far the model's overall behavior can drift from its starting point.

Catastrophic forgetting is a specific instance of a broader concept worth naming: drift, the general phenomenon of a system's behavior changing in unintended ways from what it originally did, whether from fine-tuning, prompt changes, or a shifting corpus. Fine-tuning-induced drift is unusually dangerous because it is silent — nothing in the fine-tuning process itself flags that a previously reliable capability just got worse, and it typically only surfaces later when a user hits an edge case the fine-tuned model can no longer handle.

The practical mitigation is evaluation discipline: running a broad-coverage regression test, not just the narrow task the fine-tuning targeted, before and after every fine-tuning run, so a capability regression is caught immediately rather than discovered by a confused user weeks later. Mixing a small amount of general-purpose training data into the fine-tuning set, and preferring a lower learning rate and fewer epochs over aggressive training, are also standard mitigations that trade a bit of task-specific performance for meaningfully less collateral damage elsewhere.
