import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ChunkRecord, Trace } from "../lib/types";
import type { SandboxGraph } from "./types";

const embedQueryMock = vi.fn(async (text: string) => new Float32Array([text.length, 0, 0]));
vi.mock("./embedding", () => ({ embedQuery: (text: string) => embedQueryMock(text) }));

const denseSearchMock = vi.fn(async (_vector: Float32Array, _k: number) => [
  { chunk_id: "a::0", score: 0.9, rank: 1 },
  { chunk_id: "b::0", score: 0.5, rank: 2 },
]);
vi.mock("./denseRetrieve", () => ({
  denseSearch: (vector: Float32Array, k: number) => denseSearchMock(vector, k),
}));

const bm25SearchMock = vi.fn(() => [
  { chunk_id: "c::0", score: 3, rank: 1 },
  { chunk_id: "a::0", score: 1, rank: 2 },
]);
vi.mock("./bm25", () => ({ loadBm25Index: async () => ({ search: bm25SearchMock }) }));

const { executeGraph } = await import("./execute");

function node(id: string, kind: SandboxGraph["nodes"][number]["kind"]) {
  return { id, kind, position: { x: 0, y: 0 } };
}
function edge(source: string, target: string) {
  return { id: `${source}->${target}`, source, target };
}

const chunkIndex = new Map<string, ChunkRecord>([
  ["a::0", { chunk_id: "a::0", note_id: "a", text: "LoRA freezes the base model weights", heading: null }],
  ["b::0", { chunk_id: "b::0", note_id: "b", text: "Embeddings capture semantic similarity", heading: null }],
  ["c::0", { chunk_id: "c::0", note_id: "c", text: "BM25 rewards exact keyword overlap", heading: null }],
]);

const naiveGraph: SandboxGraph = {
  nodes: [node("chunk", "chunk"), node("embed", "embed_query"), node("dense", "retrieve_dense"), node("gen", "generate")],
  edges: [edge("chunk", "dense"), edge("embed", "dense"), edge("dense", "gen")],
};

beforeEach(() => {
  embedQueryMock.mockClear();
  denseSearchMock.mockClear();
  bm25SearchMock.mockClear();
});

describe("executeGraph -- custom (non-preset) pipelines run extractively", () => {
  it("naive shape: live retrieval, extractive generate labeled and containing the real top chunk text", async () => {
    const results = await executeGraph({
      graph: naiveGraph,
      queryText: "what does LoRA freeze",
      chunkIndex,
      activePreset: null,
    });

    expect(embedQueryMock).toHaveBeenCalledWith("what does LoRA freeze");
    expect(denseSearchMock).toHaveBeenCalledTimes(1);

    const gen = results.get("gen");
    expect(gen).toBeDefined();
    expect(gen && "payload" in gen && gen.kind === "generate").toBe(true);
    if (gen && "payload" in gen && gen.kind === "generate") {
      expect(gen.payload.output).toContain("EXTRACTIVE");
      expect(gen.payload.output).toContain("LoRA freezes the base model weights"); // real top chunk (a::0, rank 1)
    }
  });

  it("grade runs an extractive lexical-overlap heuristic, not a fabricated judgement", async () => {
    const graph: SandboxGraph = {
      nodes: [...naiveGraph.nodes.filter((n) => n.id !== "gen"), node("grade", "grade")],
      edges: [edge("chunk", "dense"), edge("embed", "dense"), edge("dense", "grade")],
    };
    const results = await executeGraph({
      graph,
      queryText: "LoRA freezes weights",
      chunkIndex,
      activePreset: null,
    });
    const grade = results.get("grade");
    expect(grade && "payload" in grade && grade.kind === "grade").toBe(true);
    if (grade && "payload" in grade && grade.kind === "grade") {
      // a::0's text shares real overlap with the query ("LoRA", "freezes"/"freeze", "weights")
      const aJudgement = grade.payload.judgements.find((j) => j.chunk_id === "a::0");
      expect(aJudgement?.reason).toContain("Extractive heuristic");
      expect(aJudgement?.verdict).not.toBe(undefined);
      // b::0 shares no real overlap with this query
      const bJudgement = grade.payload.judgements.find((j) => j.chunk_id === "b::0");
      expect(bJudgement?.verdict).toBe("incorrect");
    }
  });

  it("rewrite is a labeled no-op passthrough, never a fabricated 'smarter' query", async () => {
    const graph: SandboxGraph = {
      nodes: [...naiveGraph.nodes.filter((n) => n.id !== "gen"), node("grade", "grade"), node("rewrite", "rewrite")],
      edges: [edge("chunk", "dense"), edge("embed", "dense"), edge("dense", "grade"), edge("grade", "rewrite")],
    };
    const results = await executeGraph({
      graph,
      queryText: "original query text",
      chunkIndex,
      activePreset: null,
    });
    const rewrite = results.get("rewrite");
    expect(rewrite && "payload" in rewrite && rewrite.kind === "rewrite").toBe(true);
    if (rewrite && "payload" in rewrite && rewrite.kind === "rewrite") {
      expect(rewrite.payload.from).toBe("original query text");
      expect(rewrite.payload.to).toBe("original query text");
      expect(rewrite.explain).toContain("No real rewrite");
    }
  });

  it("a second embed_query fed by rewrite embeds the rewrite's output text, not the original query box", async () => {
    const graph: SandboxGraph = {
      nodes: [
        node("chunk", "chunk"),
        node("embed1", "embed_query"),
        node("dense1", "retrieve_dense"),
        node("grade1", "grade"),
        node("rewrite", "rewrite"),
        node("embed2", "embed_query"),
        node("dense2", "retrieve_dense"),
      ],
      edges: [
        edge("chunk", "dense1"),
        edge("embed1", "dense1"),
        edge("dense1", "grade1"),
        edge("grade1", "rewrite"),
        edge("rewrite", "embed2"),
        edge("chunk", "dense2"),
        edge("embed2", "dense2"),
      ],
    };
    await executeGraph({ graph, queryText: "original query text", chunkIndex, activePreset: null });
    // rewrite is a passthrough outside a preset, so embed2 re-embeds the
    // same text -- but it must go through the rewrite node's own output,
    // not bypass straight to the global query box.
    expect(embedQueryMock).toHaveBeenNthCalledWith(1, "original query text");
    expect(embedQueryMock).toHaveBeenNthCalledWith(2, "original query text");
  });

  it("fuse genuinely combines live dense and sparse results via real RRF, not a mock", async () => {
    const graph: SandboxGraph = {
      nodes: [
        node("chunk", "chunk"),
        node("embed", "embed_query"),
        node("dense", "retrieve_dense"),
        node("sparse", "retrieve_sparse"),
        node("fuse", "fuse"),
      ],
      edges: [
        edge("chunk", "dense"),
        edge("embed", "dense"),
        edge("chunk", "sparse"),
        edge("embed", "sparse"),
        edge("dense", "fuse"),
        edge("sparse", "fuse"),
      ],
    };
    const results = await executeGraph({ graph, queryText: "q", chunkIndex, activePreset: null });
    const fuse = results.get("fuse");
    expect(fuse && "payload" in fuse && fuse.kind === "fuse").toBe(true);
    if (fuse && "payload" in fuse && fuse.kind === "fuse") {
      // a::0 appears in both dense (rank1) and sparse (rank2) -- should be
      // fused with a nonzero combined score and be present.
      const ids = fuse.payload.results.map((r) => r.chunk_id);
      expect(ids).toContain("a::0");
      expect(ids).toContain("b::0");
      expect(ids).toContain("c::0");
    }
  });

  it("chunk node reports the real chunk count, not a fabricated one", async () => {
    const results = await executeGraph({
      graph: { nodes: [node("chunk", "chunk")], edges: [] },
      queryText: "q",
      chunkIndex,
      activePreset: null,
    });
    const chunk = results.get("chunk");
    expect(chunk && chunk.kind === "chunk" && chunk.chunkCount).toBe(3);
  });
});

describe("executeGraph -- exact preset match replays the real recorded not-live nodes verbatim", () => {
  const fakeTrace: Trace = {
    trace_id: "naive::q01",
    architecture: "naive",
    question: "What does LoRA freeze?",
    answer: "LoRA freezes the base model.",
    metrics: { latency_ms: 100, llm_calls: 1, prompt_tokens: 10, completion_tokens: 5 },
    nodes: [
      { id: "n1", kind: "embed_query", label: "Embed", parent_ids: [], duration_ms: 1, explain: "e", payload: { dims: 384, preview: [] } },
      { id: "n2", kind: "retrieve_dense", label: "Retrieve", parent_ids: ["n1"], duration_ms: 1, explain: "e", payload: { results: [], k: 5 } },
      {
        id: "n3",
        kind: "generate",
        label: "Generate",
        parent_ids: ["n2"],
        duration_ms: 1,
        explain: "e",
        payload: { output: "LoRA freezes the base model -- this is the REAL recorded answer.", prompt_preview: "p", tokens: 20 },
      },
    ],
  };

  it("generate replays the exact real recorded answer, verbatim, when the preset is active", async () => {
    const results = await executeGraph({
      graph: naiveGraph,
      queryText: "what does LoRA freeze",
      chunkIndex,
      activePreset: { trace: fakeTrace, replayMap: { gen: "n3" } },
    });
    const gen = results.get("gen");
    expect(gen && "payload" in gen && gen.kind === "generate").toBe(true);
    if (gen && "payload" in gen && gen.kind === "generate") {
      expect(gen.payload.output).toBe("LoRA freezes the base model -- this is the REAL recorded answer.");
      expect(gen.payload.output).not.toContain("EXTRACTIVE");
    }
  });

  it("a node the preset's replayMap doesn't cover still runs extractively even while a preset is active", async () => {
    const graph: SandboxGraph = {
      nodes: [...naiveGraph.nodes, node("grade", "grade")],
      edges: [...naiveGraph.edges, edge("dense", "grade")],
    };
    const results = await executeGraph({
      graph,
      queryText: "what does LoRA freeze",
      chunkIndex,
      // replayMap only covers "gen", not the extra "grade" node this
      // custom graph added on top of the preset.
      activePreset: { trace: fakeTrace, replayMap: { gen: "n3" } },
    });
    const grade = results.get("grade");
    expect(grade && "payload" in grade && grade.kind === "grade").toBe(true);
    if (grade && "payload" in grade && grade.kind === "grade") {
      expect(grade.explain).toContain("lexical-overlap heuristic");
      expect(grade.payload.judgements[0]?.reason).toContain("Extractive heuristic");
    }
  });
});

describe("executeGraph -- execution order and defensive cycle handling", () => {
  it("executes nodes in real dependency order (parents complete before children)", async () => {
    const order: string[] = [];
    await executeGraph({
      graph: naiveGraph,
      queryText: "q",
      chunkIndex,
      activePreset: null,
      onNodeComplete: (id) => order.push(id),
    });
    expect(order.indexOf("chunk")).toBeLessThan(order.indexOf("dense"));
    expect(order.indexOf("embed")).toBeLessThan(order.indexOf("dense"));
    expect(order.indexOf("dense")).toBeLessThan(order.indexOf("gen"));
  });

  it("throws a clear error rather than hanging or silently misbehaving on a cyclic graph", async () => {
    const graph: SandboxGraph = {
      nodes: [node("a", "retrieve_dense"), node("b", "fuse")],
      edges: [edge("a", "b"), edge("b", "a")],
    };
    await expect(executeGraph({ graph, queryText: "q", chunkIndex, activePreset: null })).rejects.toThrow(/cycle/);
  });
});
