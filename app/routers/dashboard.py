"""Read-only stats endpoints powering the dashboard."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import AttendanceEvent, ClassSession, SpoofAttempt, Student


router = APIRouter(prefix="/api/stats", tags=["stats"])


def _sessions_in_window(db: Session, days: int) -> list[ClassSession]:
    start = date.today() - timedelta(days=days - 1)
    return (
        db.query(ClassSession)
        .filter(ClassSession.scheduled_date >= start)
        .filter(ClassSession.scheduled_date <= date.today())
        .order_by(ClassSession.scheduled_date.asc(), ClassSession.start_time.asc())
        .all()
    )


@router.get("/overview")
def overview(days: int = 30, db: Session = Depends(get_db)) -> dict:
    days = max(1, min(days, 365))
    sessions = _sessions_in_window(db, days)
    session_ids = [s.id for s in sessions]

    total_students = db.query(func.count(Student.id)).filter(Student.active.is_(True)).scalar() or 0
    enrolled = (
        db.query(func.count(Student.id))
        .filter(Student.active.is_(True), Student.face_embedding.isnot(None))
        .scalar()
        or 0
    )

    today_sessions = [s for s in sessions if s.scheduled_date == date.today()]
    attended_today = 0
    if today_sessions:
        attended_today = (
            db.query(func.count(distinct(AttendanceEvent.student_id)))
            .filter(AttendanceEvent.session_id.in_([s.id for s in today_sessions]))
            .scalar()
            or 0
        )

    spoof_24h = (
        db.query(func.count(SpoofAttempt.id))
        .filter(SpoofAttempt.detected_at >= datetime.utcnow() - timedelta(hours=24))
        .scalar()
        or 0
    )

    # Class-wide attendance % across the window
    class_pct = 0.0
    if total_students and session_ids:
        attended_pairs = (
            db.query(func.count(distinct(
                func.concat(AttendanceEvent.student_id, "_", AttendanceEvent.session_id)
            )))
            .filter(AttendanceEvent.session_id.in_(session_ids))
            .scalar()
            or 0
        )
        possible = total_students * len(session_ids)
        class_pct = round(100.0 * attended_pairs / possible, 1) if possible else 0.0

    return {
        "total_students": total_students,
        "enrolled": enrolled,
        "enrolled_pct": round(100.0 * enrolled / total_students, 1) if total_students else 0,
        "session_count_window": len(sessions),
        "today_session_count": len(today_sessions),
        "attended_today": attended_today,
        "class_pct_window": class_pct,
        "spoof_24h": spoof_24h,
        "min_attendance_pct": float(settings.MIN_ATTENDANCE_PCT),
        "window_days": days,
    }


@router.get("/per-student")
def per_student(
    days: int = 30,
    flagged_only: bool = False,
    db: Session = Depends(get_db),
) -> list[dict]:
    """Per-student attendance % over the window."""
    days = max(1, min(days, 365))
    sessions = _sessions_in_window(db, days)
    session_ids = [s.id for s in sessions]
    n_sessions = len(session_ids)

    students = (
        db.query(Student)
        .filter(Student.active.is_(True))
        .order_by(Student.last_name, Student.first_name)
        .all()
    )

    rows = []
    for s in students:
        if n_sessions == 0:
            attended = 0
            pct = 0.0
        else:
            attended = (
                db.query(func.count(distinct(AttendanceEvent.session_id)))
                .filter(AttendanceEvent.student_id == s.id)
                .filter(AttendanceEvent.session_id.in_(session_ids))
                .scalar()
                or 0
            )
            pct = round(100.0 * attended / n_sessions, 1)

        flagged = pct < settings.MIN_ATTENDANCE_PCT and n_sessions > 0
        if flagged_only and not flagged:
            continue
        rows.append(
            {
                "student_id": s.id,
                "student_code": s.student_code,
                "name": f"{s.first_name} {s.last_name}",
                "attended": attended,
                "total_sessions": n_sessions,
                "attendance_pct": pct,
                "flagged": flagged,
                "enrolled": s.face_embedding is not None,
            }
        )
    return rows


@router.get("/by-day")
def by_day(days: int = 7, db: Session = Depends(get_db)) -> list[dict]:
    """Class-wide attendance per day for a bar chart."""
    days = max(1, min(days, 90))
    out = []
    total_students = db.query(func.count(Student.id)).filter(Student.active.is_(True)).scalar() or 0

    for offset in range(days - 1, -1, -1):
        d = date.today() - timedelta(days=offset)
        day_sessions = (
            db.query(ClassSession.id)
            .filter(ClassSession.scheduled_date == d)
            .all()
        )
        session_ids = [r[0] for r in day_sessions]

        if not session_ids:
            out.append({"date": d.isoformat(), "attended": 0, "possible": 0, "pct": None})
            continue

        attended = (
            db.query(func.count(distinct(AttendanceEvent.student_id)))
            .filter(AttendanceEvent.session_id.in_(session_ids))
            .scalar()
            or 0
        )
        possible = total_students * len(session_ids)
        pct = round(100.0 * attended / possible, 1) if possible else None
        out.append({"date": d.isoformat(), "attended": attended, "possible": possible, "pct": pct})
    return out


@router.get("/recent-events")
def recent_events(limit: int = 20, db: Session = Depends(get_db)) -> list[dict]:
    limit = max(1, min(limit, 200))
    rows = (
        db.query(AttendanceEvent, Student)
        .join(Student, AttendanceEvent.student_id == Student.id)
        .order_by(AttendanceEvent.checked_in_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": ev.id,
            "student_id": st.id,
            "student_name": f"{st.first_name} {st.last_name}",
            "student_code": st.student_code,
            "checked_in_at": ev.checked_in_at.isoformat() + "Z",
            "confidence": ev.confidence,
            "liveness_score": ev.liveness_score,
            "session_id": ev.session_id,
        }
        for ev, st in rows
    ]


# ---- Spoof log ------------------------------------------------------------


spoof_router = APIRouter(prefix="/api/spoof-log", tags=["spoof"])


@spoof_router.get("")
def list_spoof(limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    limit = max(1, min(limit, 500))
    rows = (
        db.query(SpoofAttempt)
        .order_by(SpoofAttempt.detected_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "detected_at": r.detected_at.isoformat() + "Z",
            "liveness_score": r.liveness_score,
            "session_id": r.session_id,
            "notes": r.notes,
            "image_url": f"/api/spoof-log/{r.id}/image" if r.image_path else None,
        }
        for r in rows
    ]


@spoof_router.get("/{spoof_id}/image")
def get_spoof_image(spoof_id: int, db: Session = Depends(get_db)):
    row = db.get(SpoofAttempt, spoof_id)
    if not row or not row.image_path:
        raise HTTPException(status_code=404, detail="No image for this attempt.")
    path = (Path(__file__).resolve().parent.parent.parent / row.image_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Spoof frame missing on disk.")
    return FileResponse(path, media_type="image/jpeg")


@spoof_router.post("/clear")
def clear_spoof(db: Session = Depends(get_db)) -> dict:
    """Delete all spoof attempts and their saved frames."""
    rows = db.query(SpoofAttempt).all()
    deleted_files = 0
    for r in rows:
        if r.image_path:
            p = Path(__file__).resolve().parent.parent.parent / r.image_path
            try:
                p.unlink(missing_ok=True)
                deleted_files += 1
            except OSError:
                pass
        db.delete(r)
    db.commit()
    return {"rows_deleted": len(rows), "files_deleted": deleted_files}
