"""Thin wrapper around sentence-transformers for embedding chunk/query text."""

from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from engine.config import EMBEDDING_MODEL

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed a batch of texts, returning an (n, EMBEDDING_DIM) float32 array
    of L2-normalized vectors (dot product == cosine similarity)."""
    model = _get_model()
    vectors = model.encode(
        texts,
        batch_size=32,
        convert_to_numpy=True,
        show_progress_bar=False,
    ).astype(np.float32)

    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    vectors = vectors / norms

    return vectors
