---
title: "Tool Use and Function Calling"
tags: [agents]
entities: [tool use, function calling, agent, structured output]
created: 2026-01-12
---

Tool use is what lets an agent take real actions in the world — searching, calculating, calling an API, reading a file — rather than only producing text. Function calling is the specific interface mechanism most model providers expose to make this possible: the model is given a set of tool definitions, each with a name, a description, and a schema for its arguments, and instead of answering directly it can emit a structured request to call one of those tools with specific argument values.

The design of the tool interface itself matters as much as whether tool use is enabled at all. Each tool should have exactly one clear purpose rather than a single sprawling tool with a dozen optional parameters covering many unrelated behaviors — a narrowly scoped tool is easier for a model to select correctly and easier for a human to reason about when auditing what an agent actually did. Argument schemas benefit from the same discipline as structured output generally: precise types, required versus optional fields spelled out clearly, and enough description in the schema itself that the model does not have to guess what a parameter means from its name alone.

Function calling only covers the mechanism of requesting an action — the host program executing outside the model is what actually performs the call, checks permissions, and returns a result. This separation is a safety boundary, not just an implementation detail: a model emitting a function call to `delete_file(path="notes/important.md")` has only expressed an intent, and the host program retains full authority to validate, log, rate-limit, or simply refuse to execute that intent before anything irreversible happens.

Tool use is the mechanism an agent's actions flow through on every step, but it is a different concern from the planning loop that decides which tool to call and when — a system can have excellent, well-scoped tools and still behave badly if the surrounding reasoning loop calls them in the wrong order, calls the same one repeatedly without making progress, or never recognizes when the task is actually complete. The interface and the strategy for using it are separate design problems that both need to be right.
