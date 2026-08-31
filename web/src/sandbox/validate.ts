import { PALETTE } from "./palette";
import type { SandboxGraph, SandboxNode } from "./types";

export interface ValidationError {
  /** Node id the error is attached to, or `null` for a graph-wide error
   * (currently only cycles, which don't belong to one node). */
  nodeId: string | null;
  message: string;
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
}

/** Standard DFS 3-color cycle detection (white/gray/black), returning the
 * id of one node on a cycle if any exists, else null. Which specific node
 * is returned isn't meaningful beyond "a cycle exists somewhere" -- the
 * error message doesn't try to name every node on the cycle. */
function findCycleNode(graph: SandboxGraph): string | null {
  const adjacency = new Map<string, string[]>();
  for (const node of graph.nodes) adjacency.set(node.id, []);
  for (const edge of graph.edges) {
    adjacency.get(edge.source)?.push(edge.target);
  }

  const WHITE = 0;
  const GRAY = 1;
  const BLACK = 2;
  const color = new Map<string, number>(graph.nodes.map((n) => [n.id, WHITE]));

  function visit(id: string): string | null {
    color.set(id, GRAY);
    for (const next of adjacency.get(id) ?? []) {
      const c = color.get(next);
      if (c === GRAY) return next;
      if (c === WHITE) {
        const found = visit(next);
        if (found) return found;
      }
    }
    color.set(id, BLACK);
    return null;
  }

  for (const node of graph.nodes) {
    if (color.get(node.id) === WHITE) {
      const found = visit(node.id);
      if (found) return found;
    }
  }
  return null;
}

function requiredInputErrors(node: SandboxNode, graph: SandboxGraph): string[] {
  const entry = PALETTE[node.kind];
  const incomingSourceKinds = graph.edges
    .filter((e) => e.target === node.id)
    .map((e) => graph.nodes.find((n) => n.id === e.source)?.kind)
    .filter((k): k is SandboxNode["kind"] => k !== undefined);

  const errors: string[] = [];
  for (const req of entry.requiredInputs) {
    const matchCount = incomingSourceKinds.filter((k) => req.kinds.includes(k)).length;
    if (matchCount < req.count) {
      const kindLabels = req.kinds.map((k) => PALETTE[k].label).join(" or ");
      const need = req.count > 1 ? `${req.count} inputs from ${kindLabels}` : `an input from ${kindLabels}`;
      errors.push(`${entry.label} needs ${need} (has ${matchCount}).`);
    }
  }
  return errors;
}

/** Validates a sandbox graph: no cycles, every node's required inputs
 * present (per palette.ts's `requiredInputs`). Returns every violation
 * found, not just the first, so the canvas can show every inline error at
 * once rather than one-at-a-time whack-a-mole. */
export function validateGraph(graph: SandboxGraph): ValidationResult {
  const errors: ValidationError[] = [];

  const cycleNode = findCycleNode(graph);
  if (cycleNode) {
    errors.push({
      nodeId: null,
      message: "This pipeline has a cycle -- a step can't (directly or indirectly) depend on its own output.",
    });
  }

  // Required-input checking still runs even with a cycle present -- a
  // disconnected/malformed node elsewhere in the same graph is a separate,
  // independently-worth-reporting problem, not one the cycle error should
  // suppress.
  for (const node of graph.nodes) {
    for (const message of requiredInputErrors(node, graph)) {
      errors.push({ nodeId: node.id, message });
    }
  }

  return { valid: errors.length === 0, errors };
}
