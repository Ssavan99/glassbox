import { describe, expect, it } from "vitest";
import { splitAnswerCitations } from "./citations";

describe("splitAnswerCitations", () => {
  it("highlights a normal, well-formed citation", () => {
    const parts = splitAnswerCitations("LoRA freezes the base model [lora-basics::0].");
    const citations = parts.filter((p) => p.citation);
    expect(citations).toHaveLength(1);
    expect(citations[0].citation).toBe("lora-basics::0");
    expect(citations[0].text).toBe("[lora-basics::0]");
  });

  it("handles multiple citations and plain prose with no citations at all", () => {
    const withTwo = splitAnswerCitations("See [a::0] and also [b::1] for more.");
    expect(withTwo.filter((p) => p.citation).map((p) => p.citation)).toEqual(["a::0", "b::1"]);

    const withNone = splitAnswerCitations("No citations in this answer at all.");
    expect(withNone.filter((p) => p.citation)).toHaveLength(0);
    expect(withNone).toEqual([{ text: "No citations in this answer at all.", citation: null }]);
  });

  // Every case below is a real, confirmed pattern found by grepping actual
  // recorded answers in artifacts/traces/*.json during Phase 8's Code
  // Review -- the original strict regex silently rendered each as unstyled
  // plain text instead of a highlighted citation.
  describe("real corpus noise (Phase 8 Code Review findings)", () => {
    it("tolerates a zero-width space (U+200B) right after the opening bracket", () => {
      // real case: naive__q01.json
      const parts = splitAnswerCitations(
        "matrix [​lora-and-parameter-efficient-fine-tuning::0].",
      );
      const citations = parts.filter((p) => p.citation);
      expect(citations).toHaveLength(1);
      expect(citations[0].citation).toBe("lora-and-parameter-efficient-fine-tuning::0");
    });

    it("tolerates extra interior whitespace inside the brackets", () => {
      // real case: naive__q09.json / hybrid__q09.json
      const parts = splitAnswerCitations(
        "alone [ few-shot-prompting-for-grounded-answers::0 ]. \n\nIn a retr",
      );
      const citations = parts.filter((p) => p.citation);
      expect(citations).toHaveLength(1);
      expect(citations[0].citation).toBe("few-shot-prompting-for-grounded-answers::0");
    });

    it("tolerates and strips a 'citation: ' prefix inside the brackets", () => {
      // real case: corrective__q15.json / naive__q15.json
      const parts = splitAnswerCitations(
        "ed.\n\n[citation: continuous-batching-and-throughput::1]",
      );
      const citations = parts.filter((p) => p.citation);
      expect(citations).toHaveLength(1);
      expect(citations[0].citation).toBe("continuous-batching-and-throughput::1");
      // normalized display strips the "citation: " noise
      expect(citations[0].text).toBe("[continuous-batching-and-throughput::1]");
    });

    it("normalizes a Unicode hyphen variant (U+2010/U+2011) inside a real citation to ASCII", () => {
      const parts = splitAnswerCitations("See [reciprocal‑rank‑fusion::1] for detail.");
      const citations = parts.filter((p) => p.citation);
      expect(citations).toHaveLength(1);
      expect(citations[0].citation).toBe("reciprocal-rank-fusion::1");
    });

    it("does NOT treat a Unicode-hyphenated term in plain prose (not inside brackets) as a citation", () => {
      // real case: corrective__q13.json / hybrid__q13.json -- the corpus
      // uses U+2011 in running prose for an unrelated reason (typographic
      // non-breaking hyphens in bolded terms), not as a malformed citation.
      // This must stay unhighlighted, not a false positive.
      const parts = splitAnswerCitations(
        "uses the **reciprocal‑rank‑fusion constant k** (often called `RRF_K`).",
      );
      expect(parts.filter((p) => p.citation)).toHaveLength(0);
    });
  });
});
