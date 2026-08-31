"""Runtime loader for the artifacts scripts/build_index.py produces.

Architectures share one loaded index (chunk metadata + dense/sparse stores)
rather than each parsing artifacts/chunks.json and vectors.f32 themselves.
BM25 is rebuilt from chunk text at load time, but its build id is still
checked so all three retrieval artifacts are from the same generation.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from engine.artifacts import (
    ArtifactIntegrityError,
    read_bm25_build_id,
    read_chunks_artifact,
    read_vector_artifact,
)
from engine.config import BM25_PATH, CHUNKS_PATH, EMBEDDING_DIM, VECTORS_PATH
from engine.store import DenseStore, SparseStore


@dataclass
class ChunkRecord:
    chunk_id: str
    note_id: str
    text: str
    heading: str | None


@dataclass
class Index:
    chunks: list[ChunkRecord]
    chunk_by_id: dict[str, ChunkRecord]
    dense: DenseStore
    sparse: SparseStore


@lru_cache(maxsize=1)
def load_index() -> Index:
    if not CHUNKS_PATH.exists() or not VECTORS_PATH.exists() or not BM25_PATH.exists():
        raise FileNotFoundError(
            f"Retrieval index not built: {CHUNKS_PATH}, {VECTORS_PATH}, and/or {BM25_PATH} don't exist. "
            "Run this first: python scripts/build_index.py"
        )

    chunks_build_id, records = read_chunks_artifact(CHUNKS_PATH)
    vectors_build_id, vector_bytes = read_vector_artifact(VECTORS_PATH)
    bm25_build_id = read_bm25_build_id(BM25_PATH)
    if len({chunks_build_id, vectors_build_id, bm25_build_id}) != 1:
        raise ArtifactIntegrityError(
            "Retrieval artifacts are out of sync: chunks.json, vectors.f32, and bm25.json "
            "have different build ids. Rebuild all three together: python scripts/build_index.py"
        )

    chunks = [ChunkRecord(**r) for r in records]
    chunk_ids = [c.chunk_id for c in chunks]

    raw_vectors = np.frombuffer(vector_bytes, dtype=np.float32)
    expected_size = len(chunks) * EMBEDDING_DIM
    if raw_vectors.size != expected_size:
        raise ValueError(
            f"{VECTORS_PATH} has {raw_vectors.size} float32 values, expected "
            f"{expected_size} ({len(chunks)} chunks x {EMBEDDING_DIM} dims) to match "
            f"{CHUNKS_PATH}. The two artifacts are out of sync -- rebuild both together: "
            "python scripts/build_index.py"
        )
    vectors = raw_vectors.reshape(len(chunks), EMBEDDING_DIM)
    dense = DenseStore(chunk_ids, vectors)
    sparse = SparseStore(chunk_ids, [c.text for c in chunks])
    chunk_by_id = {c.chunk_id: c for c in chunks}

    return Index(chunks=chunks, chunk_by_id=chunk_by_id, dense=dense, sparse=sparse)
