import type { ChunkRecord, GradeVerdict, RetrievalResult, Trace, TraceNode } from "../lib/types";
import { RRF_K, TOP_K } from "./config";
import { denseSearch } from "./denseRetrieve";
import { embedQuery } from "./embedding";
import { loadBm25Index } from "./bm25";
import { reciprocalRankFusion } from "./fuse";
import type { SandboxGraph, SandboxNode, SandboxNodeKind } from "./types";

/**
 * ## The policy this file implements (Phase 10's central design decision)
 *
 * D2 means the shipped site never makes a live LLM call. That's no obstacle
 * for retrieval -- dense search, sparse search, and RRF fusion are all pure
 * computation, genuinely runnable live in the browser, so `chunk`,
 * `embed_query`, `retrieve_dense`, `retrieve_sparse`, and `fuse` are
 * **always** computed for real here, regardless of what query the user
 * typed or how they wired the canvas. `rerank` is also always "live" in
 * the sense that it's a real computation, but it's a disclosed
 * simplification (see palette.ts's `liveCaveat`) since the real
 * architecture's cross-encoder model isn't loaded.
 *
 * `grade`, `rewrite`, and `generate` are structurally different: their
 * real behavior *is* an LLM call, which this file can never make. There
 * are exactly two honest things such a node can do:
 *
 * 1. **Replay** -- if the current graph and query exactly match one of the
 *    three presets (unmodified since it was loaded), these nodes show the
 *    real recorded payload from that preset's real trace, verbatim. This
 *    is not a simulation; it's what actually happened when this exact
 *    question was run through the real Python pipeline.
 * 2. **Run extractively** -- for anything else (a custom pipeline, or a
 *    preset whose query text was edited), these nodes must never fabricate
 *    a plausible-looking LLM-shaped output. `generate` surfaces the real,
 *    verbatim text of whichever chunk actually reached it, clearly labeled
 *    as extractive. `grade` uses a disclosed, deterministic lexical-overlap
 *    heuristic, clearly labeled as not the real judge. `rewrite` is a
 *    labeled no-op passthrough -- inventing a "smarter" rewritten query
 *    without an LLM would be exactly the kind of fabrication this policy
 *    exists to prevent.
 *
 * Whether a `not-live` node replays or runs extractively is decided
 * per-node here, not globally: a preset's `replayMap` names exactly which
 * sandbox node ids correspond to which real trace node ids, so a node
 * outside that map (e.g. a second `grade` step the preset didn't have)
 * would correctly fall back to extractive for that one node alone, purely
 * as an engine-level guarantee. In practice this per-node granularity is
 * never actually exercised through the UI today: Sandbox.tsx's
 * `graphsStructurallyEqual` check clears `activePresetId` entirely on any
 * structural graph edit, so a modified preset always runs fully
 * extractively rather than a hybrid of replayed-and-extractive nodes --
 * more conservative than this engine is capable of, not less. Documented
 * here so a future UI change that allows partial-preset editing knows this
 * engine already supports it correctly.
 * added node while the rest of the preset still replays.
 */

export interface ChunkSourceResult {
  kind: "chunk";
  id: string;
  label: string;
  explain: string;
  chunkCount: number;
}

export type SandboxNodeResult = ChunkSourceResult | TraceNode;

export interface ActivePreset {
  trace: Trace;
  /** sandbox node id -> real trace node id, for exactly the not-live nodes
   * (grade/rewrite/generate) this preset's graph contains. */
  replayMap: Record<string, string>;
}

export interface ExecuteOptions {
  graph: SandboxGraph;
  queryText: string;
  chunkIndex: Map<string, ChunkRecord>;
  activePreset: ActivePreset | null;
  onNodeStart?: (nodeId: string) => void;
  onNodeComplete?: (nodeId: string, result: SandboxNodeResult) => void;
}

const QUERY_TOKEN_RE = /[a-z0-9]+/g;

function tokenize(text: string): Set<string> {
  return new Set((text.toLowerCase().match(QUERY_TOKEN_RE) ?? []).filter((t) => t.length > 1));
}

function topoSort(graph: SandboxGraph): string[] {
  const inDegree = new Map<string, number>();
  const adjacency = new Map<string, string[]>();
  for (const n of graph.nodes) {
    inDegree.set(n.id, 0);
    adjacency.set(n.id, []);
  }
  for (const e of graph.edges) {
    adjacency.get(e.source)?.push(e.target);
    inDegree.set(e.target, (inDegree.get(e.target) ?? 0) + 1);
  }
  const queue = graph.nodes.filter((n) => inDegree.get(n.id) === 0).map((n) => n.id);
  const order: string[] = [];
  while (queue.length > 0) {
    const id = queue.shift() as string;
    order.push(id);
    for (const next of adjacency.get(id) ?? []) {
      const remaining = (inDegree.get(next) ?? 0) - 1;
      inDegree.set(next, remaining);
      if (remaining === 0) queue.push(next);
    }
  }
  if (order.length !== graph.nodes.length) {
    throw new Error("sandbox graph has a cycle -- cannot execute (validate before running)");
  }
  return order;
}

function parentIds(nodeId: string, graph: SandboxGraph): string[] {
  return graph.edges.filter((e) => e.target === nodeId).map((e) => e.source);
}

function kindOf(nodeId: string, graph: SandboxGraph): SandboxNodeKind | undefined {
  return graph.nodes.find((n) => n.id === nodeId)?.kind;
}

function findRealNode(trace: Trace, realId: string): TraceNode {
  const found = trace.nodes.find((n) => n.id === realId);
  if (!found) {
    throw new Error(`preset replay map points at real node id "${realId}", not found in trace ${trace.trace_id}`);
  }
  return found;
}

/** Replays a real recorded node's payload verbatim, only remapping id/
 * parent_ids to the sandbox's own graph so NodeInspector renders the exact
 * real explain/label/payload the real pipeline produced. */
function replayNode(node: SandboxNode, graph: SandboxGraph, realNode: TraceNode): TraceNode {
  return { ...realNode, id: node.id, parent_ids: parentIds(node.id, graph) } as TraceNode;
}

class SandboxExecutionEngine {
  private context = {
    queryVectorByNode: new Map<string, Float32Array>(),
    queryTextByEmbedNode: new Map<string, string>(),
    retrievalByNode: new Map<string, RetrievalResult[]>(),
    gradeSurvivingChunkIdsByNode: new Map<string, string[]>(),
  };

  private options: ExecuteOptions;

  constructor(options: ExecuteOptions) {
    this.options = options;
  }

  async run(): Promise<Map<string, SandboxNodeResult>> {
    const { graph } = this.options;
    const order = topoSort(graph);
    const results = new Map<string, SandboxNodeResult>();

    for (const nodeId of order) {
      const node = graph.nodes.find((n) => n.id === nodeId);
      if (!node) continue;
      this.options.onNodeStart?.(nodeId);
      const t0 = performance.now();
      const result = await this.execNode(node, graph, results);
      const withDuration =
        "payload" in result ? { ...result, duration_ms: performance.now() - t0 } : result;
      results.set(nodeId, withDuration);
      this.options.onNodeComplete?.(nodeId, withDuration);
    }
    return results;
  }

  private replayFor(node: SandboxNode): TraceNode | null {
    const preset = this.options.activePreset;
    if (!preset) return null;
    const realId = preset.replayMap[node.id];
    if (!realId) return null;
    return replayNode(node, this.options.graph, findRealNode(preset.trace, realId));
  }

  private async execNode(
    node: SandboxNode,
    graph: SandboxGraph,
    priorResults: Map<string, SandboxNodeResult>,
  ): Promise<SandboxNodeResult> {
    switch (node.kind) {
      case "chunk":
        return this.execChunk(node);
      case "embed_query":
        return this.execEmbedQuery(node, graph, priorResults);
      case "retrieve_dense":
        return this.execRetrieveDense(node, graph);
      case "retrieve_sparse":
        return this.execRetrieveSparse(node, graph);
      case "fuse":
        return this.execFuse(node, graph);
      case "rerank":
        return this.execRerank(node, graph);
      case "grade":
        return this.execGrade(node, graph);
      case "rewrite":
        return this.execRewrite(node, graph, priorResults);
      case "generate":
        return this.execGenerate(node, graph);
    }
  }

  private async execChunk(node: SandboxNode): Promise<ChunkSourceResult> {
    return {
      kind: "chunk",
      id: node.id,
      label: "Corpus",
      explain:
        `The real corpus: ${this.options.chunkIndex.size} chunks, loaded from the same ` +
        "artifacts/chunks.json every other page on this site reads from.",
      chunkCount: this.options.chunkIndex.size,
    };
  }

  private async execEmbedQuery(
    node: SandboxNode,
    graph: SandboxGraph,
    priorResults: Map<string, SandboxNodeResult>,
  ): Promise<TraceNode> {
    // If this embed_query is fed by a rewrite step, it embeds *that* real
    // node's real (or extractive-passthrough) rewritten text, not the
    // original query box -- matching a corrective-style retry, which
    // re-embeds the rewritten query, not the original one.
    const rewriteParentId = parentIds(node.id, graph).find((pid) => kindOf(pid, graph) === "rewrite");
    const rewriteResult = rewriteParentId ? priorResults.get(rewriteParentId) : undefined;
    const text =
      rewriteResult && "payload" in rewriteResult && rewriteResult.kind === "rewrite"
        ? rewriteResult.payload.to
        : this.options.queryText;

    const vector = await embedQuery(text);
    this.context.queryVectorByNode.set(node.id, vector);
    this.context.queryTextByEmbedNode.set(node.id, text);

    return {
      id: node.id,
      kind: "embed_query",
      label: "Embed the question",
      parent_ids: parentIds(node.id, graph),
      duration_ms: 0,
      explain:
        "Computed live, right now, in your browser -- the same Xenova/all-MiniLM-L6-v2 model " +
        "(a JS port of the real Python backend's all-MiniLM-L6-v2) turns your text into a real " +
        "384-dim vector, verified to agree with the Python model to cosine similarity >=0.99.",
      payload: { dims: vector.length, preview: Array.from(vector.slice(0, 8)) },
    };
  }

  private findEmbedParent(nodeId: string, graph: SandboxGraph): string | undefined {
    return parentIds(nodeId, graph).find((pid) => kindOf(pid, graph) === "embed_query");
  }

  private async execRetrieveDense(node: SandboxNode, graph: SandboxGraph): Promise<TraceNode> {
    const embedParentId = this.findEmbedParent(node.id, graph);
    const vector = embedParentId ? this.context.queryVectorByNode.get(embedParentId) : undefined;
    if (!vector) {
      throw new Error(`Dense Retrieve (${node.id}) has no connected Embed Query input to run with`);
    }
    const results = await denseSearch(vector, TOP_K);
    this.context.retrievalByNode.set(node.id, results);
    return {
      id: node.id,
      kind: "retrieve_dense",
      label: `Top-${TOP_K} dense retrieval`,
      parent_ids: parentIds(node.id, graph),
      duration_ms: 0,
      explain:
        "Real dot-product search over the real corpus vectors, fetched live from vectors.f32 -- " +
        "identical operation to the Python backend's DenseStore.search().",
      payload: { results, k: TOP_K },
    };
  }

  private async execRetrieveSparse(node: SandboxNode, graph: SandboxGraph): Promise<TraceNode> {
    const embedParentId = this.findEmbedParent(node.id, graph);
    const text = embedParentId
      ? (this.context.queryTextByEmbedNode.get(embedParentId) ?? this.options.queryText)
      : this.options.queryText;
    const bm25 = await loadBm25Index();
    const results = bm25.search(text, TOP_K);
    this.context.retrievalByNode.set(node.id, results);
    return {
      id: node.id,
      kind: "retrieve_sparse",
      label: `Top-${TOP_K} sparse (BM25) retrieval`,
      parent_ids: parentIds(node.id, graph),
      duration_ms: 0,
      explain:
        "A real TypeScript port of the Python backend's exact BM25Okapi implementation (same k1=1.5, " +
        "b=0.75, epsilon=0.25), run live over the corpus's real tokenized text.",
      payload: { results, k: TOP_K },
    };
  }

  private async execFuse(node: SandboxNode, graph: SandboxGraph): Promise<TraceNode> {
    const parents = parentIds(node.id, graph);
    const lists = parents
      .map((pid) => this.context.retrievalByNode.get(pid))
      .filter((l): l is RetrievalResult[] => Array.isArray(l));
    const fused = reciprocalRankFusion(lists, RRF_K);
    this.context.retrievalByNode.set(node.id, fused);
    return {
      id: node.id,
      kind: "fuse",
      label: "Reciprocal rank fusion",
      parent_ids: parents,
      duration_ms: 0,
      explain:
        "Real reciprocal rank fusion (RRF_K=60, same constant the real Hybrid architecture uses) " +
        "combining its inputs' ranked lists.",
      payload: { method: "rrf", k: RRF_K, inputs: parents, results: fused },
    };
  }

  private async execRerank(node: SandboxNode, graph: SandboxGraph): Promise<TraceNode> {
    const parents = parentIds(node.id, graph);
    const before = parents.flatMap((pid) => this.context.retrievalByNode.get(pid) ?? []);
    // Simplified live rerank: the real Hybrid architecture rescores with a
    // trained cross-encoder; the sandbox doesn't load that ~80MB model, so
    // this step keeps the incoming order/scores unchanged rather than
    // fabricate a plausible-looking rescoring. See palette.ts's liveCaveat.
    const after = before.slice(0, TOP_K);
    this.context.retrievalByNode.set(node.id, after);
    return {
      id: node.id,
      kind: "rerank",
      label: "Rerank (simplified)",
      parent_ids: parents,
      duration_ms: 0,
      explain:
        "Simplified: the real Hybrid architecture reranks with a trained cross-encoder model, which " +
        "the sandbox doesn't load live (a second, unverified ~80MB model). This step keeps the " +
        "incoming order and scores unchanged rather than fabricate a plausible-looking rescoring.",
      payload: { model: "(none -- simplified passthrough, see explain)", before, after },
    };
  }

  private gradeCandidates(node: SandboxNode, graph: SandboxGraph): RetrievalResult[] {
    const parents = parentIds(node.id, graph);
    return parents.flatMap((pid) => this.context.retrievalByNode.get(pid) ?? []);
  }

  private async execGrade(node: SandboxNode, graph: SandboxGraph): Promise<TraceNode> {
    const replay = this.replayFor(node);
    if (replay && replay.kind === "grade") {
      const surviving = replay.payload.judgements
        .filter((j) => j.verdict !== "incorrect")
        .map((j) => j.chunk_id);
      this.context.gradeSurvivingChunkIdsByNode.set(
        node.id,
        surviving.length > 0 ? surviving : replay.payload.judgements.map((j) => j.chunk_id),
      );
      return replay;
    }

    const candidates = this.gradeCandidates(node, graph);
    const queryTokens = tokenize(this.options.queryText);
    const judgements = candidates.map((c) => {
      const chunkText = this.options.chunkIndex.get(c.chunk_id)?.text ?? "";
      const chunkTokens = tokenize(chunkText);
      const overlap = [...queryTokens].filter((t) => chunkTokens.has(t)).length;
      const ratio = queryTokens.size > 0 ? overlap / queryTokens.size : 0;
      const verdict: GradeVerdict = ratio >= 0.3 ? "correct" : ratio > 0 ? "ambiguous" : "incorrect";
      return {
        chunk_id: c.chunk_id,
        verdict,
        reason:
          `Extractive heuristic (lexical overlap), not the real LLM judge: ${overlap} of ` +
          `${queryTokens.size} query word(s) also appear in this chunk (${(ratio * 100).toFixed(0)}%).`,
      };
    });
    const surviving = judgements.filter((j) => j.verdict !== "incorrect").map((j) => j.chunk_id);
    this.context.gradeSurvivingChunkIdsByNode.set(
      node.id,
      surviving.length > 0 ? surviving : candidates.map((c) => c.chunk_id),
    );

    return {
      id: node.id,
      kind: "grade",
      label: "Grade retrieved chunks (extractive)",
      parent_ids: parentIds(node.id, graph),
      duration_ms: 0,
      explain:
        "Extractive: the real Corrective architecture grades with a live LLM call, which the " +
        "shipped site never makes (D2). Outside the 3 recorded presets, this step approximates " +
        "relevance with a disclosed, deterministic lexical-overlap heuristic instead -- not the " +
        "real judge, and not fabricated to look like one.",
      payload: { judgements },
    };
  }

  private async execRewrite(
    node: SandboxNode,
    graph: SandboxGraph,
    priorResults: Map<string, SandboxNodeResult>,
  ): Promise<TraceNode> {
    const replay = this.replayFor(node);
    if (replay && replay.kind === "rewrite") return replay;

    const gradeParentId = parentIds(node.id, graph).find((pid) => kindOf(pid, graph) === "grade");
    const gradeResult = gradeParentId ? priorResults.get(gradeParentId) : undefined;
    const incorrectReasons =
      gradeResult && "payload" in gradeResult && gradeResult.kind === "grade"
        ? gradeResult.payload.judgements.filter((j) => j.verdict === "incorrect").length
        : 0;

    return {
      id: node.id,
      kind: "rewrite",
      label: "Rewrite query (no-op, extractive)",
      parent_ids: parentIds(node.id, graph),
      duration_ms: 0,
      explain:
        "No real rewrite is performed outside the recorded presets. The real Corrective architecture " +
        "rewrites the query with a live LLM call, which the shipped site never makes (D2) -- the " +
        "sandbox never invents a 'smarter' query without one, so this step passes the query through " +
        `unchanged (${incorrectReasons} chunk(s) upstream were graded incorrect, but nothing new is ` +
        "substituted).",
      payload: { from: this.options.queryText, to: this.options.queryText, reason: "(extractive passthrough -- see explain)" },
    };
  }

  private async execGenerate(node: SandboxNode, graph: SandboxGraph): Promise<TraceNode> {
    const replay = this.replayFor(node);
    if (replay && replay.kind === "generate") return replay;

    const parents = parentIds(node.id, graph);
    let candidateIds: string[] = [];
    for (const pid of parents) {
      if (kindOf(pid, graph) === "grade") {
        candidateIds = candidateIds.concat(this.context.gradeSurvivingChunkIdsByNode.get(pid) ?? []);
      } else {
        candidateIds = candidateIds.concat(
          (this.context.retrievalByNode.get(pid) ?? []).map((r) => r.chunk_id),
        );
      }
    }

    const topChunkId = candidateIds[0];
    const topChunk = topChunkId ? this.options.chunkIndex.get(topChunkId) : undefined;
    const output = topChunk
      ? `[EXTRACTIVE -- top retrieved chunk, not a model-generated answer]\n\n${topChunk.text}`
      : "[EXTRACTIVE -- no chunk reached this step, so there is nothing to show]";

    return {
      id: node.id,
      kind: "generate",
      label: "Generate answer (extractive)",
      parent_ids: parents,
      duration_ms: 0,
      explain:
        "This is not a generated answer. The shipped site never makes a live LLM call (D2), so " +
        "outside the 3 recorded presets this step can't produce real generation -- it shows the " +
        "verbatim text of the top-ranked chunk that reached it instead, clearly labeled as extractive. " +
        "Only the 3 presets below can show a real generated answer, because that's a real, " +
        "already-recorded response to that exact question from the real pipeline.",
      payload: { output, prompt_preview: "(extractive -- no prompt was sent)", tokens: 0 },
    };
  }
}

export async function executeGraph(options: ExecuteOptions): Promise<Map<string, SandboxNodeResult>> {
  return new SandboxExecutionEngine(options).run();
}
