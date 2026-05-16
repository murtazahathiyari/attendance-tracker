"""Check-in pipeline.

One endpoint: POST /api/checkin/process — accepts a single JPEG frame,
runs through the cheap-then-expensive pipeline with early returns,
and tells the client what to display.

Pipeline (each step can early-return):
    1. Decode frame, look for a QR code             (cheap)
    2. Verify HMAC signature on QR                  (cheap)
    3. Look up student + ensure they're enrolled    (cheap)
    4. Liveness check via DeepFace                  (expensive, Step 9 wires it in)
    5. Detect + embed face via InsightFace          (expensive)
    6. 1:1 cosine similarity vs stored embedding    (cheap once embed is done)
    7. Dedup against active session                 (cheap)
    8. Log AttendanceEvent                          (cheap)
"""
from __future__ import annotations

import io
import logging
from datetime import datetime

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Student
from app.services import face, liveness, qr
from app.services.attendance import (
    active_session,
    ensure_today_session,
    recent_event_for_student,
    record_event,
    record_spoof_attempt,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/checkin", tags=["checkin"])


async def _read_frame(upload: UploadFile) -> np.ndarray:
    if not (upload.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="Expected an image upload.")
    raw = await upload.read()
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Not a decodable image.")
    return img


def _resp(state: str, message: str, **extra) -> dict:
    return {"state": state, "message": message, **extra}


@router.post("/process")
async def process_frame(
    frame: UploadFile,
    auto_create_session: bool = True,
    db: Session = Depends(get_db),
):
    img = await _read_frame(frame)

    # --- 1. Cheap gate: QR detection ----------------------------------------
    token = qr.decode_from_frame(img)
    if not token:
        return _resp("no_qr", "Hold your ID card up next to your face.")

    # --- 2. Verify HMAC -----------------------------------------------------
    student_id = qr.verify_token(token)
    if student_id is None:
        return _resp("invalid_qr", "This card isn't recognized.")

    # --- 3. Look up student -------------------------------------------------
    student: Student | None = db.get(Student, student_id)
    if not student or not student.active:
        return _resp("invalid_qr", "Card valid but student not in roster.")
    if not student.face_embedding:
        return _resp("invalid_qr", f"{student.first_name} isn't enrolled yet.")

    # --- 4. Liveness check --------------------------------------------------
    is_real, liveness_score, lstatus = liveness.is_live(img)
    if lstatus == "no_face":
        return _resp("no_face", "Step into view of the camera.")
    if lstatus == "multi_face":
        return _resp("multi_face", "One student at a time, please.")
    if liveness_score < settings.LIVENESS_THRESHOLD or not is_real:
        session_id_for_spoof = (active_session(db).id if active_session(db) else None)
        record_spoof_attempt(
            db,
            img_bgr=img,
            session_id=session_id_for_spoof,
            liveness_score=liveness_score,
            notes=f"Claimed student_id={student.id} ({student.first_name} {student.last_name})",
        )
        return _resp(
            "spoof",
            "SPOOF DETECTED — please present yourself in person.",
            liveness_score=float(liveness_score),
        )

    # --- 5. Face detection + embedding -------------------------------------
    emb, status = face.embed_single_face(img)
    if status == "no_face":
        return _resp("no_face", "Step into view of the camera.")
    if status == "multi_face":
        return _resp("multi_face", "One student at a time, please.")

    # --- 6. 1:1 verification -----------------------------------------------
    stored = face.deserialize_embedding(student.face_embedding)
    sim = face.cosine_similarity(emb, stored)
    if sim < settings.FACE_MATCH_THRESHOLD:
        return _resp(
            "wrong_face",
            "Face doesn't match this ID card.",
            confidence=sim,
        )

    # --- 7. Find session ---------------------------------------------------
    session = active_session(db) or (ensure_today_session(db) if auto_create_session else None)
    if not session:
        return _resp("no_session", "No class session is active right now.")

    # --- 7b. Dedup ---------------------------------------------------------
    existing = recent_event_for_student(db, student.id, session.id)
    if existing:
        return _resp(
            "duplicate",
            f"Already checked in at {existing.checked_in_at.strftime('%I:%M %p').lstrip('0')}.",
            student_name=f"{student.first_name} {student.last_name}",
            checked_in_at=existing.checked_in_at.isoformat() + "Z",
        )

    # --- 8. Log ------------------------------------------------------------
    event = record_event(
        db,
        student_id=student.id,
        session_id=session.id,
        confidence=float(sim),
        liveness_score=float(liveness_score),
    )

    return _resp(
        "ok",
        f"Welcome, {student.first_name}!",
        student_name=f"{student.first_name} {student.last_name}",
        student_code=student.student_code,
        confidence=float(sim),
        liveness_score=float(liveness_score),
        checked_in_at=event.checked_in_at.isoformat() + "Z",
        session_name=session.name,
    )
