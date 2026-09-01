---
title: "Multi-Agent Systems and Handoffs"
tags: [agents]
entities: [agent, planning loop, tool use, memory]
created: 2026-01-12
---

A multi-agent system splits a task across several specialized agents rather than relying on one general-purpose agent to handle everything within a single planning loop. A common pattern assigns one agent to plan and coordinate at a high level, and hands off well-defined subtasks to narrower agents that each have a tighter tool set and a more focused prompt — a research subtask goes to an agent with search and retrieval tools, a coding subtask goes to an agent with file and execution tools, and so on.

The motivation is similar to why narrowly scoped tools tend to outperform one sprawling tool: a narrowly scoped agent, with a tight, relevant tool set and a focused system prompt, tends to perform its specific subtask more reliably than a single general agent juggling every possible tool and context simultaneously, especially as the total number of available tools grows large enough that tool selection itself becomes error-prone.

The handoff between agents is where most of the real design difficulty lives. A handoff has to pass along enough context for the receiving agent to act correctly — the relevant part of the task, any constraints already established, results already gathered — without dumping the entire coordinating agent's full memory and transcript into the subagent's context window, which would defeat the purpose of narrowing scope in the first place and blow through the receiving agent's token budget on irrelevant history.

Coordination failures in multi-agent systems tend to look different from single-agent planning loop failures: instead of one agent repeating a failed action, a common failure is duplicated or contradictory work — two agents both attempt the same subtask because the handoff was ambiguous about ownership, or one agent's action invalidates an assumption another agent was relying on and neither notices. Debugging this requires the same discipline as debugging a single agent's planning loop, extended across every agent involved: a full trace of what each agent decided, what it handed off, and what it received, since a coordination bug is very hard to diagnose after the fact from final output alone without that record of the actual handoffs that occurred.
