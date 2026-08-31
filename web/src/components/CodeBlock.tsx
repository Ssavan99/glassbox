import { highlightPython } from "../lib/highlight";
import type { CodeExcerpt } from "../lib/types";

interface CodeBlockProps {
  excerpt: CodeExcerpt;
}

/** Renders a real code excerpt extracted from engine/ source at build time
 * (scripts/extract_code_excerpts.py, Phase 9) -- never hand-copied, so it
 * can never silently drift from what the architecture actually does. The
 * byline names the exact file and line range so a reader can go verify this
 * themselves in the real repo. */
export function CodeBlock({ excerpt }: CodeBlockProps) {
  const html = highlightPython(excerpt.code);
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-page px-4 py-2">
        <code className="text-xs text-ink-secondary">
          {excerpt.file}
          <span className="text-ink-muted">
            {" "}
            · lines {excerpt.start_line}–{excerpt.end_line}
          </span>
        </code>
        <span className="text-[10px] uppercase tracking-wide text-ink-muted">
          extracted from source at build time
        </span>
      </div>
      <pre className="max-h-[32rem] overflow-auto p-4 text-[13px] leading-relaxed">
        <code
          className="hljs language-python"
          // highlight.js escapes the input's own HTML-significant characters
          // before wrapping tokens in spans -- see lib/highlight.ts.
          dangerouslySetInnerHTML={{ __html: html }}
        />
      </pre>
    </div>
  );
}
