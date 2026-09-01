import { loadChunksArtifact } from "../lib/data";
import type { RetrievalResult } from "../lib/types";

/**
 * A faithful TypeScript port of Python's `rank_bm25.BM25Okapi`, run over the
 * corpus the Python pipeline already tokenized and exported to
 * `public/data/bm25.json`. The point is that the sandbox's sparse retrieval
 * is the *same* scoring the offline traces used -- not a lookalike -- so a
 * query typed in the browser is directly comparable to a recorded trace.
 *
 * The three constants below are rank_bm25's library defaults, and the Python
 * side never overrides them, so they're hardcoded here rather than exposed.
 */
const K1 = 1.5;
const B = 0.75;
const EPSILON = 0.25;

/** The shape of `public/data/bm25.json`, as written by scripts/export_web.py. */
export interface Bm25Artifact {
  /** Matches chunks.json and vectors.f32 for this retrieval generation. */
  build_id: string;
  /** One chunk id per document, parallel to `tokenized_texts`. */
  chunk_ids: string[];
  /** The pre-tokenized corpus (already lowercased and whitespace-split). */
  tokenized_texts: string[][];
  /**
   * term -> number of *documents* containing that term (rank_bm25's `nd`),
   * precomputed on the Python side. Note this is document frequency, not
   * term frequency -- distinct from the per-document term counts the
   * constructor builds below.
   */
  doc_freqs: Record<string, number>;
  n_docs: number;
}

export type Bm25Result = RetrievalResult;

export interface Bm25Index {
  /**
   * Scores every document against `queryText` and returns the top `k`,
   * sorted by score descending with ties broken by original document order.
   */
  search(queryText: string, k: number): Bm25Result[];
}

/**
 * Matches Python's `text.lower().split()`: lowercase, then split on runs of
 * whitespace with no empty tokens from leading/trailing/repeated whitespace.
 * `"".split(/\s+/)` yields `[""]` in JS, hence the trim and the filter.
 */
export function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .trim()
    .split(/\s+/)
    .filter((t) => t.length > 0);
}

/**
 * Ports `BM25Okapi.__init__` (including its `_calc_idf`) -- all the one-time
 * work -- so that `search()` is just the `get_scores` loop.
 */
export function buildBm25Index(artifact: Bm25Artifact, expectedBuildId?: string): Bm25Index {
  if (expectedBuildId !== undefined && artifact.build_id !== expectedBuildId) {
    throw new Error(
      "bm25.json and chunks.json have different build ids -- artifacts are out of sync, " +
        "re-run scripts/export_web.py",
    );
  }
  const { chunk_ids: chunkIds, tokenized_texts: corpus, doc_freqs: nd } = artifact;
  const corpusSize = corpus.length;

  // Python's `self.doc_freqs`: per-document term -> count. Named differently
  // here because the artifact's top-level `doc_freqs` (`nd`) is a different
  // thing entirely -- corpus-wide document frequency.
  const termFreqsByDoc: Map<string, number>[] = [];
  const docLen: number[] = [];
  let lenSum = 0;
  for (const document of corpus) {
    docLen.push(document.length);
    lenSum += document.length;
    const frequencies = new Map<string, number>();
    for (const word of document) {
      frequencies.set(word, (frequencies.get(word) ?? 0) + 1);
    }
    termFreqsByDoc.push(frequencies);
  }
  const avgdl = lenSum / corpusSize;

  // _calc_idf(nd): compute raw idf, then replace every *negative* idf with
  // epsilon * average_idf. The average is over the raw values (negatives
  // included), and is taken before any replacement -- order matters.
  const idf = new Map<string, number>();
  const negativeIdfs: string[] = [];
  let idfSum = 0;
  for (const [word, freq] of Object.entries(nd)) {
    const value = Math.log(corpusSize - freq + 0.5) - Math.log(freq + 0.5);
    idf.set(word, value);
    idfSum += value;
    if (value < 0) {
      negativeIdfs.push(word);
    }
  }
  const averageIdf = idfSum / idf.size;
  const eps = EPSILON * averageIdf;
  for (const word of negativeIdfs) {
    idf.set(word, eps);
  }

  function scoreAll(query: string[]): number[] {
    const scores: number[] = Array.from({ length: corpusSize }, () => 0);
    for (const q of query) {
      // Out-of-vocabulary query terms score 0 everywhere rather than throwing,
      // matching Python's `self.idf.get(q, 0)`.
      const qIdf = idf.get(q) ?? 0;
      for (let i = 0; i < corpusSize; i += 1) {
        const qFreq = termFreqsByDoc[i].get(q) ?? 0;
        const denom = qFreq + K1 * (1 - B + (B * docLen[i]) / avgdl);
        scores[i] += denom !== 0 ? (qIdf * (qFreq * (K1 + 1))) / denom : 0;
      }
    }
    return scores;
  }

  return {
    search(queryText: string, k: number): Bm25Result[] {
      const scores = scoreAll(tokenize(queryText));
      // Sort by score descending, ties broken by original document order.
      // Array#sort is spec-stable in modern engines, but the explicit index
      // tiebreak makes the guarantee local rather than assumed.
      const order = scores.map((score, index) => ({ score, index }));
      order.sort((a, b) => b.score - a.score || a.index - b.index);
      return order.slice(0, Math.max(0, k)).map((entry, i) => ({
        chunk_id: chunkIds[entry.index],
        score: entry.score,
        rank: i + 1,
      }));
    },
  };
}

/** See the note in lib/data.ts: fetches respect Vite's configured `base`. */
const DATA_BASE = `${import.meta.env.BASE_URL}data`;

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${DATA_BASE}/${path}`);
  if (!res.ok) {
    throw new Error(`failed to load ${path}: ${res.status} ${res.statusText}`);
  }
  // Vite's dev server serves index.html (200 OK) for any unmatched path, so a
  // missing public/data/ file parses as HTML instead of 404ing -- check the
  // content-type to get one clear error instead of "Unexpected token '<'".
  const contentType = res.headers.get("content-type") ?? "";
  if (!contentType.includes("json")) {
    throw new Error(
      `expected JSON loading ${path}, got content-type ${contentType || "(none)"} -- ` +
        `is public/data/ missing? Run \`python scripts/export_web.py\` from the repo root.`,
    );
  }
  return (await res.json()) as T;
}

// Module-level memoization, matching lib/data.ts's loaders: the artifact never
// changes at runtime, and the index build should happen exactly once.
let bm25Promise: Promise<Bm25Index> | undefined;

export function loadBm25Index(): Promise<Bm25Index> {
  bm25Promise ??= Promise.all([
    fetchJson<Bm25Artifact>("bm25.json"),
    loadChunksArtifact(),
  ]).then(([artifact, chunksArtifact]) => buildBm25Index(artifact, chunksArtifact.build_id));
  return bm25Promise;
}
