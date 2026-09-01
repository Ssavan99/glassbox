"""Extracts real, marked regions of engine/architectures/*.py into JSON so
the tutorial pages can show actual implementing code instead of a hand-copied
(and driftable) excerpt.

Each of the seven architecture files wraps its `run()` method in a
`# region: run` / `# endregion` marker pair. This script finds those markers,
extracts and dedents the code between them, and writes the result straight to
web/public/data/code_excerpts.json -- the same destination scripts/export_web.py
writes to, but never through artifacts/ and never committed, since re-running
this script is free (no LLM calls, just reading local source files) and the
whole point is that the excerpt can never go stale relative to source: delete
or rename a marker and extraction fails loudly instead of silently shipping
an empty or outdated code block.

Run after scripts/export_web.py (which clears and recreates
web/public/data/ on every run) -- this script only adds to that directory,
never clears it, so the ordering matters: export_web.py first, then this.
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.config import ROOT, WEB_DATA_DIR

REGION = "run"

# Same seven ids as web/src/lib/types.ts's ARCHITECTURE_IDS -- order here
# doesn't matter (the frontend orders them), but every one of these seven
# must extract successfully or the build fails.
ARCHITECTURE_FILES: dict[str, Path] = {
    "naive": Path("engine/architectures/naive.py"),
    "hybrid": Path("engine/architectures/hybrid.py"),
    "hyde": Path("engine/architectures/hyde.py"),
    "corrective": Path("engine/architectures/corrective.py"),
    "graph": Path("engine/architectures/graph.py"),
    "agentic": Path("engine/architectures/agentic.py"),
    "adaptive": Path("engine/architectures/adaptive.py"),
}


def extract_region(path: Path, region: str) -> tuple[str, int, int]:
    """Returns (dedented code, 1-indexed start line, 1-indexed end line) of
    the code between `# region: {region}` and the next `# endregion` in
    `path`. Raises ValueError with a clear, actionable message if either
    marker is missing -- this is the mechanism that makes a moved/renamed/
    deleted marker a loud build failure instead of a silent stale excerpt."""
    lines = path.read_text().splitlines()
    start_marker = f"# region: {region}"

    start_idx = next((i for i, line in enumerate(lines) if line.strip() == start_marker), None)
    if start_idx is None:
        raise ValueError(f"{path}: no '{start_marker}' marker found")

    end_idx = next(
        (i for i in range(start_idx + 1, len(lines)) if lines[i].strip() == "# endregion"),
        None,
    )
    if end_idx is None:
        raise ValueError(
            f"{path}: found '{start_marker}' at line {start_idx + 1} but no "
            "matching '# endregion' after it"
        )

    region_lines = lines[start_idx + 1 : end_idx]
    code = textwrap.dedent("\n".join(region_lines)).strip("\n")
    if not code:
        raise ValueError(f"{path}: region '{region}' is empty")
    return code, start_idx + 2, end_idx  # +2: start_idx is the marker line itself (1-indexed)


def extract_all(root: Path = ROOT) -> dict[str, dict]:
    excerpts: dict[str, dict] = {}
    for architecture, rel_path in ARCHITECTURE_FILES.items():
        code, start_line, end_line = extract_region(root / rel_path, REGION)
        excerpts[architecture] = {
            "architecture": architecture,
            "file": str(rel_path),
            "region": REGION,
            "start_line": start_line,
            "end_line": end_line,
            "code": code,
        }
    return excerpts


def main() -> None:
    excerpts = extract_all()
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    (WEB_DATA_DIR / "code_excerpts.json").write_text(json.dumps(excerpts, indent=2))
    print(f"extracted {len(excerpts)} code excerpt(s) to {WEB_DATA_DIR / 'code_excerpts.json'}")


if __name__ == "__main__":
    main()
