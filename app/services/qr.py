"""Signed QR tokens for printable student ID cards.

The QR encodes `{sid, sig}` where `sig` is the first 16 hex chars of
HMAC-SHA256(SECRET_KEY, json({sid: N})). An attacker can't forge a QR
for a student that doesn't exist without knowing SECRET_KEY.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import logging

import numpy as np

from app.config import settings


logger = logging.getLogger(__name__)

SIG_LEN = 16  # first 16 hex chars of HMAC-SHA256 is plenty for a 30-student class


def _canonical_msg(student_id: int) -> bytes:
    return json.dumps({"sid": student_id}, separators=(",", ":")).encode()


def _compute_sig(student_id: int) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(),
        _canonical_msg(student_id),
        hashlib.sha256,
    ).hexdigest()[:SIG_LEN]


def sign_payload(student_id: int) -> str:
    """Return a base64url-encoded token to embed in the QR."""
    payload = {"sid": int(student_id), "sig": _compute_sig(student_id)}
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def verify_token(token: str) -> int | None:
    """Return the student_id if signature is valid, else None."""
    if not token:
        return None
    try:
        padding = "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode((token + padding).encode())
        payload = json.loads(raw)
        sid = int(payload["sid"])
        provided_sig = str(payload["sig"])
    except (ValueError, KeyError, TypeError):
        return None

    expected_sig = _compute_sig(sid)
    if not hmac.compare_digest(provided_sig, expected_sig):
        return None
    return sid


def generate_qr_png(token: str, box_size: int = 10, border: int = 2) -> bytes:
    """Return a PNG byte string with the QR code rendered."""
    import qrcode

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(token)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def decode_from_frame(img_bgr: np.ndarray) -> str | None:
    """Try to decode a QR from a BGR frame. Returns the token string or None."""
    import cv2

    detector = cv2.QRCodeDetector()
    data, _points, _straight_qr = detector.detectAndDecode(img_bgr)
    return data if data else None
