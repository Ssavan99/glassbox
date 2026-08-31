import { describe, expect, it } from "vitest";
import { reciprocalRankFusion } from "./fuse";

describe("reciprocalRankFusion", () => {
  it("matches the real hybrid.py formula on a hand-computed example", () => {
    const dense = [
      { chunk_id: "a", score: 0.9, rank: 1 },
      { chunk_id: "b", score: 0.8, rank: 2 },
    ];
    const sparse = [
      { chunk_id: "b", score: 5, rank: 1 },
      { chunk_id: "c", score: 3, rank: 2 },
    ];
    const result = reciprocalRankFusion([dense, sparse], 60);

    // b: appears rank 2 in dense (1/62) + rank 1 in sparse (1/61)
    const bScore = 1 / 62 + 1 / 61;
    // a: only in dense, rank 1 -> 1/61
    const aScore = 1 / 61;
    // c: only in sparse, rank 2 -> 1/62
    const cScore = 1 / 62;

    expect(result.find((r) => r.chunk_id === "b")!.score).toBeCloseTo(bScore, 10);
    expect(result.find((r) => r.chunk_id === "a")!.score).toBeCloseTo(aScore, 10);
    expect(result.find((r) => r.chunk_id === "c")!.score).toBeCloseTo(cScore, 10);
    // b has the highest combined score -> rank 1
    expect(result[0].chunk_id).toBe("b");
    expect(result[0].rank).toBe(1);
  });

  it("a chunk present in only one list still gets a nonzero score", () => {
    const result = reciprocalRankFusion([[{ chunk_id: "solo", score: 1, rank: 1 }], []]);
    expect(result).toHaveLength(1);
    expect(result[0].score).toBeGreaterThan(0);
  });

  it("breaks score ties by first-seen order (dense list before sparse, matching Python's stable sort over insertion order)", () => {
    // Both end up with an identical fused score: rank 1 in one list only.
    const dense = [{ chunk_id: "x", score: 1, rank: 1 }];
    const sparse = [{ chunk_id: "y", score: 1, rank: 1 }];
    const result = reciprocalRankFusion([dense, sparse]);
    expect(result[0].chunk_id).toBe("x");
    expect(result[1].chunk_id).toBe("y");
  });

  it("assigns 1-indexed ranks in fused order", () => {
    const result = reciprocalRankFusion([
      [
        { chunk_id: "a", score: 1, rank: 1 },
        { chunk_id: "b", score: 1, rank: 2 },
      ],
    ]);
    expect(result.map((r) => r.rank)).toEqual([1, 2]);
  });

  it("handles no input lists", () => {
    expect(reciprocalRankFusion([])).toEqual([]);
  });
});
