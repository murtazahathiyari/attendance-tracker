"""Seed the database with 5 fake students + today's class session.

Run from the project root:
    python seed.py

Safe to run multiple times — only inserts if the rows aren't already there.
"""
from datetime import date, time

from app.database import Base, SessionLocal, engine
from app.models import AttendanceThreshold, ClassSession, Student


FAKE_STUDENTS = [
    ("S001", "Ava", "Patel"),
    ("S002", "Ben", "Garcia"),
    ("S003", "Chloe", "Nguyen"),
    ("S004", "Diego", "Martinez"),
    ("S005", "Emma", "Johnson"),
]


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Students
        for code, first, last in FAKE_STUDENTS:
            exists = db.query(Student).filter(Student.student_code == code).first()
            if not exists:
                db.add(Student(student_code=code, first_name=first, last_name=last))

        # Today's class session
        today = date.today()
        session = (
            db.query(ClassSession)
            .filter(ClassSession.scheduled_date == today)
            .first()
        )
        if not session:
            db.add(
                ClassSession(
                    name="Period 3 — Demo Class",
                    scheduled_date=today,
                    start_time=time(9, 0),
                    end_time=time(9, 50),
                )
            )

        # Default attendance threshold
        threshold = db.query(AttendanceThreshold).filter_by(key="min_attendance_pct").first()
        if not threshold:
            db.add(AttendanceThreshold(key="min_attendance_pct", value="80"))

        db.commit()
        print("Seeded:")
        print(f"  {db.query(Student).count()} students")
        print(f"  {db.query(ClassSession).count()} class sessions")
        print("Ready. Run: python run.py")
    finally:
        db.close()


if __name__ == "__main__":
    main()
