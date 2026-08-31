import type { ArchitectureId, ChunkRecord, EvalReport, GraphData, Trace } from "./types";

/** All data is exported by scripts/export_web.py into public/data/ — see
 * that script for the exact copy. Respects Vite's configured `base` so
 * fetches work both at `/` in dev and `/glassbox/` in production. */
const DATA_BASE = `${import.meta.env.BASE_URL}data`;

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${DATA_BASE}/${path}`);
  if (!res.ok) {
    throw new Error(`failed to load ${path}: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

// Module-level memoization — these files don't change at runtime, and
// several routes/components load the same one independently.
let chunksPromise: Promise<ChunkRecord[]> | undefined;
let evalPromise: Promise<EvalReport> | undefined;
let graphPromise: Promise<GraphData> | undefined;
const tracePromises = new Map<string, Promise<Trace>>();

export function loadChunks(): Promise<ChunkRecord[]> {
  chunksPromise ??= fetchJson<ChunkRecord[]>("chunks.json");
  return chunksPromise;
}

export function loadEval(): Promise<EvalReport> {
  evalPromise ??= fetchJson<EvalReport>("eval.json");
  return evalPromise;
}

export function loadGraph(): Promise<GraphData> {
  graphPromise ??= fetchJson<GraphData>("graph.json");
  return graphPromise;
}

export function loadTrace(architecture: ArchitectureId, questionId: string): Promise<Trace> {
  const key = `${architecture}__${questionId}`;
  let promise = tracePromises.get(key);
  if (!promise) {
    promise = fetchJson<Trace>(`traces/${key}.json`);
    tracePromises.set(key, promise);
  }
  return promise;
}

/** Builds a chunk_id -> ChunkRecord lookup, the join every trace-rendering
 * component needs (chunk text is never inlined in a trace, per D2). */
export async function loadChunkIndex(): Promise<Map<string, ChunkRecord>> {
  const chunks = await loadChunks();
  return new Map(chunks.map((c) => [c.chunk_id, c]));
}
