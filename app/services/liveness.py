"""Passive single-frame anti-spoofing via DeepFace's MiniFASNet model.

First call downloads ~50MB of model weights (DeepFace lazy-loads). It also
pulls in TensorFlow for the underlying inference, which is already
installed via requirements.txt.
"""
from __future__ import annotations

import logging
from threading import Lock
from typing import Literal

import numpy as np


logger = logging.getLogger(__name__)

_load_lock = Lock()
_loaded = False
LivenessStatus = Literal["ok", "spoof", "no_face", "multi_face", "error"]


def _warm():
    """Trigger DeepFace's lazy loads once. Safe to call repeatedly."""
    global _loaded
    if _loaded:
        return
    with _load_lock:
        if _loaded:
            return
        import deepface  # noqa: F401  — just ensure the module is importable
        logger.info("DeepFace warmed (anti-spoof model loads on first extract_faces call).")
        _loaded = True


def is_live(img_bgr: np.ndarray) -> tuple[bool, float, LivenessStatus]:
    """Return (is_real, antispoof_score, status).

    Uses DeepFace's MiniFASNet model. Detects faces internally; if the
    detection finds nothing, returns status='no_face' rather than raising.
    """
    from deepface import DeepFace

    _warm()
    try:
        results = DeepFace.extract_faces(
            img_path=img_bgr,
            anti_spoofing=True,
            enforce_detection=False,
            detector_backend="opencv",
        )
    except Exception as e:
        logger.warning("DeepFace extract_faces error: %s", e)
        return False, 0.0, "error"

    if not results:
        return False, 0.0, "no_face"

    # Filter out the "fallback whole-image" result that DeepFace returns
    # when enforce_detection=False and no face is actually detected.
    real_faces = [
        r for r in results
        if r.get("facial_area", {}).get("w", 0) > 0 and r.get("confidence", 0) > 0.1
    ]
    if not real_faces:
        return False, 0.0, "no_face"
    if len(real_faces) > 1:
        return False, 0.0, "multi_face"

    r = real_faces[0]
    is_real = bool(r.get("is_real", False))
    score = float(r.get("antispoof_score", 0.0))
    return is_real, score, "ok" if is_real else "spoof"
