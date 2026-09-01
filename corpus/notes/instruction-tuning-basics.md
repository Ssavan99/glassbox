---
title: "Instruction Tuning Basics"
tags: [fine-tuning, prompting]
entities: [fine-tuning, system prompt, prompt template]
created: 2026-01-09
---

Instruction tuning is a fine-tuning stage where a pretrained model is trained on examples of instructions paired with the responses that correctly follow them, rather than on raw text continuation. A base model fresh out of pretraining is good at predicting plausible next text, but it has no particular tendency to treat a prompt as a request to fulfill — instruction tuning is what turns a raw text predictor into a model that reliably behaves like an assistant responding to a user's ask.

The training data for instruction tuning typically consists of thousands to millions of instruction-response pairs spanning many task types: answering questions, summarizing text, following formatting requests, refusing inappropriate requests, and so on. This diversity matters — a model instruction-tuned only on question answering tends to generalize poorly to other instruction types, while broad and varied instruction data produces a model that follows novel instructions it never saw an exact example of during training.

Instruction tuning is what makes system prompts and prompt templates work reliably at all. A model without instruction tuning has no strong prior for treating a "system prompt" section differently from ordinary text, so techniques like role framing or structured output constraints are far less effective on a purely pretrained base model than on an instruction-tuned one, which has specifically learned to treat certain prompt structures as binding instructions rather than as more text to continue.

Most models available through commercial APIs today are already instruction-tuned, which is easy to take for granted, but it explains why prompting techniques developed for one instruction-tuned model often transfer reasonably well to another — they are all exploiting roughly the same learned behavior of treating structured prompts as instructions to follow, even though the specific instruction-tuning data and process differed between them. Fine-tuning a model further on top of an already instruction-tuned base — for a narrower task or house style — inherits this behavior rather than starting from scratch, which is part of why task-specific fine-tuning on top of an instruction-tuned model typically needs far less training data than instruction tuning a raw base model would.
