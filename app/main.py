from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import PROJECT_ROOT
from app.database import Base, engine
from app.routers import camera_test, cards, checkin, enroll, students


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on first run. For schema changes during early dev,
    # delete attendance.db and re-run seed.py.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Attendance Tracker", lifespan=lifespan)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(students.router)
app.include_router(camera_test.router)
app.include_router(enroll.router)
app.include_router(cards.router)
app.include_router(checkin.router)


@app.get("/")
def index():
    return RedirectResponse(url="/students-page")


@app.get("/students-page", include_in_schema=False)
def students_page():
    return FileResponse(STATIC_DIR / "students.html")


@app.get("/camera-test", include_in_schema=False)
def camera_test_page():
    return FileResponse(STATIC_DIR / "camera_test.html")


@app.get("/enroll-page", include_in_schema=False)
def enroll_page():
    return FileResponse(STATIC_DIR / "enroll.html")


@app.get("/checkin-page", include_in_schema=False)
def checkin_page():
    return FileResponse(STATIC_DIR / "checkin.html")


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "ok"}
