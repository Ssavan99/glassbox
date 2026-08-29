---
title: "Data Drift and Stale Corpora"
tags: [data-quality]
entities: [drift, data quality, retrieval-augmented generation, evaluation harness]
created: 2026-01-11
---

Drift, in the corpus sense, is what happens when the information in a retrieval corpus gradually stops matching reality — a note describes a config flag's old name after it was renamed, a policy note reflects a since-changed process, or a technical note refers to a library version that has since had a breaking release. Unlike a model that requires retraining to update, a RAG corpus can in principle be kept current just by editing text — but only if someone actually notices what has gone stale and edits it, which is where drift creeps in.

Stale corpus content is a particularly dangerous failure mode because it does not look broken. Retrieval can work perfectly — the right note gets found, the citation is accurate, the answer is grounded in exactly the evidence it claims to be grounded in — and the answer can still be wrong, because the evidence itself no longer reflects the current state of the world. This is a failure that citation quality checks, which only verify that a claim matches its cited source, cannot catch at all; the citation is honest, the source is simply outdated.

Detecting drift generally requires either a freshness signal tracked alongside each note — when it was created, when it was last verified — or periodic re-review triggered by some external signal, such as a linked system changing in a way that should invalidate dependent notes. Neither is automatic: a corpus with no created or last-reviewed metadata at all has no way to even flag which notes are candidates for staleness review, which is part of why frontmatter discipline — recording creation dates and, ideally, freshness signals — matters beyond just organizing the corpus.

A golden dataset used for evaluation is itself vulnerable to a specific version of this problem: if the corpus changes underneath a fixed evaluation set, an entry's recorded correct answer can silently become wrong, and the evaluation harness will keep confidently scoring answers against an outdated expectation. This is a good reason to periodically re-validate golden dataset entries against the current corpus, not just treat them as permanently correct once written — a golden dataset frozen forever is protected from evaluation noise but not from drifting out of sync with the corpus it is meant to test.
