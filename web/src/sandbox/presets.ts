import type { ArchitectureId } from "../lib/types";
import type { SandboxGraph } from "./types";

export interface SandboxPreset {
  id: string;
  label: string;
  description: string;
  /** The exact real question text -- typed unmodified, this is what makes
   * an exact replay of the real recorded answer honest rather than a
   * coincidence. */
  query: string;
  graph: SandboxGraph;
  architecture: ArchitectureId;
  questionId: string;
  /** sandbox node id -> real trace node id, for exactly this preset's
   * grade/rewrite/generate nodes -- see execute.ts's doc comment. */
  replayMap: Record<string, string>;
}

function pos(x: number, y: number) {
  return { x, y };
}

/**
 * Three real, verified (architecture, question_id) pairs, chosen for shape
 * diversity and because each is already used elsewhere on this site (q21
 * is Compare's real keyword-divergence example; naive/q01 and
 * corrective/q25 are real, unremarkable, representative runs) --
 * `activePresetId` in Sandbox.tsx clears the moment the user edits the
 * query text or the graph structure, so only an unmodified preset ever
 * replays; everything else runs extractively per execute.ts's policy.
 */
export const PRESETS: SandboxPreset[] = [
  {
    id: "naive-q01",
    label: "Naive",
    description: "The simplest real shape: embed, retrieve, generate.",
    query: "What does LoRA freeze, and roughly what fraction of a model's parameters does it actually train?",
    architecture: "naive",
    questionId: "q01",
    graph: {
      nodes: [
        { id: "chunk", kind: "chunk", position: pos(0, 120) },
        { id: "embed", kind: "embed_query", position: pos(0, 0) },
        { id: "dense", kind: "retrieve_dense", position: pos(260, 60) },
        { id: "generate", kind: "generate", position: pos(520, 60) },
      ],
      edges: [
        { id: "chunk->dense", source: "chunk", target: "dense" },
        { id: "embed->dense", source: "embed", target: "dense" },
        { id: "dense->generate", source: "dense", target: "generate" },
      ],
    },
    replayMap: { generate: "n3" },
  },
  {
    id: "hybrid-q21",
    label: "Hybrid",
    description: "Dense + sparse retrieval, fused and reranked -- the same real question /compare defaults its keyword divergence to.",
    query: "What sampling flag and value should be set when running the golden dataset so evaluation scores stay comparable across runs?",
    architecture: "hybrid",
    questionId: "q21",
    graph: {
      nodes: [
        { id: "chunk", kind: "chunk", position: pos(0, 120) },
        { id: "embed", kind: "embed_query", position: pos(0, 0) },
        { id: "dense", kind: "retrieve_dense", position: pos(260, 0) },
        { id: "sparse", kind: "retrieve_sparse", position: pos(260, 180) },
        { id: "fuse", kind: "fuse", position: pos(520, 90) },
        { id: "rerank", kind: "rerank", position: pos(780, 90) },
        { id: "generate", kind: "generate", position: pos(1040, 90) },
      ],
      edges: [
        { id: "chunk->dense", source: "chunk", target: "dense" },
        { id: "embed->dense", source: "embed", target: "dense" },
        { id: "chunk->sparse", source: "chunk", target: "sparse" },
        { id: "embed->sparse", source: "embed", target: "sparse" },
        { id: "dense->fuse", source: "dense", target: "fuse" },
        { id: "sparse->fuse", source: "sparse", target: "fuse" },
        { id: "fuse->rerank", source: "fuse", target: "rerank" },
        { id: "rerank->generate", source: "rerank", target: "generate" },
      ],
    },
    replayMap: { generate: "n6" },
  },
  {
    id: "corrective-q25",
    label: "Corrective",
    description: "A real correction loop: grade, rewrite, retry -- unrolled into a static shape, exactly like the real recorded trace.",
    query: "Does fine-tuning a model with LoRA reduce a RAG pipeline's exposure to prompt injection attacks?",
    architecture: "corrective",
    questionId: "q25",
    graph: {
      nodes: [
        { id: "chunk", kind: "chunk", position: pos(0, 160) },
        { id: "embed1", kind: "embed_query", position: pos(0, 0) },
        { id: "dense1", kind: "retrieve_dense", position: pos(260, 40) },
        { id: "grade1", kind: "grade", position: pos(520, 40) },
        { id: "rewrite", kind: "rewrite", position: pos(780, 40) },
        { id: "embed2", kind: "embed_query", position: pos(780, 220) },
        { id: "dense2", kind: "retrieve_dense", position: pos(1040, 130) },
        { id: "grade2", kind: "grade", position: pos(1300, 130) },
        { id: "generate", kind: "generate", position: pos(1560, 130) },
      ],
      edges: [
        { id: "chunk->dense1", source: "chunk", target: "dense1" },
        { id: "embed1->dense1", source: "embed1", target: "dense1" },
        { id: "dense1->grade1", source: "dense1", target: "grade1" },
        { id: "grade1->rewrite", source: "grade1", target: "rewrite" },
        { id: "rewrite->embed2", source: "rewrite", target: "embed2" },
        { id: "chunk->dense2", source: "chunk", target: "dense2" },
        { id: "embed2->dense2", source: "embed2", target: "dense2" },
        { id: "dense2->grade2", source: "dense2", target: "grade2" },
        { id: "grade2->generate", source: "grade2", target: "generate" },
      ],
    },
    replayMap: { grade1: "n3", rewrite: "n4", grade2: "n7", generate: "n8" },
  },
];
