# glassbox

**See inside RAG.** Seven retrieval-augmented generation architectures,
implemented for real in Python, run over one designed corpus, with every
intermediate step recorded and (eventually) replayed in a web frontend that
teaches how they differ.

This repo is under active construction — see `repo-plans/glassbox_PLAN.md`
(not part of this repo) for the full build plan. The full portfolio-standard
README with a live demo link, screenshots, and the seven-architecture writeup
lands in a later phase.

## What's built so far

- **`corpus/`** — 60 hand-edited notes on AI/ML engineering, designed to
  differentiate seven different RAG architectures (see `corpus/README.md` for
  the design contract: recurring entities, keyword-specific terms, multi-hop
  facts, and near-miss decoys planted on purpose).
- **`evaluation/questions.yaml`** — 27 labeled evaluation questions
  (factual / multi-hop / keyword / unanswerable) with gold chunk references.
- **`engine/`** — chunking, embedding (`all-MiniLM-L6-v2`, normalized
  vectors), dense (numpy) and sparse (BM25) retrieval stores, a dual-backend
  LLM client (Groq primary, local Ollama automatic fallback so the project
  stays free forever), and the frozen trace schema (`engine/trace.py`) that
  every architecture will record its execution against.
- **`scripts/build_index.py`** — builds `artifacts/chunks.json`,
  `artifacts/vectors.f32`, and `artifacts/bm25.json` from the corpus.

The seven architectures themselves, the evaluation harness, and the frontend
are not built yet.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # then add your own GROQ_API_KEY (see below)
python scripts/build_index.py
pytest
```

### LLM backend

`engine/llm.py` tries [Groq's free API tier](https://console.groq.com) first,
and falls back automatically to a local [Ollama](https://ollama.com) model
(`qwen2.5:7b-instruct`) if `GROQ_API_KEY` is unset, invalid, rate-limited, or
unreachable. The pipeline works with **no API key at all** — it just runs
entirely on the local fallback. To use Groq, sign up for a free key at
`console.groq.com`, create an API key, and put it in `.env` as
`GROQ_API_KEY=gsk_...` (never commit this file — it's gitignored).

## License

MIT — see `LICENSE`.
