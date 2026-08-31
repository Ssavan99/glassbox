import { describe, expect, it } from "vitest";
import type { SandboxGraph } from "./types";
import { validateGraph } from "./validate";

function node(id: string, kind: SandboxGraph["nodes"][number]["kind"]) {
  return { id, kind, position: { x: 0, y: 0 } };
}
function edge(source: string, target: string) {
  return { id: `${source}->${target}`, source, target };
}

describe("validateGraph", () => {
  it("accepts a valid naive shape: chunk + embed_query -> retrieve_dense -> generate", () => {
    const graph: SandboxGraph = {
      nodes: [
        node("c", "chunk"),
        node("e", "embed_query"),
        node("d", "retrieve_dense"),
        node("g", "generate"),
      ],
      edges: [edge("c", "d"), edge("e", "d"), edge("d", "g")],
    };
    const result = validateGraph(graph);
    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });

  it("rejects retrieve_dense missing its chunk input", () => {
    const graph: SandboxGraph = {
      nodes: [node("e", "embed_query"), node("d", "retrieve_dense")],
      edges: [edge("e", "d")],
    };
    const result = validateGraph(graph);
    expect(result.valid).toBe(false);
    expect(result.errors).toContainEqual({
      nodeId: "d",
      message: "Dense Retrieve needs an input from Chunk (has 0).",
    });
  });

  it("rejects retrieve_dense missing its embed_query input", () => {
    const graph: SandboxGraph = {
      nodes: [node("c", "chunk"), node("d", "retrieve_dense")],
      edges: [edge("c", "d")],
    };
    const result = validateGraph(graph);
    expect(result.errors).toContainEqual({
      nodeId: "d",
      message: "Dense Retrieve needs an input from Embed Query (has 0).",
    });
  });

  it("requires fuse to have 2 retrieval inputs, not 1", () => {
    const graph: SandboxGraph = {
      nodes: [node("d", "retrieve_dense"), node("f", "fuse")],
      edges: [edge("d", "f")],
    };
    const result = validateGraph(graph);
    expect(result.errors).toContainEqual({
      nodeId: "f",
      message: "Fuse needs 2 inputs from Dense Retrieve or Sparse Retrieve (has 1).",
    });
  });

  it("accepts fuse fed by one dense and one sparse retrieve (real Hybrid shape)", () => {
    const graph: SandboxGraph = {
      nodes: [
        node("c", "chunk"),
        node("e", "embed_query"),
        node("d", "retrieve_dense"),
        node("s", "retrieve_sparse"),
        node("f", "fuse"),
      ],
      edges: [edge("c", "d"), edge("e", "d"), edge("c", "s"), edge("e", "s"), edge("d", "f"), edge("s", "f")],
    };
    const result = validateGraph(graph);
    expect(result.errors).toEqual([]);
    expect(result.valid).toBe(true);
  });

  it("rejects a rewrite node with no grade input", () => {
    const graph: SandboxGraph = { nodes: [node("r", "rewrite")], edges: [] };
    const result = validateGraph(graph);
    expect(result.errors).toContainEqual({
      nodeId: "r",
      message: "Rewrite needs an input from Grade (has 0).",
    });
  });

  it("detects a direct two-node cycle", () => {
    const graph: SandboxGraph = {
      nodes: [node("a", "retrieve_dense"), node("b", "fuse")],
      edges: [edge("a", "b"), edge("b", "a")],
    };
    const result = validateGraph(graph);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.nodeId === null && e.message.includes("cycle"))).toBe(true);
  });

  it("detects a longer indirect cycle", () => {
    const graph: SandboxGraph = {
      nodes: [node("a", "chunk"), node("b", "embed_query"), node("c", "retrieve_dense")],
      edges: [edge("a", "b"), edge("b", "c"), edge("c", "a")],
    };
    expect(validateGraph(graph).valid).toBe(false);
  });

  it("does not flag a diamond shape (two paths converging, no cycle) as cyclic", () => {
    const graph: SandboxGraph = {
      nodes: [
        node("e", "embed_query"),
        node("c", "chunk"),
        node("d", "retrieve_dense"),
        node("s", "retrieve_sparse"),
        node("f", "fuse"),
      ],
      edges: [edge("c", "d"), edge("e", "d"), edge("c", "s"), edge("e", "s"), edge("d", "f"), edge("s", "f")],
    };
    expect(validateGraph(graph).valid).toBe(true);
  });

  it("reports errors on multiple independent nodes at once, not just the first", () => {
    const graph: SandboxGraph = {
      nodes: [node("d", "retrieve_dense"), node("r", "rewrite")],
      edges: [],
    };
    const result = validateGraph(graph);
    const nodeIdsWithErrors = new Set(result.errors.map((e) => e.nodeId));
    expect(nodeIdsWithErrors).toEqual(new Set(["d", "r"]));
  });

  it("chunk and embed_query nodes alone (no edges) are valid -- they're sources", () => {
    const graph: SandboxGraph = { nodes: [node("c", "chunk"), node("e", "embed_query")], edges: [] };
    expect(validateGraph(graph).valid).toBe(true);
  });

  it("an empty graph is valid", () => {
    expect(validateGraph({ nodes: [], edges: [] }).valid).toBe(true);
  });
});
