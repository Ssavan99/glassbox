import hljsCore from "highlight.js/lib/core";
import python from "highlight.js/lib/languages/python";

// Core build + one registered language, not the full highlight.js bundle --
// every code excerpt this site ever shows is Python (engine/architectures/
// *.py), so there's no reason to ship grammars for languages nothing here
// uses.
hljsCore.registerLanguage("python", python);

/** Returns syntax-highlighted HTML (safe to render via dangerouslySetInnerHTML
 * -- highlight.js escapes the input's own HTML-significant characters before
 * wrapping tokens in spans) for a snippet of real Python source. Token colors
 * are mapped to this project's own design tokens in index.css, not a
 * pre-packaged theme, so the code block stays visually consistent with the
 * rest of the site in both themes. */
export function highlightPython(code: string): string {
  return hljsCore.highlight(code, { language: "python" }).value;
}
