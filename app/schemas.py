from datetime import date, datetime, time
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class StudentCreate(BaseModel):
    first_name: str
    last_name: str
    student_code: Optional[str] = None
    email: Optional[EmailStr] = None


class StudentUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    active: Optional[bool] = None


class StudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_code: str
    first_name: str
    last_name: str
    email: Optional[str] = None
    enrolled_at: Optional[datetime] = None
    active: bool
    has_embedding: bool = False


class ClassSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    scheduled_date: date
    start_time: time
    end_time: time


class AttendanceEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    session_id: int
    checked_in_at: datetime
    confidence: float
    liveness_score: float


class CheckinResult(BaseModel):
    """Returned from POST /api/checkin/verify."""

    status: str  # "ok" | "spoof" | "wrong_face" | "invalid_qr" | "duplicate" | "no_face" | "no_qr" | "multi_face"
    message: str
    student_name: Optional[str] = None
    confidence: Optional[float] = None
    liveness_score: Optional[float] = None
    checked_in_at: Optional[datetime] = None
