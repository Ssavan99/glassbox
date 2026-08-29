"""Runtime loader for the artifacts scripts/build_index.py produces.

Architectures share one loaded index (chunk metadata + dense/sparse stores)
rather than each parsing artifacts/chunks.json and vectors.f32 themselves.
BM25 is rebuilt from chunk text at load time rather than read back from
bm25.json, since nothing has fixed that artifact's schema as a contract yet
(see scripts/build_index.py) — rebuilding is cheap and avoids depending on it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from engine.config import CHUNKS_PATH, EMBEDDING_DIM, VECTORS_PATH
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
    records = json.loads(CHUNKS_PATH.read_text())
    chunks = [ChunkRecord(**r) for r in records]
    chunk_ids = [c.chunk_id for c in chunks]

    vectors = np.fromfile(VECTORS_PATH, dtype=np.float32).reshape(len(chunks), EMBEDDING_DIM)
    dense = DenseStore(chunk_ids, vectors)
    sparse = SparseStore(chunk_ids, [c.text for c in chunks])
    chunk_by_id = {c.chunk_id: c for c in chunks}

    return Index(chunks=chunks, chunk_by_id=chunk_by_id, dense=dense, sparse=sparse)
