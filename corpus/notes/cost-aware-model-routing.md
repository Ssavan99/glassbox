---
title: "Cost-Aware Model Routing"
tags: [serving, latency]
entities: [latency, throughput, fine-tuning, evaluation harness, batching, quantization, distillation]
created: 2026-01-10
---

Cost-aware model routing sends different requests to different models based on how much capability the request actually needs, rather than sending every request to the single largest, most expensive, or slowest model available by default. A simple factual lookup that a small model can answer correctly does not need the same model as a genuinely hard multi-hop synthesis question, and routing both to the same large model wastes cost and latency budget on the easy majority of requests to accommodate the hard minority.

A common routing design uses a small, fast classifier — sometimes just a lightweight model, sometimes a rule-based heuristic on query features — to estimate query difficulty before dispatching to a generation model, then sends easy queries to a smaller or cheaper model and only escalates to a larger model when the classifier signals higher difficulty or when the smaller model's own response indicates low confidence or an explicit refusal. This mirrors how this project's own configuration distinguishes a fast local model, `OLLAMA_MODEL = "qwen2.5:7b-instruct"`, from a larger hosted one, `GROQ_MODEL = "llama-3.3-70b-versatile"`, for different stages or difficulty tiers of a request.

Routing decisions have to be validated against the golden dataset the same way any other pipeline change is, because a routing heuristic that misclassifies a hard question as easy silently degrades answer quality for exactly the queries where quality matters most — a routing error is invisible in aggregate latency or cost metrics, and only shows up as an accuracy regression on the harder slice of the evaluation set if that slice is tracked separately.

The throughput benefit of routing compounds with batching and quantization rather than replacing them: routing controls which model handles a request, while batching and quantization control how efficiently that chosen model is served once selected. A well-designed serving stack applies all three together — route to the smallest sufficient model, batch requests to that model efficiently, and serve it in a quantized form — rather than treating them as alternative solutions to the same cost problem.

Distillation is a related but different lever worth distinguishing from routing: routing picks an existing model per request, while distillation creates a new, smaller model in the first place by training it to imitate a larger teacher. A routing tier's "small model" option is frequently a distilled model rather than a separately trained one, which is one of the reasons the two techniques tend to show up together in a cost-optimized serving stack.
