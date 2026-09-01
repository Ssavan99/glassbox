import type { NodeKind } from "../lib/types";

/** Purely decorative per-kind glyphs for the canvas cards -- the real
 * display text is always `node.label`, which Python already writes with
 * specific, human-readable detail ("Top-5 dense retrieval (attempt 1)",
 * not just "retrieve_dense"). These glyphs just help visual scanning. */
export const KIND_GLYPH: Record<NodeKind, string> = {
  embed_query: "◉",
  retrieve_dense: "≈",
  retrieve_sparse: "#",
  fuse: "⋈",
  rerank: "↕",
  generate_hypothetical: "✳",
  grade: "✓",
  rewrite: "↻",
  graph_seed: "•",
  graph_expand: "◇",
  plan: "☰",
  reflect: "?",
  route: "⑂",
  generate: "▶",
};

/** Short, human-readable kind names for the node inspector's header (the
 * `explain` sentence and `node.label` carry the real detail; this is just
 * "what kind of step is this" scaffolding). */
export const KIND_NAME: Record<NodeKind, string> = {
  embed_query: "Embed query",
  retrieve_dense: "Dense retrieval",
  retrieve_sparse: "Sparse (BM25) retrieval",
  fuse: "Fuse rankings",
  rerank: "Rerank",
  generate_hypothetical: "Generate hypothetical",
  grade: "Grade",
  rewrite: "Rewrite query",
  graph_seed: "Seed graph entities",
  graph_expand: "Expand graph",
  plan: "Plan",
  reflect: "Reflect",
  route: "Route",
  generate: "Generate answer",
};
