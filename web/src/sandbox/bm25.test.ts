import { describe, expect, it } from "vitest";
import { type Bm25Artifact, buildBm25Index, tokenize } from "./bm25";

/**
 * A five-document toy corpus in exactly the artifact's shape. The expected
 * scores below were produced by running the real Python `rank_bm25.BM25Okapi`
 * over this same corpus, so they're ground truth for the port -- any drift
 * means the TS implementation stopped matching the pipeline.
 */
const FIXTURE: Bm25Artifact = {
  build_id: "a".repeat(64),
  chunk_ids: ["doc0", "doc1", "doc2", "doc3", "doc4"],
  tokenized_texts: [
    ["the", "quick", "brown", "fox", "jumps", "over", "the", "lazy", "dog"],
    ["a", "fast", "brown", "fox", "runs", "through", "the", "dark", "forest"],
    ["the", "lazy", "dog", "sleeps", "all", "day", "long", "in", "the", "sun"],
    ["quick", "foxes", "and", "lazy", "dogs", "rarely", "meet", "at", "night"],
    ["machine", "learning", "models", "process", "large", "amounts", "of", "text", "data"],
  ],
  doc_freqs: {
    fox: 2,
    dog: 2,
    brown: 2,
    over: 1,
    quick: 2,
    the: 3,
    lazy: 3,
    jumps: 1,
    runs: 1,
    a: 1,
    forest: 1,
    fast: 1,
    through: 1,
    dark: 1,
    long: 1,
    sun: 1,
    in: 1,
    all: 1,
    sleeps: 1,
    day: 1,
    at: 1,
    foxes: 1,
    meet: 1,
    rarely: 1,
    night: 1,
    and: 1,
    dogs: 1,
    data: 1,
    text: 1,
    of: 1,
    large: 1,
    learning: 1,
    machine: 1,
    models: 1,
    process: 1,
    amounts: 1,
  },
  n_docs: 5,
};

/** Ground-truth per-document scores for "quick fox", in doc0..doc4 order. */
const GOLDEN_SCORES = [
  0.6795926623304411, 0.33979633116522057, 0.0, 0.33979633116522057, 0.0,
];

/** Re-reads scores in original document order from a full-corpus search. */
function scoresInDocOrder(results: { chunk_id: string; score: number }[]): number[] {
  const byId = new Map(results.map((r) => [r.chunk_id, r.score]));
  return FIXTURE.chunk_ids.map((id) => byId.get(id) as number);
}

describe("buildBm25Index", () => {
  it("reproduces rank_bm25's exact scores for 'quick fox'", () => {
    const index = buildBm25Index(FIXTURE);
    const results = index.search("quick fox", 5);
    const scores = scoresInDocOrder(results);
    for (let i = 0; i < GOLDEN_SCORES.length; i += 1) {
      expect(scores[i]).toBeCloseTo(GOLDEN_SCORES[i], 10);
    }
  });

  it("ranks by score descending, breaking ties by original document order", () => {
    const index = buildBm25Index(FIXTURE);
    const results = index.search("quick fox", 5);
    expect(results.map((r) => r.chunk_id)).toEqual(["doc0", "doc1", "doc3", "doc2", "doc4"]);
    expect(results.map((r) => r.rank)).toEqual([1, 2, 3, 4, 5]);
  });

  it("truncates to top-k", () => {
    const index = buildBm25Index(FIXTURE);
    const results = index.search("quick fox", 2);
    expect(results.map((r) => r.chunk_id)).toEqual(["doc0", "doc1"]);
    expect(results.map((r) => r.rank)).toEqual([1, 2]);
  });

  it("lowercases the query before scoring", () => {
    const index = buildBm25Index(FIXTURE);
    expect(index.search("QUICK Fox", 5)).toEqual(index.search("quick fox", 5));
  });

  it("returns every doc at score 0 in original order for an empty query", () => {
    const index = buildBm25Index(FIXTURE);
    const results = index.search("   ", 5);
    expect(results.map((r) => r.chunk_id)).toEqual(FIXTURE.chunk_ids);
    expect(results.map((r) => r.score)).toEqual([0, 0, 0, 0, 0]);
    expect(results.map((r) => r.rank)).toEqual([1, 2, 3, 4, 5]);
  });

  it("returns every doc at score 0 when the query matches nothing", () => {
    const index = buildBm25Index(FIXTURE);
    // In-vocabulary terms would score; these are absent from every document.
    const results = index.search("zebra helicopter", 5);
    expect(results.map((r) => r.chunk_id)).toEqual(FIXTURE.chunk_ids);
    expect(results.map((r) => r.score)).toEqual([0, 0, 0, 0, 0]);
  });

  it("ignores out-of-vocabulary terms rather than throwing", () => {
    const index = buildBm25Index(FIXTURE);
    const withOov = index.search("quick zebra fox", 5);
    expect(scoresInDocOrder(withOov)).toEqual(
      scoresInDocOrder(index.search("quick fox", 5)),
    );
  });
});

describe("tokenize", () => {
  it("matches Python's text.lower().split()", () => {
    expect(tokenize("  Quick\tBROWN\n  fox  ")).toEqual(["quick", "brown", "fox"]);
    expect(tokenize("")).toEqual([]);
    expect(tokenize("   ")).toEqual([]);
  });
});
