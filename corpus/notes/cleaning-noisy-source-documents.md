---
title: "Cleaning Noisy Source Documents"
tags: [data-quality]
entities: [data quality, chunking, embedding model]
created: 2026-01-11
---

Source documents rarely arrive in a form ready to chunk and embed directly. PDFs export with broken paragraph breaks and stray page-header text interleaved into the body; scraped web pages carry navigation menus, cookie banners, and footer boilerplate mixed in with the actual content; exported chat logs and emails carry quoted reply chains and signature blocks repeated on every message. Cleaning is the step that strips this noise out before it ever reaches chunking, and skipping it does not fail loudly — it just quietly degrades everything downstream.

Boilerplate text is a particularly insidious form of noise because it is often short and repeated identically across many documents, which means an embedding model can end up treating "click here to accept cookies" as a recurring, seemingly meaningful pattern that shows up in the embeddings of many otherwise-unrelated chunks, subtly polluting how those chunks compare to each other in vector space. A chunk that is mostly boilerplate with only a sentence of real content also wastes token budget once retrieved, since a disproportionate share of what gets inserted into the prompt is noise rather than answer-bearing text.

Broken structure — paragraphs split mid-sentence by a PDF export, or headings that lost their markdown formatting during conversion — directly undermines heading-aware chunking, since a chunker relying on `##` boundaries to find coherent sections has nothing reliable to key off if those boundaries were lost in the source format. This is a case where cleaning and chunking strategy are not independent decisions: a chunking approach that works well on cleanly authored markdown can perform noticeably worse on the same content pulled from a messier source format, even though the underlying information is identical.

Cleaning is worth treating as its own auditable pipeline stage rather than an implicit side effect of ingestion, because a cleaning step that is too aggressive can strip real content along with the noise — an overzealous boilerplate filter can delete a legitimately short, information-dense paragraph that happens to resemble a footer in length and structure. Spot-checking a sample of cleaned output against its original source, the same discipline used elsewhere in this pipeline for evaluation, catches this kind of over-cleaning before it silently removes content the corpus actually needed.
