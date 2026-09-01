/** Matches a `[chunk-id::n]`-style citation, tolerating real-world noise
 * confirmed present in the actual shipped corpus (found by grepping every
 * real `artifacts/traces/*.json` answer field during Phase 8's Code Review):
 * a `citation: ` prefix, extra interior whitespace, a zero-width space
 * (U+200B) right after `[`, and a Unicode hyphen variant (U+2010/U+2011) in
 * place of ASCII `-`. The strict original pattern silently rendered these
 * as unstyled plain text instead of a highlighted citation. Written with
 * explicit \u escapes (not literal invisible/lookalike characters) so the
 * pattern stays legible in a diff and can't be silently corrupted by an
 * editor or copy-paste. */
const ZWSP = "\u200B";
const HYPHEN_VARIANTS = "\u2010\u2011"; // HYPHEN, NON-BREAKING HYPHEN
const CITATION_RE = new RegExp(
  `\\[\\s*(?:citation:\\s*)?${ZWSP}?([a-z0-9][a-z0-9${HYPHEN_VARIANTS}-]*::\\d+)${ZWSP}?\\s*\\]`,
  "gi",
);

export interface AnswerPart {
  text: string;
  /** The normalized chunk_id (Unicode hyphen variants folded to ASCII `-`)
   * if this part is a citation, else null for plain prose. */
  citation: string | null;
}

/** Splits answer text into alternating prose/citation parts. Citation parts
 * are re-rendered as a clean `[chunk-id::n]` rather than echoing whatever
 * noisy original text matched (e.g. `[citation: real-id]` becomes
 * `[real-id]`), since the point is to help a reader spot real grounding,
 * not to preserve incidental LLM formatting quirks. */
export function splitAnswerCitations(text: string): AnswerPart[] {
  const parts: AnswerPart[] = [];
  let lastIndex = 0;
  for (const match of text.matchAll(CITATION_RE)) {
    const start = match.index ?? 0;
    if (start > lastIndex) {
      parts.push({ text: text.slice(lastIndex, start), citation: null });
    }
    const normalizedId = match[1].replace(new RegExp(`[${HYPHEN_VARIANTS}]`, "g"), "-");
    parts.push({ text: `[${normalizedId}]`, citation: normalizedId });
    lastIndex = start + match[0].length;
  }
  if (lastIndex < text.length) {
    parts.push({ text: text.slice(lastIndex), citation: null });
  }
  return parts;
}
