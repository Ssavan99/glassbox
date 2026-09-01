import type { RetrievalResult } from "../lib/types";

/** RRF_K from engine/config.py -- hardcoded here rather than fetched,
 * since it's a fixed algorithm constant, not corpus-derived data (the same
 * choice `web/src/lib/architectures.ts` and friends make for other
 * Python-side constants that don't change per-build). */
const RRF_K = 60;

/** Real reciprocal rank fusion -- byte-for-byte the same formula as
 * `engine/architectures/hybrid.py`'s `reciprocal_rank_fusion()`:
 * `rrf_score(chunk) = sum(1 / (RRF_K + rank))` over every input list the
 * chunk appears in, rank 1-indexed within that list. A chunk present in
 * only one list still accumulates a nonzero score from that single term. */
export function reciprocalRankFusion(
  rankedLists: RetrievalResult[][],
  k = RRF_K,
): RetrievalResult[] {
  const fused = new Map<string, number>();
  const firstSeenOrder: string[] = [];
  for (const list of rankedLists) {
    for (const result of list) {
      const prior = fused.get(result.chunk_id);
      if (prior === undefined) firstSeenOrder.push(result.chunk_id);
      fused.set(result.chunk_id, (prior ?? 0) + 1 / (k + result.rank));
    }
  }

  const order = [...firstSeenOrder].sort((a, b) => (fused.get(b) ?? 0) - (fused.get(a) ?? 0));
  return order.map((chunk_id, i) => ({
    chunk_id,
    score: fused.get(chunk_id) ?? 0,
    rank: i + 1,
  }));
}
