import json

import numpy as np
import pytest

import engine.index as index_mod
from engine.artifacts import vector_artifact_bytes
from engine.config import EMBEDDING_DIM


@pytest.fixture(autouse=True)
def _clear_index_cache():
    index_mod.load_index.cache_clear()
    yield
    index_mod.load_index.cache_clear()


def test_load_index_missing_files_raises_actionable_error(tmp_path, monkeypatch):
    monkeypatch.setattr(index_mod, "CHUNKS_PATH", tmp_path / "chunks.json")
    monkeypatch.setattr(index_mod, "VECTORS_PATH", tmp_path / "vectors.f32")
    monkeypatch.setattr(index_mod, "BM25_PATH", tmp_path / "bm25.json")

    with pytest.raises(FileNotFoundError, match="python scripts/build_index.py"):
        index_mod.load_index()


def test_load_index_mismatched_vector_count_raises_clear_error(tmp_path, monkeypatch):
    chunks_path = tmp_path / "chunks.json"
    vectors_path = tmp_path / "vectors.f32"
    bm25_path = tmp_path / "bm25.json"
    monkeypatch.setattr(index_mod, "CHUNKS_PATH", chunks_path)
    monkeypatch.setattr(index_mod, "VECTORS_PATH", vectors_path)
    monkeypatch.setattr(index_mod, "BM25_PATH", bm25_path)

    chunks = [
        {"chunk_id": "note::0", "note_id": "note", "text": "a", "heading": None},
        {"chunk_id": "note::1", "note_id": "note", "text": "b", "heading": None},
    ]
    build_id = "a" * 64
    chunks_path.write_text(json.dumps({"build_id": build_id, "chunks": chunks}))
    # Only one row of vectors for two chunks -- a stale/desynced artifact pair.
    vectors_path.write_bytes(
        vector_artifact_bytes(build_id, np.zeros((1, EMBEDDING_DIM), dtype=np.float32).tobytes())
    )
    bm25_path.write_text(json.dumps({"build_id": build_id}))

    with pytest.raises(ValueError, match="out of sync"):
        index_mod.load_index()


def test_load_index_succeeds_with_consistent_artifacts(tmp_path, monkeypatch):
    chunks_path = tmp_path / "chunks.json"
    vectors_path = tmp_path / "vectors.f32"
    bm25_path = tmp_path / "bm25.json"
    monkeypatch.setattr(index_mod, "CHUNKS_PATH", chunks_path)
    monkeypatch.setattr(index_mod, "VECTORS_PATH", vectors_path)
    monkeypatch.setattr(index_mod, "BM25_PATH", bm25_path)

    chunks = [{"chunk_id": "note::0", "note_id": "note", "text": "a", "heading": None}]
    build_id = "a" * 64
    chunks_path.write_text(json.dumps({"build_id": build_id, "chunks": chunks}))
    vectors_path.write_bytes(
        vector_artifact_bytes(build_id, np.zeros((1, EMBEDDING_DIM), dtype=np.float32).tobytes())
    )
    bm25_path.write_text(json.dumps({"build_id": build_id}))

    idx = index_mod.load_index()
    assert len(idx.chunks) == 1


def test_load_index_rejects_partial_artifact_write_even_when_counts_match(tmp_path, monkeypatch):
    chunks_path = tmp_path / "chunks.json"
    vectors_path = tmp_path / "vectors.f32"
    bm25_path = tmp_path / "bm25.json"
    monkeypatch.setattr(index_mod, "CHUNKS_PATH", chunks_path)
    monkeypatch.setattr(index_mod, "VECTORS_PATH", vectors_path)
    monkeypatch.setattr(index_mod, "BM25_PATH", bm25_path)

    chunks = [{"chunk_id": "note::0", "note_id": "note", "text": "a", "heading": None}]
    # Simulate an interruption after chunks/vectors were published but before
    # bm25.json was replaced. Counts still agree, so only the build id can
    # detect the mixed generation.
    new_build_id = "a" * 64
    stale_build_id = "b" * 64
    chunks_path.write_text(json.dumps({"build_id": new_build_id, "chunks": chunks}))
    vectors_path.write_bytes(
        vector_artifact_bytes(new_build_id, np.zeros((1, EMBEDDING_DIM), dtype=np.float32).tobytes())
    )
    bm25_path.write_text(json.dumps({"build_id": stale_build_id}))

    with pytest.raises(ValueError, match="Retrieval artifacts are out of sync"):
        index_mod.load_index()
