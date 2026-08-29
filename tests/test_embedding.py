import numpy as np
import pytest

from engine.config import EMBEDDING_DIM
from engine.embedding import embed_texts


def test_embedding_shape_and_normalization():
    texts = ["Chunking splits documents into pieces.", "The sky is blue today."]
    vectors = embed_texts(texts)

    assert vectors.shape == (2, EMBEDDING_DIM)
    assert vectors.dtype == np.float32

    norms = np.linalg.norm(vectors, axis=1)
    np.testing.assert_allclose(norms, 1.0, atol=1e-4)


def test_similar_text_scores_higher_than_dissimilar_text():
    vectors = embed_texts(
        [
            "Retrieval-augmented generation combines search and generation.",
            "Retrieval-augmented generation combines search and generation.",
            "Bananas are a good source of potassium.",
        ]
    )
    self_similarity = float(np.dot(vectors[0], vectors[1]))
    cross_similarity = float(np.dot(vectors[0], vectors[2]))

    assert self_similarity > cross_similarity
    assert self_similarity == pytest.approx(1.0, abs=1e-3)
