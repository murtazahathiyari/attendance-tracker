"""Quick Enroll endpoint.

POST /api/enroll with multipart form-data:
    - student_id: int (the student to enroll/re-enroll)
    - frames: file, repeated, 1-5 JPEG/PNG images at different angles
    - angle_labels: optional comma-separated list (defaults to straight,left,right,up,down)
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Student
from app.services.enrollment import ANGLE_LABELS, enroll_student


router = APIRouter(prefix="/api/enroll", tags=["enroll"])


@router.post("")
async def enroll(
    student_id: int = Form(...),
    frames: list[UploadFile] = File(...),
    angle_labels: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    if not frames:
        raise HTTPException(status_code=400, detail="Need at least one frame.")
    if len(frames) > 8:
        raise HTTPException(status_code=400, detail="Too many frames (max 8).")

    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    raw_frames: list[bytes] = []
    for f in frames:
        if not (f.content_type or "").startswith("image/"):
            raise HTTPException(status_code=400, detail=f"{f.filename} is not an image.")
        raw_frames.append(await f.read())

    labels = ANGLE_LABELS[: len(raw_frames)]
    if angle_labels:
        provided = [s.strip() for s in angle_labels.split(",") if s.strip()]
        if len(provided) == len(raw_frames):
            labels = provided

    result = enroll_student(db, student, raw_frames, angle_labels=labels)

    return {
        "ok": result.ok,
        "student_id": result.student_id,
        "frames_used": result.frames_used,
        "frames_failed": result.frames_failed,
        "failures": result.failures,
        "card_pdf_url": f"/api/cards/{student.id}.pdf" if result.ok else None,
        "card_html_url": f"/api/cards/{student.id}.html" if result.ok else None,
        "message": result.message,
    }
