---
title: "Chain-of-Thought Prompting and When It Helps"
tags: [prompting]
entities: [chain of thought, prompt template, multi-hop question, temperature, token budget]
created: 2026-01-08
---

Chain-of-thought prompting asks a model to work through intermediate reasoning steps in its output before giving a final answer, typically by instructing it to "think step by step" or by structuring the prompt to separate a reasoning section from a conclusion section. The effect is to give the model more computation, in the form of additional generated tokens, to work with before it commits to an answer.

Chain-of-thought helps most on tasks that genuinely require multi-step reasoning: arithmetic, logic puzzles, and — directly relevant to a RAG system — multi-hop questions, where the answer depends on combining two separate facts. Writing out "note A says X, note B says Y, therefore the answer is Z" as an explicit intermediate step measurably reduces the rate at which a model skips the second fact entirely and answers from only the first note it noticed.

Chain-of-thought does not reliably help, and can even hurt, on tasks that are simple lookups rather than reasoning problems. Forcing a model to "think step by step" before stating a fact it could have retrieved directly sometimes introduces an opportunity for it to reason itself into a wrong answer that a direct response would have gotten right, and it always costs additional tokens and additional latency for no benefit on questions that never needed the extra steps.

There is a real cost side to weigh against the benefit: every reasoning token generated before the final answer adds to token budget and to end-to-end latency, and if a user-facing product is not designed to hide or summarize the intermediate reasoning, showing raw chain-of-thought output can also just be confusing or overwhelming to read. A common practical pattern is to prompt for reasoning but only surface the final answer and its citations to the user, keeping the reasoning as an internal scratchpad rather than user-visible text.

Whether chain-of-thought is worth the cost is really a question about the query, not a global setting: a system that always forces step-by-step reasoning pays the latency and token cost on every simple factual question just to occasionally help on the harder multi-hop ones, which is why some systems route only genuinely complex questions through a chain-of-thought prompt rather than applying it uniformly.
