---
title: "Structured Output and JSON Mode"
tags: [prompting, architecture]
entities: [prompt template, function calling, citation, evaluation harness]
created: 2026-01-08
---

Structured output constrains a model to produce text matching a predefined schema — typically JSON with specific required fields — rather than free-form prose. This matters wherever downstream code needs to parse the model's response programmatically, which in a RAG system usually means the answer, its list of citations, and a confidence or refusal flag all need to arrive in a predictable, machine-readable shape rather than embedded loosely in a paragraph.

Some model providers expose a dedicated JSON mode that constrains generation at the decoding level, guaranteeing syntactically valid JSON output. Others rely on prompt instructions alone — describing the desired schema in the system prompt and asking the model to comply — which is less reliable and occasionally produces malformed output, especially on longer or more complex schemas, that downstream code then has to handle defensively with a parsing fallback rather than assuming success.

Structured output is close cousins with function calling: both constrain the model to emit a specific shape rather than open text, and both exist so that a program, not a human, consumes the output directly. The difference is intent — function calling signals "call this tool with these arguments," while structured output signals "here is my final answer, shaped this way." A RAG system's final response often benefits from structured output specifically so that citations can be validated programmatically: a `citations` field listing note ids can be checked against the actual retrieved set, catching a fabricated citation automatically rather than relying on a human or judge model to notice it.

The tradeoff is expressiveness: forcing a rigid schema can make it awkward for a model to express genuine partial answers or nuanced hedging that does not fit neatly into a fixed field. A well-designed schema anticipates this by including an explicit `confidence` or `sufficient_evidence` field rather than forcing every answer into a binary "answered or not," so uncertainty has a legitimate place to live in the structured output instead of getting flattened away.

Structured output is also what makes an evaluation harness's job considerably easier: comparing a parsed `answer` field and a parsed `citations` list against a golden dataset entry is far more reliable than trying to extract the same information from unstructured prose with a regex or a second model call.
