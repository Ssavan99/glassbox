---
title: "Agent Memory and Context Management"
tags: [agents]
entities: [memory, agent, context window, token budget]
created: 2026-01-12
---

Agent memory is what persists information across steps of a planning loop, or across entirely separate sessions, so an agent does not have to re-derive context it has already gathered. The simplest form is just the running transcript of the current task — every observation, action, and result kept in the prompt so the model can see its own history when deciding what to do next. This works well for short tasks but runs directly into the context window limit as a task grows longer: eventually the full transcript no longer fits, and something has to be dropped, summarized, or moved out of the prompt entirely.

Longer-running or multi-session agents typically need memory that outlives a single prompt's context window — a store the agent explicitly writes important facts to and can query later, separate from the transcript of any one conversation. This introduces a genuinely different set of problems than transcript memory does: what counts as important enough to write down, how to retrieve the relevant piece of stored memory when it becomes relevant again (which is itself a retrieval problem, subject to the same embedding and chunking tradeoffs as any other retrieval system), and how to keep stored memory from silently going stale in the same way a corpus can drift out of date.

Poorly scoped memory is its own distinct failure mode, separate from a planning loop failure: an agent that "remembers" something from an earlier step and treats it as still true, even after the underlying situation has changed, will act confidently on stale information exactly the way a model relying on drifted corpus content does. The fix is the same instinct as elsewhere in this pipeline — memory needs a notion of freshness or an explicit invalidation trigger, not just an assumption that whatever was written down remains true indefinitely.

Context management, more broadly, is the discipline of deciding what belongs in the model's limited context window at any given moment — recent transcript, retrieved long-term memory, tool results, task instructions — under the same token budget pressure that governs prompt template design for retrieval-augmented answers. An agent with unmanaged context tends to either exceed the context window on long tasks or dilute its attention across too much low-value history, both of which degrade decision quality in the planning loop even when every individual piece of memory it holds is accurate.
