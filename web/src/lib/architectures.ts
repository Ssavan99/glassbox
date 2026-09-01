import type { ArchitectureId } from "./types";
import { ARCHITECTURE_IDS } from "./types";

export interface ArchitectureMeta {
  id: ArchitectureId;
  name: string;
  tagline: string;
  /** CSS var name (see index.css) — always pair with a visible text label,
   * never color alone: 3 of these fail 3:1 contrast on the light surface
   * by design (see the dataviz-skill validator output logged in the plan). */
  colorVar: string;
}

export const ARCHITECTURES: Record<ArchitectureId, ArchitectureMeta> = {
  naive: {
    id: "naive",
    name: "Naive",
    tagline: "Chunk, embed, cosine top-5, generate. The baseline everything else is measured against.",
    colorVar: "--arch-naive",
  },
  hybrid: {
    id: "hybrid",
    name: "Hybrid",
    tagline: "BM25 and dense retrieval fused by reciprocal rank, then cross-encoder reranked.",
    colorVar: "--arch-hybrid",
  },
  hyde: {
    id: "hyde",
    name: "HyDE",
    tagline: "Drafts a hypothetical answer first, and embeds that instead of the question.",
    colorVar: "--arch-hyde",
  },
  corrective: {
    id: "corrective",
    name: "Corrective",
    tagline: "Grades its own retrieval, rewrites the query, and re-retrieves when it's wrong.",
    colorVar: "--arch-corrective",
  },
  graph: {
    id: "graph",
    name: "Graph",
    tagline: "Traverses a knowledge graph built from the corpus instead of ranking by similarity alone.",
    colorVar: "--arch-graph",
  },
  agentic: {
    id: "agentic",
    name: "Agentic",
    tagline: "Plans sub-questions, picks a retrieval tool for each, and reflects before synthesizing.",
    colorVar: "--arch-agentic",
  },
  adaptive: {
    id: "adaptive",
    name: "Adaptive",
    tagline: "Routes each question to whichever of the other six architectures fits it best.",
    colorVar: "--arch-adaptive",
  },
};

/** "Start here" order per Phase 9's tutorial ordering. */
export const ARCHITECTURE_ORDER: ArchitectureId[] = [...ARCHITECTURE_IDS];

export function architectureColor(id: ArchitectureId): string {
  return `var(${ARCHITECTURES[id].colorVar})`;
}
