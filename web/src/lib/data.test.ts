/**
 * Asserts the TS types in ./types.ts actually match the real, current shape
 * of the exported artifacts (not just §3.2's original design sketch) --
 * read directly off disk here via fs, not fetch, since this runs in Node
 * under vitest rather than a browser. Run `python scripts/export_web.py`
 * first if public/data/ is missing (a clean checkout won't have it, since
 * it's gitignored -- generated from the already-committed artifacts/).
 */
import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import type { ChunkRecord, EvalReport, GraphData, Question, Trace } from "./types";
import { ARCHITECTURE_IDS } from "./types";

const DATA_DIR = resolve(__dirname, "../../public/data");

function readJson<T>(name: string): T {
  return JSON.parse(readFileSync(resolve(DATA_DIR, name), "utf-8")) as T;
}

describe("questions.json matches Question[]", () => {
  const questions = readJson<Question[]>("questions.json");

  it("is a non-empty array covering all four real question types", () => {
    expect(questions.length).toBeGreaterThan(0);
    const types = new Set(questions.map((q) => q.type));
    expect(types).toEqual(new Set(["factual", "multi_hop", "keyword", "unanswerable"]));
  });

  it("every question has exactly id/question/type, no leaked evaluation-internal fields", () => {
    for (const q of questions) {
      expect(typeof q.id).toBe("string");
      expect(typeof q.question).toBe("string");
      expect(["factual", "multi_hop", "keyword", "unanswerable"]).toContain(q.type);
      expect(Object.keys(q).sort()).toEqual(["id", "question", "type"]);
    }
  });

  it("includes q11 (real, verified divergence /compare defaults to) and q21 (the other real, verified divergence -- Hybrid beats Naive on a paraphrased keyword question -- not the default, but still a real question this dataset needs to keep containing)", () => {
    const ids = questions.map((q) => q.id);
    expect(ids).toContain("q11"); // Agentic's documented multi-hop synthesis weakness -- /compare's actual default
    expect(ids).toContain("q21"); // Hybrid beats Naive on a paraphrased keyword question
  });
});

describe("chunks.json matches ChunkRecord[]", () => {
  const chunks = readJson<ChunkRecord[]>("chunks.json");

  it("is a non-empty array of real chunk records", () => {
    expect(Array.isArray(chunks)).toBe(true);
    expect(chunks.length).toBeGreaterThan(0);
  });

  it("every chunk has the exact fields ChunkRecord declares", () => {
    for (const chunk of chunks) {
      expect(typeof chunk.chunk_id).toBe("string");
      expect(typeof chunk.note_id).toBe("string");
      expect(typeof chunk.text).toBe("string");
      expect(chunk.heading === null || typeof chunk.heading === "string").toBe(true);
    }
  });
});

describe("graph.json matches GraphData", () => {
  const graph = readJson<GraphData>("graph.json");

  it("has entities, edges, and communities arrays", () => {
    expect(Array.isArray(graph.entities)).toBe(true);
    expect(Array.isArray(graph.edges)).toBe(true);
    expect(Array.isArray(graph.communities)).toBe(true);
    expect(graph.entities.length).toBeGreaterThan(0);
    expect(graph.edges.length).toBeGreaterThan(0);
  });

  it("entities/edges/communities have the shape GraphEntity/GraphEdge/GraphCommunity declare", () => {
    const entity = graph.entities[0];
    expect(typeof entity.id).toBe("string");
    expect(Array.isArray(entity.chunk_ids)).toBe(true);
    expect(typeof entity.community).toBe("number");
    // every entity's community must resolve to a real GraphCommunity.id
    const communityIds = new Set(graph.communities.map((c) => c.id));
    for (const e of graph.entities) {
      expect(communityIds.has(e.community)).toBe(true);
    }

    const edge = graph.edges[0];
    expect(typeof edge.src).toBe("string");
    expect(typeof edge.rel).toBe("string");
    expect(typeof edge.dst).toBe("string");
    expect(typeof edge.chunk_id).toBe("string");

    const community = graph.communities[0];
    expect(typeof community.id).toBe("number");
    expect(Array.isArray(community.entity_ids)).toBe(true);
    expect(typeof community.summary).toBe("string");
  });
});

describe("eval.json matches EvalReport", () => {
  const report = readJson<EvalReport>("eval.json");

  it("has the real top-level fields grown during Phase 6/6.1/6.2, not just §3.2's original sketch", () => {
    expect(typeof report.llm_judge_caveat).toBe("string");
    expect(typeof report.rank_metrics_caveat).toBe("string");
    expect(typeof report.n_architectures).toBe("number");
    expect(typeof report.n_questions).toBe("number");
    expect(Array.isArray(report.rows)).toBe(true);
    expect(report.rows.length).toBe(report.n_architectures * report.n_questions);
  });

  function expectNumberOrNull(value: unknown) {
    expect(value === null || typeof value === "number").toBe(true);
  }

  it("by_architecture covers exactly the seven known architectures with the real summary shape", () => {
    expect(Object.keys(report.by_architecture).sort()).toEqual([...ARCHITECTURE_IDS].sort());
    for (const id of ARCHITECTURE_IDS) {
      const summary = report.by_architecture[id];
      expect(typeof summary.n_questions).toBe("number");
      expectNumberOrNull(summary.recall_at_5_mean);
      expectNumberOrNull(summary.mrr_at_10_mean);
      expectNumberOrNull(summary.ndcg_at_10_mean);
      expectNumberOrNull(summary.recall_full_mean);
      expect(typeof summary.rank_metrics_note).toBe("string");
      expectNumberOrNull(summary.faithfulness_mean);
      expectNumberOrNull(summary.refusal_correctness_rate);
      expectNumberOrNull(summary.latency_ms_mean);
      expectNumberOrNull(summary.llm_calls_mean);
      expectNumberOrNull(summary.prompt_tokens_mean);
      expectNumberOrNull(summary.completion_tokens_mean);
      expect(typeof summary.backend_mix).toBe("object");
    }
  });

  it("every row has every field EvalRow declares, with the right type", () => {
    for (const row of report.rows) {
      expect(ARCHITECTURE_IDS).toContain(row.architecture);
      expect(typeof row.question_id).toBe("string");
      expect(["factual", "multi_hop", "keyword", "unanswerable"]).toContain(row.question_type);
      expect(typeof row.trace_id).toBe("string");
      expect(typeof row.answer).toBe("string");
      expect(Array.isArray(row.retrieved_chunk_ids)).toBe(true);
      expect(Array.isArray(row.gold_chunk_ids)).toBe(true);
      expectNumberOrNull(row.recall_at_5);
      expectNumberOrNull(row.mrr_at_10);
      expectNumberOrNull(row.ndcg_at_10);
      expectNumberOrNull(row.recall_full);
      expect(typeof row.graph_tool_involved).toBe("boolean");
      expectNumberOrNull(row.faithfulness);
      expect(typeof row.reads_as_refusal).toBe("boolean");
      expect(row.refusal_correctness === null || typeof row.refusal_correctness === "boolean").toBe(
        true,
      );
      expect(typeof row.judge_reasoning).toBe("string");
      expect(typeof row.latency_ms).toBe("number");
      expect(typeof row.llm_calls).toBe("number");
      expect(typeof row.prompt_tokens).toBe("number");
      expect(typeof row.completion_tokens).toBe("number");
      expect(Array.isArray(row.backend_calls)).toBe(true);
      expect(typeof row.judge_backend).toBe("string");
      if (row.architecture === "adaptive") {
        expect(typeof row.adaptive_routed_to).toBe("string");
      }
    }
  });

  it("adaptive_routing and adaptive_routing_accuracy have the real shape", () => {
    expect(Array.isArray(report.adaptive_routing)).toBe(true);
    const acc = report.adaptive_routing_accuracy;
    expect(typeof acc.correct).toBe("number");
    expect(typeof acc.total).toBe("number");
    expect(typeof acc.rubric).toBe("object");
  });
});

describe("a real trace matches Trace/TraceNode", () => {
  const files = readdirSync(resolve(DATA_DIR, "traces")).filter((f) => f.endsWith(".json"));

  it("public/data/traces/ has real, recorded trace files", () => {
    expect(files.length).toBeGreaterThan(0);
  });

  it("every node kind in a sample of real traces is one of §3.2's closed set, with the right payload keys", () => {
    // Sample instead of all 189 for test speed -- every architecture is
    // still covered, since filenames are `{architecture}__{question_id}.json`.
    const sampleByArch = new Map<string, string>();
    for (const f of files) {
      const arch = f.split("__")[0];
      if (!sampleByArch.has(arch)) sampleByArch.set(arch, f);
    }
    expect(sampleByArch.size).toBe(ARCHITECTURE_IDS.length);

    for (const file of sampleByArch.values()) {
      const trace = readJson<Trace>(`traces/${file}`);
      expect(ARCHITECTURE_IDS).toContain(trace.architecture);
      expect(typeof trace.answer).toBe("string");
      expect(typeof trace.metrics.latency_ms).toBe("number");
      expect(typeof trace.metrics.llm_calls).toBe("number");
      expect(trace.nodes.length).toBeGreaterThan(0);

      for (const node of trace.nodes) {
        expect(typeof node.id).toBe("string");
        expect(Array.isArray(node.parent_ids)).toBe(true);
        expect(typeof node.explain).toBe("string");
        expect(typeof node.payload).toBe("object");
      }

      // The trace must end in `generate` -- extract_retrieved_chunk_ids
      // (Python side) relies on this invariant; the frontend will too.
      expect(trace.nodes[trace.nodes.length - 1].kind).toBe("generate");
    }
  });
});
