---
title: "LoRA and Parameter-Efficient Fine-Tuning"
tags: [fine-tuning]
entities: [lora, fine-tuning, quantization]
created: 2026-01-09
---

LoRA, short for low-rank adaptation, is a parameter-efficient fine-tuning method that freezes the original model's weights entirely and instead trains a pair of small, low-rank matrices injected alongside each frozen weight matrix. Instead of updating every parameter in the model during training, LoRA updates only these small added matrices, then combines their output with the frozen original weights at inference time.

The idea rests on the observation that the *change* needed to adapt a large pretrained model to a new task tends to have much lower effective rank than the full weight matrix itself — the update does not need nearly as many degrees of freedom as the original model has. By constraining the trainable update to a low-rank decomposition, LoRA captures most of the benefit of full fine-tuning while training a tiny fraction of the total parameter count, often well under 1% of the base model's parameters, depending on the chosen rank.

This has direct practical consequences beyond just training speed. Because the frozen base weights are shared, a single base model can serve many different LoRA adapters — one per task or per customer — swapped in and out at inference time, without needing to store a full separate copy of the model for each variant. Training also needs far less GPU memory than full fine-tuning, since gradients and optimizer state only need to be tracked for the small adapter matrices rather than the entire model.

LoRA adapters are commonly combined with quantization of the frozen base model — loading the large frozen weights in a lower-precision format to save memory, while still training the small LoRA matrices in full precision — a combination that pushes fine-tuning within reach of much more modest hardware than full-precision full fine-tuning would require.

The specific rank chosen for the low-rank matrices, and the tradeoff between using LoRA versus full fine-tuning at all, are decisions with real numeric consequences covered in a separate note — LoRA's parameter efficiency is not free, and knowing when the gap in output quality actually matters is a distinct question from understanding the mechanism itself.
