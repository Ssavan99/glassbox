---
title: "Rate Limits and Retry Storms"
tags: [failure-modes, serving]
entities: [latency, throughput, guardrails]
created: 2026-01-13
---

Rate limits cap how many requests a client can send to an API within a time window, and every hosted model provider enforces one. A request that exceeds the limit gets rejected with a `429 Too Many Requests` HTTP status — a specific, well-known code worth recognizing on sight, since it means the request itself was valid and would likely have succeeded, it simply arrived too fast relative to the account's allowed rate rather than being malformed or unauthorized.

The naive response to a 429 is to retry immediately, and this is exactly what produces a retry storm: if a system is being rate-limited because it is sending requests too fast, retrying instantly just adds another request to an already-overloaded rate window, which gets rejected too, triggering another immediate retry, and so on — the retry logic itself becomes the thing keeping the system stuck in a failure loop rather than recovering from one. This is especially damaging in a multi-agent or high-concurrency system where many callers can independently hit the same rate limit and all begin retrying in the same tight loop simultaneously, amplifying load on the provider at exactly the moment it is already struggling to keep up.

The standard mitigation is exponential backoff with jitter: each retry waits progressively longer than the last — doubling the delay on each attempt is a common scheme — with a small random jitter added to each wait so that many simultaneously-retrying clients do not all retry at the exact same moment and immediately recreate the same spike that triggered the rate limit in the first place. A retry loop should also cap its total number of attempts and its maximum backoff delay, and treat exhausting those retries as a defined failure to surface, the same discipline used for bounding an agent's planning loop, rather than retrying indefinitely.

Rate limiting is also a guardrail worth applying deliberately on the calling side, not just something a provider enforces reactively from outside: a system that caps its own outgoing request rate below the provider's actual limit, with headroom, rarely triggers 429 responses at all, which is a more reliable strategy than handling rate limit errors gracefully after the fact, since avoiding the failure mode entirely beats recovering from it quickly every time.
