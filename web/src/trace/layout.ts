import dagre from "@dagrejs/dagre";
import type { Edge, Node as FlowNode } from "@xyflow/react";

export const NODE_WIDTH = 200;
export const NODE_HEIGHT = 64;

/** Lays a trace's DAG out top-to-bottom with dagre -- chosen over left-to-right
 * specifically because it degrades gracefully at mobile widths (a tall,
 * narrow, scrollable canvas beats a wide one requiring horizontal pan on a
 * 375px screen). Returns new node objects with `position` set; doesn't
 * mutate the input. */
export function layoutNodes<T extends FlowNode>(nodes: T[], edges: Edge[]): T[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 32, ranksep: 56 });

  for (const node of nodes) {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  for (const edge of edges) {
    g.setEdge(edge.source, edge.target);
  }

  dagre.layout(g);

  return nodes.map((node) => {
    const { x, y } = g.node(node.id);
    return {
      ...node,
      // dagre positions by center; React Flow positions by top-left.
      position: { x: x - NODE_WIDTH / 2, y: y - NODE_HEIGHT / 2 },
    };
  });
}
