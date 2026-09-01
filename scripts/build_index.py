"""Build the retrieval index artifacts (chunks, vectors, bm25) from the corpus.

Loads corpus/notes -> chunks the notes -> embeds every chunk -> writes:
  - artifacts/chunks.json  (build id + chunk_id, note_id, text, heading per chunk)
  - artifacts/vectors.f32  (build-id header + raw float32, row-major)
  - artifacts/bm25.json    (tokenized corpus + doc frequencies, enough to
                             rebuild a SparseStore without recomputing from
                             raw text)
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

# Ensure the repo root is importable when this script is invoked directly
# (e.g. `python scripts/build_index.py`) regardless of how the environment's
# editable install resolves sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.artifacts import retrieval_build_id, vector_artifact_bytes
from engine.chunking import chunk_notes
from engine.config import ARTIFACTS_DIR, BM25_PATH, CHUNKS_PATH, CORPUS_DIR, VECTORS_PATH
from engine.corpus import load_corpus
from engine.embedding import embed_texts
from engine.store import tokenize


def _bm25_payload(chunk_ids: list[str], texts: list[str]) -> dict:
    tokenized = [tokenize(t) for t in texts]
    doc_freqs: Counter[str] = Counter()
    for tokens in tokenized:
        doc_freqs.update(set(tokens))

    return {
        "chunk_ids": chunk_ids,
        "tokenized_texts": tokenized,
        "doc_freqs": dict(doc_freqs),
        "n_docs": len(tokenized),
    }


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write via a temp file + os.replace() so a crash mid-write can never
    leave `path` truncated/partial -- the rename is the only visible state
    change, and it's atomic on the same filesystem."""
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_bytes(data)
    os.replace(tmp_path, path)


def _atomic_write_text(path: Path, text: str) -> None:
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(tmp_path, path)


def _write_temp_bytes(path: Path, data: bytes) -> Path:
    """Stage an artifact without making the new generation visible yet."""
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_bytes(data)
    return tmp_path


def _write_temp_text(path: Path, text: str) -> Path:
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    return tmp_path


def _commit_staged_artifacts(staged: list[tuple[Path, Path]]) -> None:
    """Publish a fully staged bundle with no work between successive renames.

    Filesystems cannot atomically rename three paths as one transaction. The
    shared build id lets readers reject the short-lived mixed generation if a
    process is interrupted during this immediate sequence.
    """
    for tmp_path, target_path in staged:
        os.replace(tmp_path, target_path)


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    notes = load_corpus(CORPUS_DIR)
    chunks = chunk_notes(notes)
    build_id = retrieval_build_id(CORPUS_DIR)

    texts = [c.text for c in chunks]
    chunk_ids = [c.chunk_id for c in chunks]

    chunks_payload = {
        "build_id": build_id,
        "chunks": [
            {
                "chunk_id": c.chunk_id,
                "note_id": c.note_id,
                "text": c.text,
                "heading": c.heading,
            }
            for c in chunks
        ],
    }

    vectors = embed_texts(texts) if texts else None
    raw_vector_bytes = vectors.tobytes() if vectors is not None else b""
    vector_bytes_data = vector_artifact_bytes(build_id, raw_vector_bytes)
    vector_bytes = vectors.nbytes if vectors is not None else 0

    bm25_payload = _bm25_payload(chunk_ids, texts)
    bm25_payload["build_id"] = build_id

    # Stage every file before exposing any of this build. A crash during the
    # final renames can still leave an old/new mix, so each artifact carries
    # the same build id and runtime loaders reject divergent generations.
    staged = [
        (_write_temp_text(CHUNKS_PATH, json.dumps(chunks_payload)), CHUNKS_PATH),
        (_write_temp_bytes(VECTORS_PATH, vector_bytes_data), VECTORS_PATH),
        (_write_temp_text(BM25_PATH, json.dumps(bm25_payload)), BM25_PATH),
    ]
    _commit_staged_artifacts(staged)

    print(f"notes: {len(notes)}")
    print(f"chunks: {len(chunks)}")
    print(f"build id: {build_id}")
    print(f"vector bytes: {vector_bytes}")
    print(f"wrote: {CHUNKS_PATH}")
    print(f"wrote: {VECTORS_PATH}")
    print(f"wrote: {BM25_PATH}")


if __name__ == "__main__":
    main()
