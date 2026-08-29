---
title: "Reducing Latency with Quantization"
tags: [serving, latency]
entities: [quantization, latency, throughput]
created: 2026-01-10
---

Quantization reduces the numerical precision used to store a model's weights — from 32-bit or 16-bit floating point down to 8-bit integers, or even lower with more aggressive schemes — trading a small amount of numerical precision for a large reduction in memory footprint and, often, faster compute.

The latency benefit of quantization comes from two compounding effects. First, smaller weights mean less data to move between GPU memory and the compute units on every forward pass, and for large models this memory movement — not raw arithmetic — is frequently the actual bottleneck, so shrinking the weights directly speeds up inference. Second, some hardware has dedicated fast paths for lower-precision arithmetic, so an 8-bit operation can execute faster than the equivalent 32-bit one even setting aside the memory savings.

The concrete numbers are worth internalizing: moving from 32-bit floating point weights to 8-bit integer weights cuts memory footprint by roughly 4x, and moving to 4-bit schemes cuts it further to roughly 8x relative to full precision. This is not free — more aggressive quantization introduces more numerical error into every computation, and beyond a certain point that error measurably degrades output quality, particularly on tasks requiring precise reasoning or exact recall of learned facts. 8-bit quantization is generally considered a safe default with minimal quality loss on most tasks; 4-bit quantization starts to show a noticeable quality gap on harder tasks, though it remains a common choice when memory is the binding constraint.

Quantization is a different lever from batching for the same underlying goal of serving models efficiently: batching improves throughput by processing many requests together on unchanged hardware, while quantization improves both the per-request latency and the memory footprint by changing how the model itself is stored and computed. The two are complementary and are routinely combined in production serving stacks — a quantized model that also serves batched requests gets both benefits at once, and neither technique substitutes for the other, since one addresses request scheduling and the other addresses model representation.
