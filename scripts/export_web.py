"""Copies artifacts/ into web/public/data/ so the frontend can fetch real,
already-recorded data (D2: the published site never calls an LLM -- every
trace, chunk, graph, and eval number it shows was recorded offline).

Copies chunks.json, eval.json, graph.json, bm25.json, vectors.f32, and the
full traces/ directory verbatim. bm25.json/vectors.f32 aren't consumed by
any route yet (Phase 10's sandbox needs them for live in-browser retrieval),
but copying the whole artifacts/ directory now means Phase 10 doesn't need
to touch this script later.

The target directory is cleared and rewritten on every run (not merged) so
a trace deleted from artifacts/ doesn't linger as stale data on the site.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.config import ARTIFACTS_DIR, ROOT

WEB_DATA_DIR = ROOT / "web" / "public" / "data"

FILES_TO_COPY = ["chunks.json", "eval.json", "graph.json", "bm25.json", "vectors.f32"]


def main() -> None:
    if not ARTIFACTS_DIR.exists():
        raise SystemExit(
            f"export_web: {ARTIFACTS_DIR} does not exist -- run scripts/build_index.py "
            "and scripts/build_graph.py first."
        )

    if WEB_DATA_DIR.exists():
        shutil.rmtree(WEB_DATA_DIR)
    WEB_DATA_DIR.mkdir(parents=True)

    copied = 0
    for name in FILES_TO_COPY:
        src = ARTIFACTS_DIR / name
        if not src.exists():
            print(f"skipping {name} (not built yet)")
            continue
        shutil.copy2(src, WEB_DATA_DIR / name)
        copied += 1

    src_traces = ARTIFACTS_DIR / "traces"
    n_traces = 0
    if src_traces.exists():
        dst_traces = WEB_DATA_DIR / "traces"
        shutil.copytree(src_traces, dst_traces)
        n_traces = sum(1 for _ in dst_traces.glob("*.json"))

    print(f"exported {copied} artifact file(s) and {n_traces} trace(s) to {WEB_DATA_DIR}")


if __name__ == "__main__":
    main()
