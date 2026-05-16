"""Serve generated ID card files (PDF + HTML preview)."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Student
from app.services.enrollment import card_paths


router = APIRouter(prefix="/api/cards", tags=["cards"])


def _lookup_paths(db: Session, student_id: int):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    if not student.face_embedding:
        raise HTTPException(status_code=409, detail="Student not enrolled yet — no card to print.")
    return student, *card_paths(student)


@router.get("/{student_id}.pdf")
def get_pdf(student_id: int, db: Session = Depends(get_db)):
    student, pdf_path, _ = _lookup_paths(db, student_id)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not generated yet. Re-enroll.")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"{student.student_code}_card.pdf",
    )


@router.get("/{student_id}.html")
def get_html(student_id: int, db: Session = Depends(get_db)):
    student, _, html_path = _lookup_paths(db, student_id)
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="HTML not generated yet. Re-enroll.")
    return FileResponse(html_path, media_type="text/html")
