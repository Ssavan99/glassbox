import { loadChunks } from "../lib/data";
import type { RetrievalResult } from "../lib/types";

const EMBEDDING_DIM = 384;

/** Fetches the real `vectors.f32` artifact (raw, row-major Float32,
 * written by scripts/build_index.py) as an ArrayBuffer and wraps it as a
 * `Float32Array` view -- no copy, no parsing beyond the typed-array cast.
 * Row i is chunk i's vector, in the exact same order as `chunks.json`
 * (both are built from the same `chunks` list in `build_index.py`'s single
 * pass), which is why this reuses `loadChunks()` for the parallel
 * chunk_id array rather than trusting bm25.json's own `chunk_ids` (same
 * order in practice, but chunks.json is the authoritative source every
 * other route in this app already reads chunk records from). */
let vectorsPromise: Promise<{ chunkIds: string[]; vectors: Float32Array }> | undefined;

function loadVectors(): Promise<{ chunkIds: string[]; vectors: Float32Array }> {
  vectorsPromise ??= (async () => {
    const [chunks, buf] = await Promise.all([
      loadChunks(),
      fetch(`${import.meta.env.BASE_URL}data/vectors.f32`).then((res) => {
        if (!res.ok) {
          throw new Error(`failed to load vectors.f32: ${res.status} ${res.statusText}`);
        }
        return res.arrayBuffer();
      }),
    ]);
    const vectors = new Float32Array(buf);
    const expectedLength = chunks.length * EMBEDDING_DIM;
    if (vectors.length !== expectedLength) {
      throw new Error(
        `vectors.f32 has ${vectors.length} floats but chunks.json has ${chunks.length} chunks ` +
          `(expected ${expectedLength}) -- artifacts are out of sync, re-run scripts/export_web.py`,
      );
    }
    return { chunkIds: chunks.map((c) => c.chunk_id), vectors };
  })();
  return vectorsPromise;
}

/** Real dot-product search over the real corpus vectors -- identical
 * operation to `engine/store.py`'s `DenseStore.search()`, since both the
 * Python-computed corpus vectors and (via sandbox/embedding.ts) the
 * live-computed query vector are L2-normalized, making dot product ==
 * cosine similarity. */
export async function denseSearch(
  queryVector: Float32Array,
  k: number,
): Promise<RetrievalResult[]> {
  const { chunkIds, vectors } = await loadVectors();
  if (queryVector.length !== EMBEDDING_DIM) {
    throw new Error(`query vector has ${queryVector.length} dims, expected ${EMBEDDING_DIM}`);
  }

  const scores: number[] = Array.from({ length: chunkIds.length });
  for (let i = 0; i < chunkIds.length; i++) {
    let dot = 0;
    const base = i * EMBEDDING_DIM;
    for (let d = 0; d < EMBEDDING_DIM; d++) {
      dot += vectors[base + d] * queryVector[d];
    }
    scores[i] = dot;
  }

  const order = chunkIds.map((_, i) => i).sort((a, b) => scores[b] - scores[a]);
  return order.slice(0, Math.max(0, k)).map((i, rank) => ({
    chunk_id: chunkIds[i],
    score: scores[i],
    rank: rank + 1,
  }));
}
