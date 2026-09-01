import type { NodeKind } from "../lib/types";

/**
 * The sandbox's palette is deliberately narrower than the real trace
 * schema's 14-kind `NodeKind` set (Phase 9's plan explicitly excludes
 * `graph_seed`/`graph_expand` -- the sandbox doesn't support Graph-style
 * pipelines) and adds exactly one kind the real schema doesn't have:
 * `"chunk"`, a source node representing "the real corpus is loaded and
 * available to search over". Every other kind here is a real `NodeKind`,
 * so a genuinely-computed step's result can be handed directly to the same
 * `NodeInspector` Phase 8 built, with no parallel rendering system.
 */
export type SandboxNodeKind = "chunk" | RealSandboxKind;

export type RealSandboxKind = Extract<
  NodeKind,
  | "embed_query"
  | "retrieve_dense"
  | "retrieve_sparse"
  | "fuse"
  | "rerank"
  | "grade"
  | "rewrite"
  | "generate"
>;

export const SANDBOX_NODE_KINDS: SandboxNodeKind[] = [
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

export interface SandboxNode {
  id: string;
  kind: SandboxNodeKind;
  position: { x: number; y: number };
}

export interface SandboxEdge {
  id: string;
  source: string;
  target: string;
}

export interface SandboxGraph {
  nodes: SandboxNode[];
  edges: SandboxEdge[];
}

/**
 * Every node kind that isn't `"chunk"`/`"embed_query"` needs a minimum
 * count of incoming edges whose *source* node's kind is in `kinds`, for
 * each entry in its `requiredInputs` list -- e.g. `retrieve_dense` needs
 * one edge from a `"chunk"` node AND (a separate requirement) one edge
 * from an `"embed_query"` node, while `fuse` needs two edges total from
 * either retrieval kind (one requirement, count 2). This mirrors the real
 * architectures' own parenting convention: hybrid.py structurally parents
 * `retrieve_sparse` on `embed_query` even though it only consumes the raw
 * query text, "because both retrieval branches fire off the same query" --
 * the sandbox's `retrieve_sparse` requires the same edge for the same
 * pedagogical reason.
 */
export interface RequiredInput {
  kinds: SandboxNodeKind[];
  count: number;
}

/** Whether a node kind's execution result is genuinely computed live in the
 * browser, or whether it can only replay a real recorded value (when the
 * current graph+query exactly matches one of the three presets) or run a
 * clearly-labeled extractive/passthrough fallback otherwise. See
 * `sandbox/execute.ts`'s doc comment for the full policy -- this flag drives
 * the "retrieval: live · generation: recorded/extractive" badge, which must
 * never blur into implying a fabricated result is real. */
export type LiveKind = "live" | "not-live";

export interface PaletteEntry {
  kind: SandboxNodeKind;
  label: string;
  glyph: string;
  description: string;
  live: LiveKind;
  /** Set only when `live` is `"live"` but the real behavior is a disclosed
   * simplification (currently only `rerank`, which doesn't load a second
   * ~80MB cross-encoder model live -- see palette.ts). */
  liveCaveat?: string;
  requiredInputs: RequiredInput[];
}
