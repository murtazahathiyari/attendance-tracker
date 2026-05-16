from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Student
from app.schemas import StudentCreate, StudentOut, StudentUpdate


router = APIRouter(prefix="/api/students", tags=["students"])


def _to_out(student: Student) -> StudentOut:
    return StudentOut(
        id=student.id,
        student_code=student.student_code,
        first_name=student.first_name,
        last_name=student.last_name,
        email=student.email,
        enrolled_at=student.enrolled_at,
        active=student.active,
        has_embedding=student.face_embedding is not None,
    )


def _next_student_code(db: Session) -> str:
    count = db.query(Student).count()
    return f"S{count + 1:03d}"


@router.get("", response_model=list[StudentOut])
def list_students(active_only: bool = False, db: Session = Depends(get_db)):
    query = db.query(Student)
    if active_only:
        query = query.filter(Student.active.is_(True))
    return [_to_out(s) for s in query.order_by(Student.last_name, Student.first_name).all()]


@router.get("/{student_id}", response_model=StudentOut)
def get_student(student_id: int, db: Session = Depends(get_db)):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return _to_out(student)


@router.post("", response_model=StudentOut, status_code=201)
def create_student(payload: StudentCreate, db: Session = Depends(get_db)):
    code = payload.student_code or _next_student_code(db)

    existing = db.query(Student).filter(Student.student_code == code).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"student_code {code} already exists")

    student = Student(
        student_code=code,
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        email=payload.email,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return _to_out(student)


@router.patch("/{student_id}", response_model=StudentOut)
def update_student(student_id: int, payload: StudentUpdate, db: Session = Depends(get_db)):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(student, key, value)

    db.commit()
    db.refresh(student)
    return _to_out(student)


@router.delete("/{student_id}", status_code=204)
def delete_student(student_id: int, db: Session = Depends(get_db)):
    """Right-to-be-forgotten: removes the student, their embedding,
    and all attendance/alert rows referencing them (via ON DELETE CASCADE)."""
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    db.delete(student)
    db.commit()
    return None
