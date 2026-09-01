import type {
  ArchitectureId,
  ChunksArtifact,
  ChunkRecord,
  CodeExcerpts,
  EvalReport,
  GraphData,
  Question,
  Trace,
} from "./types";

/** All data is exported by scripts/export_web.py into public/data/ (run it
 * before `npm run dev` if that directory is missing -- a fresh clone won't
 * have it, since it's gitignored and generated from the already-committed
 * artifacts/). Respects Vite's configured `base` (`/glassbox/` in both dev
 * and prod -- see vite.config.ts) so fetches resolve correctly either way. */
const DATA_BASE = `${import.meta.env.BASE_URL}data`;

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${DATA_BASE}/${path}`);
  if (!res.ok) {
    throw new Error(`failed to load ${path}: ${res.status} ${res.statusText}`);
  }
  // Vite's dev server serves index.html (200 OK) for any unmatched path
  // (SPA fallback), so a missing public/data/ file doesn't 404 in dev --
  // it silently returns HTML that fails to parse as JSON. Check the
  // content-type so a missing export produces one clear, actionable error
  // instead of a generic "Unexpected token '<'" from a failed .json() call.
  const contentType = res.headers.get("content-type") ?? "";
  if (!contentType.includes("json")) {
    throw new Error(
      `expected JSON loading ${path}, got content-type ${contentType || "(none)"} -- ` +
        `is public/data/ missing? Run \`python scripts/export_web.py\` from the repo root.`,
    );
  }
  return (await res.json()) as T;
}

// Module-level memoization — these files don't change at runtime, and
// several routes/components load the same one independently.
let chunksPromise: Promise<ChunkRecord[]> | undefined;
let chunksArtifactPromise: Promise<ChunksArtifact> | undefined;
let evalPromise: Promise<EvalReport> | undefined;
let graphPromise: Promise<GraphData> | undefined;
let questionsPromise: Promise<Question[]> | undefined;
let codeExcerptsPromise: Promise<CodeExcerpts> | undefined;
const tracePromises = new Map<string, Promise<Trace>>();

export function loadChunks(): Promise<ChunkRecord[]> {
  chunksPromise ??= loadChunksArtifact().then((artifact) => artifact.chunks);
  return chunksPromise;
}

/** Loads the chunk records together with the retrieval build id shared by the
 * retrieval artifact bundle. */
export function loadChunksArtifact(): Promise<ChunksArtifact> {
  chunksArtifactPromise ??= fetchJson<ChunksArtifact>("chunks.json");
  return chunksArtifactPromise;
}

export function loadEval(): Promise<EvalReport> {
  evalPromise ??= fetchJson<EvalReport>("eval.json");
  return evalPromise;
}

export function loadGraph(): Promise<GraphData> {
  graphPromise ??= fetchJson<GraphData>("graph.json");
  return graphPromise;
}

export function loadQuestions(): Promise<Question[]> {
  questionsPromise ??= fetchJson<Question[]>("questions.json");
  return questionsPromise;
}

export function loadCodeExcerpts(): Promise<CodeExcerpts> {
  codeExcerptsPromise ??= fetchJson<CodeExcerpts>("code_excerpts.json");
  return codeExcerptsPromise;
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
