---
title: "Deduplication in Training and Corpus Data"
tags: [data-quality]
entities: [deduplication, data quality, retrieval metrics, chunking]
created: 2026-01-11
---

Deduplication removes near-identical or exactly duplicated content from a dataset, whether that dataset is training data for fine-tuning or a corpus being indexed for retrieval. Duplicates are a subtler problem than they first appear, because their harm differs sharply depending on which pipeline stage they show up in.

In fine-tuning data, duplicated examples effectively increase that example's weight during training without the model creator intending it — a phrase or fact that happens to be duplicated across many source documents gets reinforced disproportionately relative to genuinely rarer information, which can bias a fine-tuned model toward overrepresented patterns and, in more severe cases, contribute to the model memorizing and later regurgitating specific duplicated passages verbatim rather than generalizing from them.

In a retrieval corpus, near-duplicate notes create a different problem: they compete with each other for the same top-k retrieval slots, crowding out other genuinely distinct, relevant chunks that might otherwise have made the cut. This directly hurts retrieval metrics like recall@k, since several duplicate slots effectively count as one useful slot from the model's perspective — it is shown the same information three times instead of three different pieces of evidence. This is one of the concrete ways decoy notes and duplicate content can quietly poison an otherwise well-built corpus if introduced by accident rather than deliberately as an evaluation stress test.

Deduplication is harder than a simple exact-string match because most real duplicates are near-duplicates — the same underlying content reworded, reformatted, or lightly edited rather than byte-identical. Practical deduplication pipelines typically use a fuzzy similarity measure, sometimes the same embedding-based cosine similarity used for retrieval itself, to flag pairs of documents or chunks above a similarity threshold for human review or automatic removal. Setting that threshold is itself a tradeoff familiar from other parts of this pipeline: too aggressive and genuinely distinct but related content gets wrongly merged away; too conservative and true duplicates slip through untouched, continuing to cause exactly the problems deduplication was meant to fix in the first place.
