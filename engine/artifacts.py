"""Shared serialization helpers for the retrieval artifact bundle.

`chunks.json`, `vectors.f32`, and `bm25.json` are built as one generation.
Each carries the same content-derived build id so readers can reject a mixed
generation instead of silently pairing chunks with unrelated vectors.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from engine.config import (
    CHUNK_OVERLAP_TOKENS,
    CHUNK_TARGET_TOKENS,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
)

BUILD_ID_KEY = "build_id"
CHUNKS_KEY = "chunks"
VECTOR_BUILD_ID_PREFIX = b"GLASSBOX_BUILD_ID:"
BUILD_ID_HEX_LENGTH = 64
VECTOR_HEADER_SIZE = len(VECTOR_BUILD_ID_PREFIX) + BUILD_ID_HEX_LENGTH + 1
_BUILD_ID_RE = re.compile(r"^[0-9a-f]{64}$")


class ArtifactIntegrityError(ValueError):
    """Raised when retrieval artifacts are malformed or from different builds."""


def retrieval_build_id(corpus_dir: Path) -> str:
    """Return a stable id for corpus content and retrieval-producing inputs.

    Chunking settings and embedding configuration affect the serialized
    artifacts even when the notes do not, so they must participate in the id
    that protects a staged build from a same-count stale pairing.
    """
    digest = hashlib.sha256()
    for path in sorted(corpus_dir.rglob("*.md")):
        digest.update(path.relative_to(corpus_dir).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    for name, value in (
        ("chunk_target_tokens", CHUNK_TARGET_TOKENS),
        ("chunk_overlap_tokens", CHUNK_OVERLAP_TOKENS),
        ("embedding_model", EMBEDDING_MODEL),
        ("embedding_dim", EMBEDDING_DIM),
    ):
        digest.update(f"{name}={value}".encode())
        digest.update(b"\0")
    return digest.hexdigest()


def _require_build_id(value: object, source: Path | str) -> str:
    if not isinstance(value, str) or not _BUILD_ID_RE.fullmatch(value):
        raise ArtifactIntegrityError(
            f"{source} is missing a valid {BUILD_ID_KEY}; rebuild the retrieval artifacts "
            "with python scripts/build_index.py"
        )
    return value


def read_chunks_artifact(path: Path) -> tuple[str, list[dict]]:
    import json

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get(CHUNKS_KEY), list):
        raise ArtifactIntegrityError(
            f"{path} must contain a {BUILD_ID_KEY} and a {CHUNKS_KEY} list; "
            "rebuild with python scripts/build_index.py"
        )
    return _require_build_id(raw.get(BUILD_ID_KEY), path), raw[CHUNKS_KEY]


def read_bm25_build_id(path: Path) -> str:
    import json

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ArtifactIntegrityError(
            f"{path} must be a JSON object; rebuild with python scripts/build_index.py"
        )
    return _require_build_id(raw.get(BUILD_ID_KEY), path)


def vector_artifact_bytes(build_id: str, vectors: bytes) -> bytes:
    """Prefix raw float32 bytes with the fixed-size, self-describing build id."""
    _require_build_id(build_id, "build id")
    return VECTOR_BUILD_ID_PREFIX + build_id.encode("ascii") + b"\n" + vectors


def read_vector_artifact(path: Path) -> tuple[str, bytes]:
    data = path.read_bytes()
    header = data[:VECTOR_HEADER_SIZE]
    if not header.startswith(VECTOR_BUILD_ID_PREFIX) or not header.endswith(b"\n"):
        raise ArtifactIntegrityError(
            f"{path} is missing its retrieval build-id header; rebuild with "
            "python scripts/build_index.py"
        )
    build_id = header[len(VECTOR_BUILD_ID_PREFIX) : -1].decode("ascii", errors="replace")
    return _require_build_id(build_id, path), data[VECTOR_HEADER_SIZE:]
