"""Quick Enroll orchestration.

Takes 1-5 frames of a student, computes their face embedding,
stores artifacts to enrollment_data/ and id_cards/, and writes the
signed-QR ID card.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Student
from app.services import face, qr
from app.services.cards import write_card_pdf, write_card_html


logger = logging.getLogger(__name__)

ANGLE_LABELS = ["straight", "left", "right", "up", "down"]
MIN_GOOD_FRAMES = 1  # one valid frame is enough to enroll; more = more robust


@dataclass
class EnrollResult:
    ok: bool
    student_id: int
    frames_used: int = 0
    frames_failed: int = 0
    failures: list[str] = field(default_factory=list)
    card_pdf_path: str | None = None
    card_html_path: str | None = None
    message: str = ""


def _slug(name: str) -> str:
    """Filesystem-safe slug for a name like 'Ava Patel' -> 'ava_patel'."""
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_")
    return s or "student"


def student_dir(student: Student) -> Path:
    return settings.ENROLLMENT_DIR / f"{student.student_code}_{_slug(student.first_name + ' ' + student.last_name)}"


def card_paths(student: Student) -> tuple[Path, Path]:
    base = settings.ID_CARDS_DIR / f"{student.student_code}_{_slug(student.first_name + ' ' + student.last_name)}"
    return base.with_suffix(".pdf"), base.with_suffix(".html")


def _decode_frame(raw: bytes) -> np.ndarray | None:
    """Decode an in-memory JPEG/PNG byte string to a BGR numpy array."""
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def enroll_student(
    db: Session,
    student: Student,
    frames_raw: list[bytes],
    angle_labels: list[str] | None = None,
) -> EnrollResult:
    """Enroll `student` using the provided JPEG/PNG-encoded frames.

    Steps:
        1. Decode each frame, run face detection + embedding
        2. Require at least MIN_GOOD_FRAMES valid (exactly-one-face) embeddings
        3. L2-renormalize the average → student's stored embedding
        4. Persist artifacts to enrollment_data/{code}_{name}/
        5. Render PDF + HTML ID cards to id_cards/{code}_{name}.*
    """
    if angle_labels is None:
        angle_labels = ANGLE_LABELS[: len(frames_raw)]

    result = EnrollResult(ok=False, student_id=student.id)
    valid_embeddings: list[np.ndarray] = []
    saved_frames: list[tuple[str, bytes]] = []

    for i, (raw, label) in enumerate(zip(frames_raw, angle_labels), start=1):
        img = _decode_frame(raw)
        if img is None:
            result.frames_failed += 1
            result.failures.append(f"frame_{i:02d}_{label}: not a valid image")
            continue
        emb, status = face.embed_single_face(img)
        if emb is None:
            result.frames_failed += 1
            result.failures.append(f"frame_{i:02d}_{label}: {status}")
            continue
        valid_embeddings.append(emb)
        saved_frames.append((f"frame_{i:02d}_{label}.jpg", raw))

    result.frames_used = len(valid_embeddings)

    if result.frames_used < MIN_GOOD_FRAMES:
        result.message = (
            f"Enrollment failed: only {result.frames_used}/{len(frames_raw)} frames "
            f"contained exactly one face. Need at least {MIN_GOOD_FRAMES}."
        )
        return result

    averaged = face.average_embeddings(valid_embeddings)

    # Persist to disk first — if DB write fails, files are reproducible from DB.
    out_dir = student_dir(student)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for name, raw in saved_frames:
        (out_dir / name).write_bytes(raw)
    np.save(out_dir / "embedding.npy", averaged)
    (out_dir / "metadata.json").write_text(
        json.dumps(
            {
                "student_code": student.student_code,
                "first_name": student.first_name,
                "last_name": student.last_name,
                "enrolled_at": datetime.utcnow().isoformat() + "Z",
                "frames_used": result.frames_used,
                "frames_failed": result.frames_failed,
                "embedding_dim": int(averaged.shape[0]),
            },
            indent=2,
        )
    )

    student.face_embedding = face.serialize_embedding(averaged)
    student.enrolled_at = datetime.utcnow()
    db.commit()

    # Generate card artifacts AFTER the student is committed so the QR
    # signing uses the canonical student.id.
    token = qr.sign_payload(student.id)
    qr_png = qr.generate_qr_png(token)
    pdf_path, html_path = card_paths(student)
    write_card_pdf(pdf_path, student, qr_png)
    write_card_html(html_path, student, qr_png, token)

    result.ok = True
    result.card_pdf_path = str(pdf_path)
    result.card_html_path = str(html_path)
    result.message = f"Enrolled {student.first_name} {student.last_name} from {result.frames_used} frame(s)."
    logger.info(result.message)
    return result
