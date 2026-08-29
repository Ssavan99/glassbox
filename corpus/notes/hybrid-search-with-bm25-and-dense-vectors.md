---
title: "Hybrid Search with BM25 and Dense Vectors"
tags: [retrieval, search]
entities: [hybrid search, bm25, dense retrieval, sparse retrieval, semantic search, embedding model]
created: 2026-01-06
---

Hybrid search combines two retrieval methods that fail in complementary ways: dense retrieval, which searches by embedding similarity, and sparse retrieval, typically implemented with bm25, which searches by keyword overlap and term frequency. Neither method alone is reliably good across the full range of queries a real corpus receives, which is why production retrieval systems increasingly run both and merge the results rather than picking one.

Bm25 is a scoring function built on term frequency and inverse document frequency: it rewards a document for containing the query's exact terms, weighted by how rare those terms are across the whole corpus. This makes it extremely strong at exact keyword and identifier matching — an acronym, a config flag name, a version number — precisely the cases where an embedding model tends to smooth things over and miss the exact string. What bm25 cannot do is match on meaning: a query phrased differently from the document, even if conceptually identical, scores poorly.

Dense retrieval is the mirror image: it excels at conceptual, paraphrased, or vague queries because it compares meaning rather than surface tokens, but it can genuinely miss a chunk that contains the exact right answer if that chunk's embedding happens to land slightly off in vector space, especially for short, jargon-heavy text where the embedding model has little context to work with.

Running both searches and merging their ranked lists gives you the strengths of each without needing to predict, ahead of time, which kind of query a user will type. The merge step itself is a separate design decision — usually handled with a fusion method such as reciprocal rank fusion — and is covered in its own note, since how the two rankings are combined matters as much as running both searches in the first place.

In a personal knowledge base, hybrid search matters more than it might in a narrower domain, because notes mix conceptual prose ("why retrieval quality matters") with exact technical terms (an exact library function name, a config constant) in the same corpus, and a single retrieval method will systematically underserve one of those two content types.
