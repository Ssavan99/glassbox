# Corpus Design Contract

This corpus is the test fixture for the glassbox RAG architecture atlas: 60 markdown
notes on AI/ML engineering, written not just to be *correct* but to be a
deliberately instrumented stress test for retrieval, evaluation, and (later)
knowledge-graph construction. If a note reads as slightly over-explained or
cross-references its neighbors more than a typical wiki page would, that is
intentional — the connective tissue between notes is the point.

Every note lives in `corpus/notes/` as `<kebab-case-slug-of-title>.md`. The
filename stem is the note's stable `note_id`. Frontmatter shape (parsed by
`engine/corpus.py`):

```yaml
---
title: "Human-Readable Title"
tags: [tag-one, tag-two]
entities: [entity one, entity two, entity three]
created: 2026-01-15
---
```

`entities` are lowercase, human-readable canonical terms, reused verbatim
across every note that touches the same concept (never a near-duplicate
variant like "BM25" vs "bm25 algorithm") — see "Recurring entities" below for
why this matters and `scripts/verify_corpus.py` for the automated check.

## Why the corpus looks the way it does

A retrieval pipeline is easy to make *look* like it works — return something
plausible for every query — and hard to make *actually* work: retrieve the
right evidence, cite it accurately, and refuse when the corpus doesn't have
the answer. A corpus made entirely of clean, independent, easily-distinguished
notes cannot tell those two states apart; every query has an obvious answer,
so every retrieval strategy looks equally good. This corpus instead plants
four specific structural contrasts so that later phases (chunking, hybrid
search, evaluation question-writing, graph construction) have real failure
modes to actually be tested against.

## 1. Recurring entities

43 canonical entities appear in the frontmatter of 3 or more notes (target was
40+; see `scripts/verify_corpus.py` output for the exact live count — rerun it
after any future corpus edit, since counts here are a snapshot). This is what
gives a future knowledge-graph pass real edges to traverse instead of a
scatter of singleton concepts. The highest-frequency hub entities, which
appear across most clusters and act as connective tissue:

| entity | notes | entity | notes |
|---|---|---|---|
| latency | 13 | dense retrieval | 5 |
| evaluation harness | 12 | multi-hop question | 5 |
| grounding | 12 | refusal | 5 |
| hallucination | 12 | batching | 4 |
| retrieval-augmented generation | 12 | cosine similarity | 4 |
| citation | 11 | golden dataset | 4 |
| prompt template | 11 | memory | 4 |
| throughput | 11 | planning loop | 4 |
| embedding model | 10 | quantization | 4 |
| fine-tuning | 10 | bm25, cross-encoder, distillation, drift, embedding dimension, function calling, hybrid search, kv cache, lora, needle in a haystack, prompt injection, reranking, semantic search, system prompt, temperature | 3 each |
| chunking | 9 | | |
| context window | 9 | | |
| agent | 8 | | |
| token budget | 8 | | |
| data quality | 7 | | |
| guardrails | 7 | | |
| retrieval metrics | 6 | | |
| tool use | 6 | | |
| vector database | 6 | | |

Run `python scripts/verify_corpus.py` for the full, current frequency table
and the enforced thresholds (≥55 notes, ≥40 entities with ≥3 occurrences).

## 2. Keyword-specific terms (exact strings a dense embedding model tends to fumble)

These are real, verbatim strings — config constants from this repo's own
frozen `engine/config.py`, real model identifiers, or realistic exact error
text — planted specifically so BM25/keyword search should win over pure
semantic search on a query targeting them:

- `CHUNK_TARGET_TOKENS = 250`, `CHUNK_OVERLAP_TOKENS = 50` — `chunk-overlap-and-why-it-matters.md`
- `RRF_K = 60` — `reciprocal-rank-fusion-explained.md`
- `EMBEDDING_DIM = 384`, `all-MiniLM-L6-v2` — `embedding-dimension-and-model-size-tradeoffs.md`
- `cross-encoder/ms-marco-MiniLM-L-6-v2` — `reranking-with-cross-encoders.md`
- `OLLAMA_MODEL = "qwen2.5:7b-instruct"`, `GROQ_MODEL = "llama-3.3-70b-versatile"` — `cost-aware-model-routing.md`
- `--temperature 0.0` — `temperature-and-sampling-controls.md`
- `429 Too Many Requests` — `rate-limits-and-retry-storms.md`
- `This model's maximum context length is 8192 tokens. However, your messages resulted in 9147 tokens` — `context-window-overflow-and-truncation.md`
- This engine's own trace node kinds (`embed_query`, `retrieve_dense`, `rerank`, `graph_expand`, etc.) and its node/parent-edge shape — `trace-logging-for-agent-debugging.md`

## 3. Multi-hop facts (deliberately split across 2–3 notes)

No single note below contains the full answer to the bracketed question — a
correct answer requires retrieving and combining both/all notes listed.

1. **"What's the tradeoff of using LoRA instead of full fine-tuning?"**
   `lora-and-parameter-efficient-fine-tuning.md` (what LoRA is; trains under
   ~1% of parameters) + `full-fine-tuning-vs-adapters.md` (the actual quality
   gap: full fine-tuning has a small edge, especially on tasks far outside
   the base model's pretraining distribution).
2. **"What does cross-encoder reranking cost in latency?"**
   `reranking-with-cross-encoders.md` (what cross-encoder reranking is and
   why it's more accurate than bi-encoder cosine similarity, but no numbers)
   + `latency-budgets-in-a-rag-pipeline.md` (the actual cost: ~100–300ms for
   reranking a 20–50 candidate shortlist).
3. **"What constant controls reciprocal rank fusion's sensitivity to rank, and what value does this engine use?"**
   `hybrid-search-with-bm25-and-dense-vectors.md` (introduces RRF as the
   fusion mechanism, no constant given) + `reciprocal-rank-fusion-explained.md`
   (the `RRF_K = 60` constant and what it does).
4. **"Besides a corpus-level retrieval miss, how else can a correctly-retrieved fact still fail to produce a correct answer, and how is it fixed?"**
   `needle-in-a-haystack-evaluation.md` (introduces the "lost in the middle"
   context-position phenomenon in passing) + `retrieval-failures-lost-in-the-middle.md`
   (the full mechanism and the prompt-template-level fix).
5. **"Why does continuous batching depend on KV cache management?"**
   `kv-cache-and-why-it-matters-for-serving.md` (what the KV cache is and why
   it exists) + `continuous-batching-and-throughput.md` (states the
   dependency: per-request cache state has to be tracked/freed as requests
   dynamically join/leave the batch).
6. **"What are this engine's exact chunk size and overlap settings, and why is overlap a genuine tradeoff rather than a free correctness fix?"**
   `chunking-strategy-and-chunk-size-tradeoffs.md` (general chunk-size
   tradeoffs, no exact numbers) + `chunk-overlap-and-why-it-matters.md`
   (the exact `CHUNK_TARGET_TOKENS`/`CHUNK_OVERLAP_TOKENS` values and the
   storage-vs-completeness tradeoff of the 20% ratio).

## 4. Near-miss decoy pairs

Same cluster, overlapping vocabulary, worded similarly enough that naive
(especially pure dense) retrieval could confuse them — but each pair actually
answers a different question:

| pair | looks similar because | actually differs on |
|---|---|---|
| `chunking-strategy-and-chunk-size-tradeoffs.md` vs `chunk-overlap-and-why-it-matters.md` | both about chunking, both use "chunk size" vocabulary | one is about chunk *size*, the other about *overlap* between chunks — independent levers |
| `reducing-latency-with-batching.md` vs `reducing-latency-with-quantization.md` | identical title pattern, both "serving latency" | batching mainly trades latency for *throughput*; quantization actually cuts *per-request* latency via smaller/faster weights |
| `tool-use-and-function-calling.md` vs `planning-loops-in-agents.md` | both agent-cluster, both discuss tools and loops | one is the action *interface*, the other is the *reasoning strategy* that decides when to use it |
| `building-a-golden-dataset-for-rag-evaluation.md` vs `needle-in-a-haystack-evaluation.md` | both evaluation-methodology notes | one is about constructing a stable test *set*, the other about a specific *distractor-competition* test pattern |
| `few-shot-prompting-for-grounded-answers.md` vs `chain-of-thought-prompting-and-when-it-helps.md` | both prompting techniques, both discuss token cost | one shapes output *format* via examples, the other shapes *reasoning process* via intermediate steps |
| `lora-and-parameter-efficient-fine-tuning.md` vs `full-fine-tuning-vs-adapters.md` | both LoRA/fine-tuning vocabulary (also the multi-hop pair #1 above) | one explains the *mechanism*, the other the *decision/tradeoff* of when to use it |
| `deduplication-in-training-and-corpus-data.md` vs `pii-redaction-in-training-data.md` | both "cleaning training/corpus data" | one is a retrieval-quality/efficiency concern, the other a privacy/safety concern |
| `hallucination-from-missing-context.md` vs `hallucination-from-prompt-injection.md` | both explicitly about hallucination causes | one is a retrieval-coverage-and-refusal problem, the other an adversarial-input/guardrails problem — different fixes entirely |

## Content clusters

Notes are spread roughly evenly across: retrieval & embeddings (9),
evaluation (8), prompting (7), fine-tuning (7), serving & latency (8), data
quality (7), agents & tool use (7), failure modes (7) — 60 total.

## Provenance note

The 5 notes that existed before this corpus was built (`AI Agents and Tool
Use`, `AI Evaluation for Personal Knowledge Bases`, `Embeddings and Semantic
Search`, `Prompt Engineering as Interface Design`, `Retrieval-Augmented
Generation Basics`) were expanded to the standard above, renamed to
kebab-case, and folded into the entity/decoy/multi-hop structure rather than
being replaced outright — they are the anchor notes for the retrieval,
evaluation, agents, and prompting clusters respectively.
