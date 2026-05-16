from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import ForeignKey, LargeBinary, UniqueConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(64))
    last_name: Mapped[str] = mapped_column(String(64))
    email: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # 512 float32 InsightFace embedding, L2-normalized and averaged over enrollment frames.
    # Stored as raw bytes; load with np.frombuffer(blob, dtype=np.float32).
    face_embedding: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    enrolled_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    active: Mapped[bool] = mapped_column(default=True)

    attendance_events: Mapped[list["AttendanceEvent"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )


class ClassSession(Base):
    __tablename__ = "class_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    scheduled_date: Mapped[date]
    start_time: Mapped[time]
    end_time: Mapped[time]
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    attendance_events: Mapped[list["AttendanceEvent"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class AttendanceEvent(Base):
    __tablename__ = "attendance_events"
    __table_args__ = (
        UniqueConstraint("student_id", "session_id", name="uq_student_session"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    session_id: Mapped[int] = mapped_column(ForeignKey("class_sessions.id", ondelete="CASCADE"))
    checked_in_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    confidence: Mapped[float] = mapped_column(default=0.0)
    liveness_score: Mapped[float] = mapped_column(default=0.0)
    source: Mapped[str] = mapped_column(String(32), default="camera_door")

    student: Mapped[Student] = relationship(back_populates="attendance_events")
    session: Mapped[ClassSession] = relationship(back_populates="attendance_events")


class SpoofAttempt(Base):
    __tablename__ = "spoof_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("class_sessions.id", ondelete="SET NULL"), nullable=True
    )
    detected_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    liveness_score: Mapped[float] = mapped_column(default=0.0)
    image_path: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)


class AttendanceThreshold(Base):
    """Single-row k/v config table for runtime-tunable thresholds."""

    __tablename__ = "attendance_thresholds"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(128))


class AlertLog(Base):
    __tablename__ = "alert_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    triggered_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    attendance_pct: Mapped[float] = mapped_column(default=0.0)
    sent_to: Mapped[str] = mapped_column(String(128))
