---
title: "Source Freshness and Recency Weighting"
tags: [data-quality, retrieval]
entities: [drift, retrieval metrics, data quality, cosine similarity]
created: 2026-01-11
---

Recency weighting adjusts a retrieval system's ranking to favor newer documents over older ones, on top of whatever relevance score similarity search alone would produce. Pure cosine similarity has no concept of time — a note written two years ago and one written yesterday are ranked purely on how close their embeddings are to the query, with no penalty at all for the old note being outdated, which is exactly the mechanism that lets stale corpus content quietly outrank its own correction if a topic gets revisited and updated later.

The simplest form of recency weighting blends a relevance score with a decay function based on document age — a note's contribution to the final ranking score gets discounted the older it is, so two similarly relevant notes get separated by recency when relevance alone would have left them tied or nearly tied. This is a genuinely different mechanism from the freshness metadata discussed in the note on data drift: metadata lets a human or a review process identify which notes are candidates for staleness review, while recency weighting is an automatic ranking adjustment applied at query time regardless of whether anyone has manually reviewed anything.

Recency weighting is not universally appropriate and needs to be scoped to content type rather than applied globally. It is clearly useful for corpora where facts genuinely change over time — pricing, policy, current best practices — but actively harmful for corpora containing durable, timeless explanations, where an older note explaining what reciprocal rank fusion is remains just as correct as a note on the same topic written yesterday, and downweighting it purely for age would push a perfectly good answer out of the top results for no real reason.

A more targeted middle ground is applying recency weighting only to note clusters known to be time-sensitive, tagged explicitly as such in frontmatter, rather than as a blanket adjustment across the whole corpus — which keeps the timeless, conceptual majority of notes ranked purely on relevance while still correcting for staleness in the smaller subset of content where document age genuinely predicts correctness.
