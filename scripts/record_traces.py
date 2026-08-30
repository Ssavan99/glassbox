"""Run all 7 architectures over every question in evaluation/questions.yaml
and write each resulting Trace to artifacts/traces/{architecture}__{question_id}.json.

Same sweep as evaluation/run_eval.py (imports its architecture registry and
per-(architecture, question) runner directly rather than duplicating them),
just persisting the raw traces instead of computing metrics from them --
these are what Phase 8's frontend TracePlayer reads. Real LLM calls this
script makes are cached by engine/llm.py, so running this before or after
evaluation/run_eval.py mostly reuses the same cache rather than doubling the
real call volume.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.config import TRACES_DIR
from evaluation.run_eval import ARCHITECTURES, load_questions, run_one


def main() -> None:
    TRACES_DIR.mkdir(parents=True, exist_ok=True)
    questions = load_questions()

    total = len(ARCHITECTURES) * len(questions)
    done = 0
    for arch_name in ARCHITECTURES:
        for question in questions:
            trace, _backend_calls = run_one(arch_name, question)
            trace.validate()

            out_path = TRACES_DIR / f"{arch_name}__{question['id']}.json"
            out_path.write_text(json.dumps(trace.to_dict(), indent=2))

            done += 1
            print(f"[{done}/{total}] wrote {out_path.name}", flush=True)

    print(f"\nwrote {done} traces to {TRACES_DIR}")


if __name__ == "__main__":
    main()
