"""Thin wrapper around sentence-transformers' CrossEncoder for reranking.

Mirrors the lazy-singleton pattern in engine/embedding.py's _get_model():
the model is loaded once, on first use, and cached for the process lifetime.
"""

from __future__ import annotations

from sentence_transformers import CrossEncoder

from engine.config import RERANK_MODEL

_model: CrossEncoder | None = None


def _get_model() -> CrossEncoder:
    global _model
    if _model is None:
        _model = CrossEncoder(RERANK_MODEL)
    return _model


def rerank_scores(query: str, texts: list[str]) -> list[float]:
    """Score each (query, text) pair with the cross-encoder. Higher is more
    relevant. Returns scores in the same order as `texts`."""
    if not texts:
        return []
    model = _get_model()
    pairs = [(query, text) for text in texts]
    scores = model.predict(pairs)
    return [float(s) for s in scores]
