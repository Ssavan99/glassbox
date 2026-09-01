import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import type { Trace } from "../lib/types";
import { PRESETS } from "./presets";
import { validateGraph } from "./validate";

const DATA_DIR = resolve(__dirname, "../../public/data");

function readTrace(architecture: string, questionId: string): Trace {
  return JSON.parse(
    readFileSync(resolve(DATA_DIR, "traces", `${architecture}__${questionId}.json`), "utf-8"),
  ) as Trace;
}

describe("PRESETS", () => {
  it("every preset's graph passes validateGraph cleanly (no cycles, all required inputs wired)", () => {
    for (const preset of PRESETS) {
      const result = validateGraph(preset.graph);
      expect(result.errors, `${preset.id} should have no validation errors`).toEqual([]);
      expect(result.valid).toBe(true);
    }
  });

  it("every replayMap entry names a sandbox node that actually exists in the preset's own graph", () => {
    for (const preset of PRESETS) {
      const nodeIds = new Set(preset.graph.nodes.map((n) => n.id));
      for (const sandboxNodeId of Object.keys(preset.replayMap)) {
        expect(nodeIds.has(sandboxNodeId), `${preset.id}: replayMap references unknown node "${sandboxNodeId}"`).toBe(
          true,
        );
      }
    }
  });

  it("every replayMap target is only for a not-live kind (grade/rewrite/generate)", () => {
    const notLiveKinds = new Set(["grade", "rewrite", "generate"]);
    for (const preset of PRESETS) {
      for (const sandboxNodeId of Object.keys(preset.replayMap)) {
        const kind = preset.graph.nodes.find((n) => n.id === sandboxNodeId)?.kind;
        expect(kind && notLiveKinds.has(kind), `${preset.id}: "${sandboxNodeId}" is kind "${kind}"`).toBe(true);
      }
    }
  });

  it("every replayMap entry points at a real trace node of the *matching kind* -- catches an id-swap between two same-kind nodes silently attributing the wrong real judgement to the wrong step", () => {
    for (const preset of PRESETS) {
      const trace = readTrace(preset.architecture, preset.questionId);
      const traceNodesById = new Map(trace.nodes.map((n) => [n.id, n]));

      for (const [sandboxNodeId, realNodeId] of Object.entries(preset.replayMap)) {
        const sandboxKind = preset.graph.nodes.find((n) => n.id === sandboxNodeId)?.kind;
        const realNode = traceNodesById.get(realNodeId);
        expect(
          realNode,
          `${preset.id}: replayMap points sandbox node "${sandboxNodeId}" at real trace node ` +
            `"${realNodeId}", which does not exist in ${preset.architecture}__${preset.questionId}.json`,
        ).toBeDefined();
        expect(
          realNode!.kind,
          `${preset.id}: sandbox node "${sandboxNodeId}" (kind "${sandboxKind}") is mapped to real ` +
            `node "${realNodeId}" (kind "${realNode!.kind}") -- kinds must match or replay would show ` +
            `the wrong step's real data under the wrong label`,
        ).toBe(sandboxKind);
      }
    }
  });

  it("every real trace's question text exactly matches the preset's query -- an exact-match replay is only honest if this is the literal question that was actually run", () => {
    for (const preset of PRESETS) {
      const trace = readTrace(preset.architecture, preset.questionId);
      expect(trace.question, `${preset.id}: preset query text doesn't match the real trace's own question`).toBe(
        preset.query,
      );
    }
  });

  it("has exactly three presets, one per architecture, matching the plan's requirement", () => {
    expect(PRESETS).toHaveLength(3);
    expect(new Set(PRESETS.map((p) => p.architecture))).toEqual(
      new Set(["naive", "hybrid", "corrective"]),
    );
  });
});
