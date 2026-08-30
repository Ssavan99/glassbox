import json

import numpy as np
import pytest

import engine.index as index_mod
from engine.config import EMBEDDING_DIM


@pytest.fixture(autouse=True)
def _clear_index_cache():
    index_mod.load_index.cache_clear()
    yield
    index_mod.load_index.cache_clear()


def test_load_index_missing_files_raises_actionable_error(tmp_path, monkeypatch):
    monkeypatch.setattr(index_mod, "CHUNKS_PATH", tmp_path / "chunks.json")
    monkeypatch.setattr(index_mod, "VECTORS_PATH", tmp_path / "vectors.f32")

    with pytest.raises(FileNotFoundError, match="python scripts/build_index.py"):
        index_mod.load_index()


def test_load_index_mismatched_vector_count_raises_clear_error(tmp_path, monkeypatch):
    chunks_path = tmp_path / "chunks.json"
    vectors_path = tmp_path / "vectors.f32"
    monkeypatch.setattr(index_mod, "CHUNKS_PATH", chunks_path)
    monkeypatch.setattr(index_mod, "VECTORS_PATH", vectors_path)

    chunks = [
        {"chunk_id": "note::0", "note_id": "note", "text": "a", "heading": None},
        {"chunk_id": "note::1", "note_id": "note", "text": "b", "heading": None},
    ]
    chunks_path.write_text(json.dumps(chunks))
    # Only one row of vectors for two chunks -- a stale/desynced artifact pair.
    vectors_path.write_bytes(np.zeros((1, EMBEDDING_DIM), dtype=np.float32).tobytes())

    with pytest.raises(ValueError, match="out of sync"):
        index_mod.load_index()


def test_load_index_succeeds_with_consistent_artifacts(tmp_path, monkeypatch):
    chunks_path = tmp_path / "chunks.json"
    vectors_path = tmp_path / "vectors.f32"
    monkeypatch.setattr(index_mod, "CHUNKS_PATH", chunks_path)
    monkeypatch.setattr(index_mod, "VECTORS_PATH", vectors_path)

    chunks = [{"chunk_id": "note::0", "note_id": "note", "text": "a", "heading": None}]
    chunks_path.write_text(json.dumps(chunks))
    vectors_path.write_bytes(np.zeros((1, EMBEDDING_DIM), dtype=np.float32).tobytes())

    idx = index_mod.load_index()
    assert len(idx.chunks) == 1
