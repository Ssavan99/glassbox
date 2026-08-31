import { describe, expect, it } from "vitest";
import type { Edge, Node as FlowNode } from "@xyflow/react";
import { layoutNodes, NODE_WIDTH } from "./layout";

function node(id: string): FlowNode {
  return { id, type: "x", position: { x: 0, y: 0 }, data: {} };
}

describe("layoutNodes", () => {
  it("gives every node a finite, real position", () => {
    const nodes = [node("a"), node("b"), node("c")];
    const edges: Edge[] = [
      { id: "a-b", source: "a", target: "b" },
      { id: "b-c", source: "b", target: "c" },
    ];

    const laid = layoutNodes(nodes, edges);

    expect(laid).toHaveLength(3);
    for (const n of laid) {
      expect(Number.isFinite(n.position.x)).toBe(true);
      expect(Number.isFinite(n.position.y)).toBe(true);
    }
  });

  it("does not mutate the input node array", () => {
    const nodes = [node("a"), node("b")];
    const original = nodes.map((n) => ({ ...n.position }));
    layoutNodes(nodes, [{ id: "a-b", source: "a", target: "b" }]);
    expect(nodes.map((n) => n.position)).toEqual(original);
  });

  it("orders a linear chain top-to-bottom (later nodes get a greater y)", () => {
    // rankdir: "TB" -- a real chain like embed_query -> retrieve -> generate
    // should lay out with strictly increasing y per rank, matching how a
    // trace's own node array order reads top-to-bottom in the canvas.
    const nodes = [node("n1"), node("n2"), node("n3")];
    const edges: Edge[] = [
      { id: "n1-n2", source: "n1", target: "n2" },
      { id: "n2-n3", source: "n2", target: "n3" },
    ];

    const laid = layoutNodes(nodes, edges);
    const byId = new Map(laid.map((n) => [n.id, n.position]));

    expect(byId.get("n1")!.y).toBeLessThan(byId.get("n2")!.y);
    expect(byId.get("n2")!.y).toBeLessThan(byId.get("n3")!.y);
  });

  it("keeps sibling nodes (same rank, common parent) from overlapping", () => {
    // Mirrors Agentic's real shape: one node fans out into several parallel
    // branches. If the dagre-center -> React-Flow-top-left conversion used
    // the wrong sign or the wrong node dimensions, siblings placed side by
    // side by dagre could end up drawn on top of each other despite dagre
    // itself having spaced their centers out correctly.
    const nodes = [node("root"), node("a"), node("b"), node("c")];
    const edges: Edge[] = [
      { id: "root-a", source: "root", target: "a" },
      { id: "root-b", source: "root", target: "b" },
      { id: "root-c", source: "root", target: "c" },
    ];

    const laid = layoutNodes(nodes, edges);
    const siblings = laid.filter((n) => n.id !== "root");
    const xs = siblings.map((n) => n.position.x).sort((x, y) => x - y);

    for (let i = 1; i < xs.length; i++) {
      expect(xs[i] - xs[i - 1]).toBeGreaterThanOrEqual(NODE_WIDTH);
    }
  });

  it("handles an empty graph without crashing", () => {
    expect(layoutNodes([], [])).toEqual([]);
  });
});
