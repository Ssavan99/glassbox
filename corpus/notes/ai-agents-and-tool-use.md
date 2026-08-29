---
title: "AI Agents and Tool Use"
tags: [agents, architecture]
entities: [agent, tool use, function calling, planning loop, memory, guardrails, trace]
created: 2026-01-05
---

An AI agent combines a language model with tools, memory, and a planning loop, letting it decide when to search, calculate, call an API, read a file, or ask for clarification rather than emitting a single response. The core pattern is a loop: observe the goal, reason about the next step, act through a tool, inspect the result, and continue until the task is done or the agent decides to stop. This loop is what separates an agent from a plain chatbot — the model is not just answering, it is choosing actions.

Tool use, sometimes exposed to the model as function calling, is the mechanism that lets the model request an action rather than only produce text. The model emits a structured call — a tool name and arguments — the host program executes it outside the model, and the result is fed back into the conversation for the next reasoning step. Good agent design depends on tight tool boundaries: each tool should have one clear purpose, a predictable input schema, and a safe, legible failure mode. A tool that silently returns malformed data on error is far more dangerous than one that throws a clear exception, because the model may not notice anything went wrong and will happily reason forward from garbage.

The planning loop itself needs bounds. An unbounded agent can spiral into repeating the same failed tool call, or chase an increasingly irrelevant subgoal. Production agents typically cap the loop with a maximum number of steps and a maximum number of model calls, and treat hitting that cap as a defined failure state to report rather than an infinite retry.

Agent memory is a separate concern from the planning loop: it is what persists across steps, or across sessions, so the agent does not have to re-derive context it already gathered. Memory can be as simple as the running transcript of the current task, or as involved as a store the agent explicitly writes to and queries. Poorly scoped memory causes its own failure mode — an agent that "remembers" stale information from an earlier step and treats it as still true.

Because agents take real actions, not just generate text, they need guardrails beyond what a chatbot needs: logging every step, permission checks before risky actions, rate limits, and human approval for anything irreversible such as sending a message, moving money, or deleting data. A trace of every node in the agent's reasoning and action path — what it decided, what tool it called, what came back — is what makes an agent's behavior debuggable after the fact instead of an unexplainable black box.
