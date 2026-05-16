# Attendance Tracker — Build Plan

> Portable, in-repo build plan. Lets you (or AI helpers) pick up work from
> any machine without losing context. See [../README.md](../README.md) for
> setup instructions.

## Why this project exists

Capstone for an 8th-grade student. Original idea was a custom dashboard on
top of Jibble's API; pivoted to a from-scratch open-source build because
Jibble already ships dashboards, scheduled reports, and threshold alerts
out of the box — a thin wrapper would have been a weak capstone story.

The from-scratch build gives:
1. A defensible story — every architectural choice is his
2. A demo "wow" moment — hold up a phone photo of a student and watch the
   system reject it as a spoof
3. Real learning across web dev, databases, computer vision, ethics
4. Zero subscription cost — the actual problem statement ("schools
   shouldn't need paid SaaS for attendance")

**MVP scope:** single teacher, single class, ~30 students. Runs on the
teacher's Windows or Mac laptop with the built-in webcam. No cloud.

---

## Stack (all pinned in [../requirements.txt](../requirements.txt))

| Layer | Choice | Reason |
|---|---|---|
| Runtime | **Python 3.11** | DeepFace + onnxruntime wheels target 3.11 |
| Web | FastAPI 0.115 + uvicorn | Easy, AI-coding-assistant friendly |
| Database | SQLite + SQLAlchemy 2.x ORM | Zero-setup, ORM friendlier than raw sqlite3 |
| Face embedding | **InsightFace 0.7.3** (onnxruntime) | Best OSS embedder, no dlib install pain |
| Liveness/anti-spoof | **DeepFace 0.0.93** `anti_spoofing=True` | One flag → MiniFASNet model |
| QR | `qrcode` + `cv2.QRCodeDetector` | Stdlib-ish |
| Scheduler | APScheduler 3.10 BackgroundScheduler | One process, in-FastAPI lifespan |
| PDF cards | `reportlab` 4.2 | Pure-Python PDF generator |
| Email | stdlib `smtplib` + Gmail app password | No extra deps |
| Frontend | Vanilla HTML/JS + Chart.js (CDN) | No build tooling |

**Hard pin:** `numpy<2`. InsightFace, onnxruntime, and OpenCV all break on
NumPy 2.x with cryptic `np.float_` errors.

---

## Architecture decisions worth knowing

### Why InsightFace, not `face_recognition`
`face_recognition` uses dlib, which needs a C++ build toolchain on Windows
unless you find an unofficial wheel. InsightFace is pure-pip via
onnxruntime, equally accurate, and installs cleanly on every platform.

### Why printed per-student QR cards, not rotating TOTP
With a single laptop using its built-in webcam, there is no second screen
to display a rotating kiosk QR — the camera can't see its own screen.
Per-student printed cards solve the geometry problem; the "stolen card"
attack is defeated by 1:1 face verification + liveness detection.

If the hardware later becomes "laptop at door + tablet at door" (two
screens), revisit this — TOTP becomes viable again.

### Why two-stage check-in pipeline
The expensive ML pipeline (DeepFace + InsightFace) runs at maybe 1–3 fps.
A naive "POST every frame" approach saturates the laptop's CPU. Two-stage:
1. **Cheap gate (30fps)** — detect a face + decode a QR in the frame. UI
   shows state-machine prompts: idle, "one at a time," "hold up your
   card," etc.
2. **Expensive verify (fires once)** — when gate passes, do HMAC check →
   liveness → 1:1 face match → dedup → log.

### Why no Alembic / no migrations
Single-laptop demo project. `Base.metadata.create_all()` at startup is
enough. If schema changes mid-development, delete `attendance.db` and
re-run `seed.py`.

### Privacy posture
- Database stores **embeddings only** (512-float vectors), never raw photos
- `enrollment_data/` holds capture frames for troubleshooting; teacher can
  delete the folder at any time
- "Delete student" cascades to embedding + all attendance/alert rows
- Spoof attempts logged with frame saved to `spoof_log/`; "Clear log"
  button purges them
- Local-only — data never leaves the laptop
- README + slide deck must mention parental opt-in for biometric data

---

## Threat model

| Attack | Defense |
|---|---|
| Photo of another student (on phone or printed) | **Liveness** (MiniFASNet) rejects flat 2D images |
| Video replay of another student | Liveness rejects most; per-frame check |
| Steal another student's ID card | **1:1 face verification** — face doesn't match the claimed identity |
| Forge a fake QR | **HMAC signature** check fails |
| Remote attendance from home | Camera physically at the door |
| Identical twin | **Known limitation** — manual override; flag in slides |
| Professional 3D mask | **Out of scope** — acknowledge in slides |

---

## Project layout

```
attendance_tracker/
  app/
    main.py               FastAPI entry, lifespan starts scheduler
    config.py             pydantic-settings, .env loader, paths
    database.py           SQLAlchemy engine + SessionLocal + get_db
    models.py             6 tables
    schemas.py            pydantic request/response shapes
    routers/
      students.py         ✓ Roster CRUD
      camera_test.py      ✓ Step 4 stub (delete once Step 8 lands)
      enroll.py           [Step 5/6] enrollment endpoints
      checkin.py          [Step 8] /api/checkin/gate + /verify
      dashboard.py        [Step 10] stats endpoints
      cards.py            [Step 7] printable card PDF/HTML
    services/
      face.py             [Step 5] InsightFace wrapper — embed, verify, detect
      liveness.py         [Step 9] DeepFace wrapper — is_live(img)
      qr.py               [Step 7] sign, verify, decode_from_frame
      attendance.py       [Step 8] check_in() business logic + dedup
      enrollment.py       [Step 6] quick_enroll() — saves frames + makes card
      reporting.py        [Step 11] weekly_report() HTML + email
      email.py            [Step 11] SMTP helper
    scheduler.py          [Step 11] APScheduler setup
    static/               HTML/CSS/JS served by FastAPI
    templates/            Jinja2 (weekly_email.html, card.html)
  enrollment_data/        Per-student capture frames (gitignored)
  id_cards/               Printable PDF cards (gitignored)
  spoof_log/              Rejected-spoof frames (gitignored)
  requirements.txt
  .env.example
  run.py
  seed.py
  attendance.db           SQLite (gitignored)
```

---

## Database schema (in [../app/models.py](../app/models.py))

- **Student** — id, student_code (unique), first/last name, email, **face_embedding (BLOB, 512×float32, L2-normalized)**, enrolled_at, active
- **ClassSession** — id, name, scheduled_date, start_time, end_time
- **AttendanceEvent** — id, student_id, session_id, checked_in_at, confidence, liveness_score, source. `UNIQUE(student_id, session_id)` for DB-level dedup
- **SpoofAttempt** — id, session_id (nullable), detected_at, liveness_score, image_path, notes
- **AttendanceThreshold** — k/v config (`min_attendance_pct=80`)
- **AlertLog** — id, student_id, triggered_at, attendance_pct, sent_to

---

## Implementation status

> Each step is a commit and a demoable milestone. If time runs out after
> step 9, the project still presents well.

- [x] **Step 1 — Setup**: Python 3.11, venv, requirements, FastAPI skeleton
- [x] **Step 2 — Models + seed**: SQLAlchemy schema, `seed.py` creates 5 fake students + today's session
- [x] **Step 3 — Roster page**: `/students-page` CRUD UI, full API at `/api/students`
- [x] **Step 4 — Webcam pipeline scaffold**: `/camera-test` + `/api/camera-test/echo` stub
- [ ] **Step 5 — Face enrollment v1**: `services/face.py` InsightFace wrapper; capture 1 frame, embed, store in `Student.face_embedding`
- [ ] **Step 6 — Quick Enroll v2**: 5-angle guided UI (straight/left/right/up/down); save frames to `enrollment_data/{code}_{name}/`; L2-normalized average embedding
- [ ] **Step 7 — Signed QR ID cards**: HMAC payload in `services/qr.py`; `services/qr.py::decode_from_frame()`; `routers/cards.py` renders PDF via `reportlab` (4 cards per page) to `id_cards/`
- [ ] **Step 8 — Two-stage check-in**: `routers/checkin.py` with `/gate` (cheap detect) and `/verify` (expensive); state-machine overlays in `static/checkin.html`; 3-second confirmation flag; 3-second cooldown
- [ ] **Step 9 — Liveness**: DeepFace `anti_spoofing=True` in `services/liveness.py`; integrate into `/verify`; save failed frames to `spoof_log/` + `SpoofAttempt` row
- [ ] **Step 10 — Dashboard**: `routers/dashboard.py` stats endpoints; `static/dashboard.html` with Chart.js (weekly/monthly bars + per-student filter); spoof log viewer
- [ ] **Step 11 — APScheduler + weekly Gmail report**: `services/reporting.py` renders `templates/weekly_email.html`; `services/email.py` sends via Gmail app password; `app/scheduler.py` registers Fri 5pm cron
- [ ] **Step 12 — Threshold alerts + privacy controls**: daily 6pm threshold check → `AlertLog`; "Clear spoof log" button; threshold config UI; reconfirm delete-student cascades work
- [ ] **Step 13 — Polish + demo rehearsal**: README polish; slide-deck outline in `docs/demo.md`; rehearsal checklist matching the demo plan in this file

---

## Demo plan (5 minutes — final capstone presentation)

1. **(15s) Roster** — `/students-page` shows 5 seeded students
2. **(60s) Live enrollment** — Click "+ Quick Enroll", type a volunteer's name; guided UI captures 5 angles; open `enrollment_data/` in File Explorer to show the frames; click "Print ID Card" → PDF opens on projector
3. **(15s) Normal check-in** — Volunteer holds card next to face; state machine transitions idle → "Verifying..." → green ✓ "Welcome, [Name]"
4. **(30s) "One at a time" guard** — Two volunteers step in frame; yellow overlay blocks the pipeline
5. **(45s) THE SPOOF ATTACK — centerpiece** — Phone with volunteer's photo + their card → red **"SPOOF DETECTED"**; `/spoof-log` shows the saved frame; repeat with printed photo
6. **(20s) Wrong-card defense** — Hold student A's card with own face → red "Face doesn't match"
7. **(60s) Dashboard tour** — Per-student filter, weekly bars, two students flagged below 80%
8. **(30s) Email demo** — Hit hidden `/admin/run-report` → Gmail on projector → email arrives live
9. **(60s) Limitations + Q&A** — Identical twins, 3D masks (out of scope); privacy controls; "what would I add next"

---

## Risks / gotchas (the things that will trip a 13-year-old)

1. **Python version** — must be 3.11, NOT 3.8 (which is EOL); use python.org installer or conda, NOT Microsoft Store
2. **First-run model downloads** — InsightFace `buffalo_l` (~280MB) + DeepFace antispoof + TensorFlow weights — looks frozen for 5–10 min on first server start
3. **NumPy 2.x** — pin `numpy<2`; transitive deps may otherwise pull 2.x and crash with `np.float_` AttributeError
4. **`getUserMedia` requires HTTPS** — except on `localhost`/`127.0.0.1`; never use the LAN IP
5. **OpenCV camera permission on Windows** — first `cv2.VideoCapture(0)` triggers a buried Settings → Privacy prompt; black frames = unanswered permission
6. **Gmail app password** — needs 2FA on the Google account + a generated app password (not the regular Gmail password)
7. **QR detection in low light** — `cv2.QRCodeDetector` struggles with small or poorly-lit QRs; printed card QR should be ≥3cm
8. **One face per frame** — reject when 2+ faces detected; "largest face" is too ambiguous to debug
9. **Embedding drift** — new haircut/glasses/hat can stop matches; provide per-student "Re-enroll" button

---

## How to continue from another machine

1. `git clone <repo-url>`
2. `cd attendance-tracker`
3. Follow setup in [../README.md](../README.md) — install Python 3.11 (or `conda create -n attendance python=3.11`)
4. `pip install -r requirements.txt`
5. `cp .env.example .env`; generate a `SECRET_KEY` (`python -c "import secrets; print(secrets.token_urlsafe(48))"`)
6. `python seed.py`
7. `python run.py` → open `http://localhost:8000`
8. Find the next unchecked step in **Implementation status** above and continue

This file is the single source of truth — update the checkboxes and the
relevant section whenever a step lands. Each step's section names the
exact files that should be created or modified.
