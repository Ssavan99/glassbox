import type { PaletteEntry, SandboxNodeKind } from "./types";

/**
 * The sandbox's node palette -- narrower than the real trace schema by
 * design (no `graph_seed`/`graph_expand`; Graph-style pipelines are out of
 * scope for Phase 10). `requiredInputs` drives validate.ts's inline-error
 * checking; `live`/`liveCaveat` drive the "retrieval: live ·
 * generation: recorded/extractive" badge -- see execute.ts's doc comment
 * for the full policy on what each non-live kind actually does when run
 * outside of an exact preset match.
 */
export const PALETTE: Record<SandboxNodeKind, PaletteEntry> = {
  chunk: {
    kind: "chunk",
    label: "Chunk",
    glyph: "▤",
    description: "The real corpus: 127 chunks, loaded from artifacts/chunks.json.",
    live: "live",
    requiredInputs: [],
  },
  embed_query: {
    kind: "embed_query",
    label: "Embed Query",
    glyph: "◉",
    description: "Embeds your typed query with a real, live in-browser model run.",
    live: "live",
    requiredInputs: [],
  },
  retrieve_dense: {
    kind: "retrieve_dense",
    label: "Dense Retrieve",
    glyph: "≈",
    description: "Real dot-product search over the corpus's real embedding vectors.",
    live: "live",
    requiredInputs: [
      { kinds: ["chunk"], count: 1 },
      { kinds: ["embed_query"], count: 1 },
    ],
  },
  retrieve_sparse: {
    kind: "retrieve_sparse",
    label: "Sparse Retrieve",
    glyph: "#",
    description: "Real BM25 search over the corpus's real tokenized text.",
    live: "live",
    requiredInputs: [
      { kinds: ["chunk"], count: 1 },
      // Requires an embed_query edge even though sparse search only
      // consumes the raw query text, not the vector -- the same
      // convention hybrid.py's real code uses (see this file's doc
      // comment), because both retrieval branches fire off the same query.
      { kinds: ["embed_query"], count: 1 },
    ],
  },
  fuse: {
    kind: "fuse",
    label: "Fuse",
    glyph: "⋈",
    description: "Real reciprocal rank fusion (same RRF_K as the real Hybrid architecture) over its inputs.",
    live: "live",
    requiredInputs: [{ kinds: ["retrieve_dense", "retrieve_sparse"], count: 2 }],
  },
  rerank: {
    kind: "rerank",
    label: "Rerank",
    glyph: "↕",
    description: "Reorders candidates by their existing retrieval score.",
    live: "live",
    liveCaveat:
      "Simplified: the real Hybrid architecture reranks with a trained cross-encoder model, which " +
      "the sandbox doesn't load live (a second ~80MB model, never verified here). This step keeps " +
      "the incoming order and scores unchanged rather than fabricate a plausible-looking rescoring.",
    requiredInputs: [{ kinds: ["fuse", "retrieve_dense", "retrieve_sparse"], count: 1 }],
  },
  grade: {
    kind: "grade",
    label: "Grade",
    glyph: "✓",
    description: "Judges each candidate's relevance -- real LLM judgements only replay for the 3 presets.",
    live: "not-live",
    requiredInputs: [{ kinds: ["fuse", "rerank", "retrieve_dense", "retrieve_sparse"], count: 1 }],
  },
  rewrite: {
    kind: "rewrite",
    label: "Rewrite",
    glyph: "↻",
    description: "Rewrites the query after grading -- real LLM rewrites only replay for the 3 presets.",
    live: "not-live",
    requiredInputs: [{ kinds: ["grade"], count: 1 }],
  },
  generate: {
    kind: "generate",
    label: "Generate",
    glyph: "▶",
    description: "Generates the final answer -- real LLM answers only replay for the 3 presets.",
    live: "not-live",
    requiredInputs: [
      { kinds: ["fuse", "rerank", "grade", "retrieve_dense", "retrieve_sparse"], count: 1 },
    ],
  },
};

export const PALETTE_ORDER: SandboxNodeKind[] = [
  "chunk",
  "embed_query",
  "retrieve_dense",
  "retrieve_sparse",
  "fuse",
  "rerank",
  "grade",
  "rewrite",
  "generate",
];
