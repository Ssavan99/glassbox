---
title: "Full Fine-Tuning vs Adapters"
tags: [fine-tuning]
entities: [lora, fine-tuning, distillation]
created: 2026-01-09
---

Choosing between full fine-tuning and an adapter method like LoRA is a decision with a concrete numeric tradeoff, not just a matter of convenience. Full fine-tuning updates every parameter in the model, which gives it the largest possible hypothesis space to adapt to a new task and, in most published comparisons, a small but real edge in final task performance — typically a modest quality gap in favor of full fine-tuning on tasks that are substantially different from anything in the base model's pretraining distribution.

The cost of that edge is steep. Full fine-tuning requires storing gradients and optimizer state for every parameter, which for a large model can mean several times the memory footprint of the model weights alone, and it produces a completely separate full-size model checkpoint for every task or variant trained — there is no sharing between them. LoRA and other adapter methods train under 1% of the parameters, need a fraction of the GPU memory, and let many task-specific adapters share one frozen base model, at the cost of that small quality gap and a hypothesis space constrained by the chosen adapter rank.

In practice, the quality gap between LoRA and full fine-tuning narrows or disappears for tasks that are close to what the base model already does reasonably well — teaching a consistent citation format, a specific tone, or a narrow output schema — and widens for tasks that require the model to acquire substantially new capability far outside its pretraining distribution. This means the right choice depends on how large a behavioral change is actually being asked for, not just on available hardware budget.

A middle path worth knowing about is knowledge distillation, covered separately, which is a different technique entirely — it trains a smaller model to imitate a larger one's outputs, rather than adapting one model's own weights to a new task. Distillation and adapter methods are sometimes combined: a large model is fine-tuned or prompted well on a task, then a smaller model is distilled from its outputs to get similar behavior at a fraction of the serving cost.

For most personal or small-team projects, the practical default is to reach for LoRA first and escalate to full fine-tuning only if a measured evaluation gap actually justifies the added memory and storage cost — treating full fine-tuning as the default is rarely justified by the marginal quality gain most tasks will actually see.
