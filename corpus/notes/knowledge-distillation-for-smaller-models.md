---
title: "Knowledge Distillation for Smaller Models"
tags: [fine-tuning, serving]
entities: [distillation, fine-tuning, latency, throughput]
created: 2026-01-09
---

Knowledge distillation trains a smaller "student" model to imitate the outputs of a larger "teacher" model, rather than training the student directly on raw labeled data. In its simplest form, the teacher generates outputs (or full probability distributions over its output vocabulary) for a set of inputs, and the student is trained to match those outputs as closely as possible. The student ends up capturing much of the teacher's behavior in a fraction of the parameter count.

Distillation is fundamentally a serving-cost optimization, not a capability-improving technique — a well-distilled student rarely exceeds its teacher's quality, and the goal is instead to get most of the teacher's quality at a much lower latency and throughput cost. A smaller student model runs faster per token, fits on cheaper or more available hardware, and can serve substantially more concurrent requests than the original large teacher, which matters directly for any production system with real request volume.

Distillation differs from fine-tuning a base model on a narrow task in what it is actually targeting: fine-tuning adapts one model's own weights to perform a specific task better, while distillation transfers a *different, larger* model's general behavior into a smaller architecture entirely. The two are complementary rather than competing — a common pipeline first fine-tunes or carefully prompts a large teacher model until its behavior on a target task is strong, then distills that behavior into a small student that is cheap enough to actually deploy at scale.

The main risk in distillation is that the student inherits not just the teacher's strengths but also its blind spots and biases, amplified by the compression — a smaller model has less capacity to smooth over edge cases the teacher handled adequately, so distilled models often show a wider quality gap on rare or unusual inputs than on the common cases the training data was dominated by. This is why a distilled model deserves its own evaluation pass against a golden dataset rather than being assumed equivalent to its teacher, especially on multi-hop or edge-case questions where the smaller model's reduced capacity is most likely to show.
