"""Check-in business logic: pick session, dedup, persist event."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AttendanceEvent, ClassSession, SpoofAttempt


logger = logging.getLogger(__name__)

DEDUP_WINDOW = timedelta(hours=1)


def active_session(db: Session, now: datetime | None = None) -> ClassSession | None:
    """Return the most recent ClassSession whose date is today.

    If multiple sessions exist for today, prefer the one whose time-window
    contains `now`; otherwise return the latest by start_time.
    """
    now = now or datetime.now()
    today = now.date()
    sessions = (
        db.query(ClassSession)
        .filter(ClassSession.scheduled_date == today)
        .order_by(ClassSession.start_time.desc())
        .all()
    )
    if not sessions:
        return None
    current_t = now.time()
    for s in sessions:
        if s.start_time <= current_t <= s.end_time:
            return s
    return sessions[0]


def recent_event_for_student(
    db: Session, student_id: int, session_id: int, within: timedelta = DEDUP_WINDOW
) -> AttendanceEvent | None:
    """Return the most recent AttendanceEvent for this student+session if it's
    within the dedup window, else None."""
    cutoff = datetime.utcnow() - within
    return (
        db.query(AttendanceEvent)
        .filter(
            and_(
                AttendanceEvent.student_id == student_id,
                AttendanceEvent.session_id == session_id,
                AttendanceEvent.checked_in_at >= cutoff,
            )
        )
        .order_by(AttendanceEvent.checked_in_at.desc())
        .first()
    )


def record_event(
    db: Session,
    *,
    student_id: int,
    session_id: int,
    confidence: float,
    liveness_score: float,
    source: str = "camera_door",
) -> AttendanceEvent:
    event = AttendanceEvent(
        student_id=student_id,
        session_id=session_id,
        confidence=confidence,
        liveness_score=liveness_score,
        source=source,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def record_spoof_attempt(
    db: Session,
    *,
    img_bgr: np.ndarray,
    session_id: int | None,
    liveness_score: float,
    notes: str | None = None,
) -> SpoofAttempt:
    """Save the spoof frame to spoof_log/ and write a SpoofAttempt row."""
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    out_path = settings.SPOOF_LOG_DIR / f"spoof_{ts}.jpg"
    settings.SPOOF_LOG_DIR.mkdir(exist_ok=True)
    cv2.imwrite(str(out_path), img_bgr)

    attempt = SpoofAttempt(
        session_id=session_id,
        liveness_score=float(liveness_score),
        image_path=str(out_path.relative_to(settings.SPOOF_LOG_DIR.parent)),
        notes=notes,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def ensure_today_session(db: Session) -> ClassSession:
    """Create a default session for today if none exists. Useful when the
    teacher forgot to seed one and a student walks up to the camera."""
    s = active_session(db)
    if s:
        return s
    from datetime import time
    s = ClassSession(
        name="Auto-created session",
        scheduled_date=date.today(),
        start_time=time(0, 0),
        end_time=time(23, 59),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s
