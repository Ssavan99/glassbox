"""Dense (vector) and sparse (BM25) chunk stores."""

from __future__ import annotations

import numpy as np
from rank_bm25 import BM25Okapi


def tokenize(text: str) -> list[str]:
    return text.lower().split()


class DenseStore:
    """Holds an (n, dim) float32 matrix of normalized vectors + chunk ids.
    Search is a dot product against the query vector (== cosine similarity
    since vectors are L2-normalized)."""

    def __init__(self, chunk_ids: list[str], vectors: np.ndarray):
        if len(chunk_ids) != vectors.shape[0]:
            raise ValueError("chunk_ids length must match vectors row count")
        self.chunk_ids = list(chunk_ids)
        self.vectors = np.asarray(vectors, dtype=np.float32)

    def search(self, query_vector: np.ndarray, k: int) -> list[tuple[str, float]]:
        query_vector = np.asarray(query_vector, dtype=np.float32)
        scores = self.vectors @ query_vector
        k = min(k, len(self.chunk_ids))
        if k <= 0:
            return []
        top_idx = np.argpartition(-scores, k - 1)[:k]
        top_idx = top_idx[np.argsort(-scores[top_idx])]
        return [(self.chunk_ids[i], float(scores[i])) for i in top_idx]


class SparseStore:
    """Wraps rank_bm25.BM25Okapi over whitespace-tokenized, lowercased
    chunk texts."""

    def __init__(self, chunk_ids: list[str], texts: list[str]):
        if len(chunk_ids) != len(texts):
            raise ValueError("chunk_ids length must match texts length")
        self.chunk_ids = list(chunk_ids)
        self.tokenized_texts = [tokenize(t) for t in texts]
        self.bm25 = BM25Okapi(self.tokenized_texts)

    def search(self, query_text: str, k: int) -> list[tuple[str, float]]:
        query_tokens = tokenize(query_text)
        scores = self.bm25.get_scores(query_tokens)
        k = min(k, len(self.chunk_ids))
        if k <= 0:
            return []
        top_idx = np.argpartition(-scores, k - 1)[:k]
        top_idx = top_idx[np.argsort(-scores[top_idx])]
        return [(self.chunk_ids[i], float(scores[i])) for i in top_idx]
