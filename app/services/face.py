"""InsightFace wrapper: detection + embedding + 1:1 verification.

Loads the `buffalo_l` model once on first call. First call downloads
~280MB to ~/.insightface/models/ — looks frozen but isn't.
"""
from __future__ import annotations

import logging
from threading import Lock

import numpy as np


logger = logging.getLogger(__name__)

_app = None
_lock = Lock()


def _get_app():
    """Lazy-load the InsightFace FaceAnalysis pipeline (CPU)."""
    global _app
    if _app is not None:
        return _app
    with _lock:
        if _app is not None:
            return _app
        from insightface.app import FaceAnalysis

        logger.info("Loading InsightFace buffalo_l model... (first run downloads ~280MB)")
        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=-1, det_size=(640, 640))  # ctx_id=-1 => CPU
        _app = app
        logger.info("InsightFace model ready.")
        return _app


def detect_faces(img_bgr: np.ndarray) -> list:
    """Return InsightFace's Face objects for the image.

    Each face has: bbox, kps (5 landmarks), det_score, embedding,
    normed_embedding, age, gender, etc.
    """
    return _get_app().get(img_bgr)


def embed_single_face(img_bgr: np.ndarray) -> tuple[np.ndarray | None, str]:
    """Detect one face and return its L2-normalized 512-dim embedding.

    Returns (embedding, status) where status is one of:
        "ok"          — exactly one face found
        "no_face"     — zero faces detected
        "multi_face"  — more than one face detected
    """
    faces = detect_faces(img_bgr)
    if len(faces) == 0:
        return None, "no_face"
    if len(faces) > 1:
        return None, "multi_face"
    return faces[0].normed_embedding.astype(np.float32), "ok"


def average_embeddings(embeddings: list[np.ndarray]) -> np.ndarray:
    """Average several normed embeddings into one, then L2-renormalize."""
    if not embeddings:
        raise ValueError("Need at least one embedding")
    stacked = np.stack(embeddings, axis=0).astype(np.float32)
    mean = stacked.mean(axis=0)
    norm = np.linalg.norm(mean)
    if norm == 0:
        raise ValueError("Embeddings averaged to zero vector")
    return (mean / norm).astype(np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity assuming both are L2-normalized."""
    return float(np.dot(a, b))


def serialize_embedding(emb: np.ndarray) -> bytes:
    """Convert a float32 (512,) embedding to bytes for SQLite BLOB storage."""
    return emb.astype(np.float32).tobytes()


def deserialize_embedding(blob: bytes) -> np.ndarray:
    """Inverse of serialize_embedding."""
    return np.frombuffer(blob, dtype=np.float32)
