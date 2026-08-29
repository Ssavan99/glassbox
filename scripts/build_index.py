"""Build the retrieval index artifacts (chunks, vectors, bm25) from the corpus.

Loads corpus/notes -> chunks the notes -> embeds every chunk -> writes:
  - artifacts/chunks.json  (chunk_id, note_id, text, heading per chunk)
  - artifacts/vectors.f32  (raw float32, row-major, same order as chunks.json)
  - artifacts/bm25.json    (tokenized corpus + doc frequencies, enough to
                             rebuild a SparseStore without recomputing from
                             raw text)
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

# Ensure the repo root is importable when this script is invoked directly
# (e.g. `python scripts/build_index.py`) regardless of how the environment's
# editable install resolves sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.chunking import chunk_notes
from engine.config import ARTIFACTS_DIR, BM25_PATH, CHUNKS_PATH, CORPUS_DIR, VECTORS_PATH
from engine.corpus import load_corpus
from engine.embedding import embed_texts
from engine.store import tokenize


def _write_bm25_artifact(chunk_ids: list[str], texts: list[str], path) -> None:
    tokenized = [tokenize(t) for t in texts]
    doc_freqs: Counter[str] = Counter()
    for tokens in tokenized:
        doc_freqs.update(set(tokens))

    payload = {
        "chunk_ids": chunk_ids,
        "tokenized_texts": tokenized,
        "doc_freqs": dict(doc_freqs),
        "n_docs": len(tokenized),
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    notes = load_corpus(CORPUS_DIR)
    chunks = chunk_notes(notes)

    texts = [c.text for c in chunks]
    chunk_ids = [c.chunk_id for c in chunks]

    chunks_payload = [
        {
            "chunk_id": c.chunk_id,
            "note_id": c.note_id,
            "text": c.text,
            "heading": c.heading,
        }
        for c in chunks
    ]
    CHUNKS_PATH.write_text(json.dumps(chunks_payload), encoding="utf-8")

    vectors = embed_texts(texts) if texts else None
    if vectors is not None:
        VECTORS_PATH.write_bytes(vectors.tobytes())
        vector_bytes = vectors.nbytes
    else:
        VECTORS_PATH.write_bytes(b"")
        vector_bytes = 0

    _write_bm25_artifact(chunk_ids, texts, BM25_PATH)

    print(f"notes: {len(notes)}")
    print(f"chunks: {len(chunks)}")
    print(f"vector bytes: {vector_bytes}")
    print(f"wrote: {CHUNKS_PATH}")
    print(f"wrote: {VECTORS_PATH}")
    print(f"wrote: {BM25_PATH}")


if __name__ == "__main__":
    main()
