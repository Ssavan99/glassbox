import { loadChunksArtifact } from "../lib/data";
import type { RetrievalResult } from "../lib/types";

const EMBEDDING_DIM = 384;

const VECTOR_BUILD_ID_PREFIX = "GLASSBOX_BUILD_ID:";
const VECTOR_BUILD_ID_LENGTH = 64;
const VECTOR_HEADER_SIZE = VECTOR_BUILD_ID_PREFIX.length + VECTOR_BUILD_ID_LENGTH + 1;

/** Fetches the real `vectors.f32` artifact. Its fixed-size build-id header
 * is checked against chunks.json before the remaining row-major Float32
 * payload is used, so a partially published artifact generation fails fast. */
let vectorsPromise: Promise<{ chunkIds: string[]; vectors: Float32Array }> | undefined;

function loadVectors(): Promise<{ chunkIds: string[]; vectors: Float32Array }> {
  vectorsPromise ??= (async () => {
    const [chunksArtifact, buf] = await Promise.all([
      loadChunksArtifact(),
      fetch(`${import.meta.env.BASE_URL}data/vectors.f32`).then((res) => {
        if (!res.ok) {
          throw new Error(`failed to load vectors.f32: ${res.status} ${res.statusText}`);
        }
        return res.arrayBuffer();
      }),
    ]);
    const header = new TextDecoder().decode(new Uint8Array(buf, 0, VECTOR_HEADER_SIZE));
    const vectorBuildId = header.slice(
      VECTOR_BUILD_ID_PREFIX.length,
      VECTOR_BUILD_ID_PREFIX.length + VECTOR_BUILD_ID_LENGTH,
    );
    if (
      !header.startsWith(VECTOR_BUILD_ID_PREFIX) ||
      !header.endsWith("\n") ||
      !/^[0-9a-f]{64}$/.test(vectorBuildId)
    ) {
      throw new Error("vectors.f32 is missing a valid retrieval build-id header");
    }
    if (vectorBuildId !== chunksArtifact.build_id) {
      throw new Error(
        "vectors.f32 and chunks.json have different build ids -- artifacts are out of sync, " +
          "re-run scripts/export_web.py",
      );
    }
    const vectors = new Float32Array(buf.slice(VECTOR_HEADER_SIZE));
    const expectedLength = chunksArtifact.chunks.length * EMBEDDING_DIM;
    if (vectors.length !== expectedLength) {
      throw new Error(
        `vectors.f32 has ${vectors.length} floats but chunks.json has ${chunksArtifact.chunks.length} chunks ` +
          `(expected ${expectedLength}) -- artifacts are out of sync, re-run scripts/export_web.py`,
      );
    }
    return { chunkIds: chunksArtifact.chunks.map((c) => c.chunk_id), vectors };
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
