import numpy as np
import pytest

from engine.store import DenseStore, SparseStore


def _normalize(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v)


def test_dense_store_returns_exact_chunk_as_top1():
    rng = np.random.default_rng(42)
    chunk_ids = ["a::0", "a::1", "a::2", "a::3"]
    vectors = np.array(
        [_normalize(rng.normal(size=8)) for _ in chunk_ids], dtype=np.float32
    )
    store = DenseStore(chunk_ids, vectors)

    query = vectors[2]
    results = store.search(query, k=3)

    assert results[0][0] == "a::2"
    assert results[0][1] == pytest.approx(1.0, abs=1e-4)


def test_sparse_store_ranks_keyword_match_above_no_match():
    chunk_ids = ["a::0", "a::1", "a::2"]
    texts = [
        "This chunk talks about zebras and giraffes at the savanna.",
        "This chunk is about cooking pasta and making sauce.",
        "This chunk discusses gardening and growing tomatoes.",
    ]
    store = SparseStore(chunk_ids, texts)

    results = store.search("zebras savanna", k=3)

    assert results[0][0] == "a::0"
    scores = dict(results)
    assert scores["a::0"] > scores["a::1"]
    assert scores["a::0"] > scores["a::2"]
