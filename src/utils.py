import numpy as np


def cosine_similarity(vector_a, vector_b):
    """
    Measures how similar two vectors are.

    Result range:
    - 1.0 means very similar
    - 0.0 means unrelated
    - -1.0 means opposite direction

    For embeddings, higher = more semantically similar.
    """
    a = np.array(vector_a)
    b = np.array(vector_b)

    denominator = np.linalg.norm(a) * np.linalg.norm(b)

    if denominator == 0:
        return 0

    return float(np.dot(a, b) / denominator)