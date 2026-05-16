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
- [x] **Step 5 — Face enrollment v1**: `services/face.py` InsightFace wrapper (lazy load, embed, average, cosine, serialize)
- [x] **Step 6 — Quick Enroll v2**: 5-angle guided UI at `/enroll-page`; saves frames + `embedding.npy` + `metadata.json` to `enrollment_data/{code}_{name}/`; L2-normalized average embedding
- [x] **Step 7 — Signed QR ID cards**: HMAC-SHA256 in `services/qr.py`; `cv2.QRCodeDetector` decode-from-frame; `services/cards.py` renders 4-per-page PDF via `reportlab` + HTML preview to `id_cards/`
- [x] **Step 8 — Check-in pipeline**: single `POST /api/checkin/process` endpoint with cheap-then-expensive early returns (no_qr → invalid_qr → liveness → no_face/multi_face/spoof → embed → wrong_face → no_session/duplicate → ok); `static/checkin.html` polls every 800ms with state-machine overlay + 3-second cooldown lock + live feed
- [x] **Step 9 — Liveness**: DeepFace `anti_spoofing=True` in `services/liveness.py` (MiniFASNet, threshold from `LIVENESS_THRESHOLD`); spoof attempts save frame to `spoof_log/` + write `SpoofAttempt` row via `services/attendance.py::record_spoof_attempt`
- [~] **Step 10 — Dashboard (HALF-DONE — pick up here)**: Stats API endpoints written and wired in `routers/dashboard.py`, but the UI page `static/dashboard.html` is **not yet built**. See "Next-up handoff" below.
- [ ] **Step 11 — APScheduler + weekly Gmail report**: `services/reporting.py` renders `templates/weekly_email.html`; `services/email.py` sends via Gmail app password; `app/scheduler.py` registers Fri 5pm cron, started from FastAPI `lifespan` in `main.py`; manual trigger button `POST /admin/run-report`
- [ ] **Step 12 — Threshold alerts + privacy controls**: daily 6pm cron in scheduler — scan `per-student` stats, write `AlertLog` rows for any student below `MIN_ATTENDANCE_PCT`; "Clear spoof log" UI calls existing `POST /api/spoof-log/clear`; surface `MIN_ATTENDANCE_PCT` config in the dashboard
- [ ] **Step 13 — Polish + demo rehearsal**: README polish (mark Steps 5-13 as live in "What works today"); slide-deck outline in `docs/demo.md` (the demo plan above is the source); rehearsal checklist

## Next-up handoff (Step 10 — Dashboard UI)

### What's already in place
- `app/routers/dashboard.py` exposes these endpoints (all return JSON):
  - `GET /api/stats/overview?days=30` — header KPIs: total students, enrolled count + %, sessions in window, today's attendance count, class-wide attendance %, spoof count last 24h, min threshold
  - `GET /api/stats/per-student?days=30&flagged_only=false` — table data with `attendance_pct` and `flagged: bool`
  - `GET /api/stats/by-day?days=7` — list of `{date, attended, possible, pct}` for a bar chart
  - `GET /api/stats/recent-events?limit=20` — recent check-ins with student name + timestamp + confidence
  - `GET /api/spoof-log?limit=50` — list of spoof attempts; each has an `image_url`
  - `GET /api/spoof-log/{id}/image` — serves the saved JPEG frame
  - `POST /api/spoof-log/clear` — purges all spoof rows + their JPEGs
- Both `dashboard.router` and `dashboard.spoof_router` are already `include_router`'d in `app/main.py`.
- The other pages have a disabled "Dashboard" nav link (`data-disabled`); unset that when the page is live.

### What's left for Step 10
1. **Create `app/static/dashboard.html`** with sections in this order:
   - **Header KPIs** (4-tile grid) — pull from `/api/stats/overview`: total students, enrolled %, attended today, spoof 24h
   - **By-day bar chart** — Chart.js bar pulling `/api/stats/by-day?days=7`. Use the Chart.js CDN URL (no build tool needed).
   - **Per-student table** — pull `/api/stats/per-student?days=30`. Columns: code, name, attended/total, %, flag. Style flagged rows red. Add a text input that filters client-side by name and a "Flagged only" checkbox that re-fetches with `?flagged_only=true`.
   - **Recent check-ins feed** — pull `/api/stats/recent-events?limit=20`
   - **Spoof log viewer** — pull `/api/spoof-log`. Render thumbnails using `image_url`. Include a "Clear log" button that POSTs to `/api/spoof-log/clear`.
2. **Add the page route** in `app/main.py`:
   ```python
   @app.get("/dashboard-page", include_in_schema=False)
   def dashboard_page():
       return FileResponse(STATIC_DIR / "dashboard.html")
   ```
3. **Activate the nav link** — replace `<a href="#" data-disabled>Dashboard</a>` with `<a href="/dashboard-page">Dashboard</a>` in: `students.html`, `enroll.html`, `checkin.html`, `camera_test.html`.

### What hasn't been end-to-end tested on this machine
- **No webcam available** during this session, so the camera-driven paths (enrollment, check-in, liveness) were not actually run against real faces. Smoke-tested:
  - All endpoints import + register correctly
  - `/healthz`, `/api/students`, `/api/checkin/process` with a blank frame returns `no_qr` correctly
  - QR sign/verify round-trip
  - PDF + HTML card generation
- **InsightFace model has not been downloaded yet** — the buffalo_l weights (~280MB) lazy-load on first call to `face.embed_single_face()`. Expect a long pause on the first real enrollment.
- **DeepFace antispoof model** likewise loads on first call to `liveness.is_live()`.
- Worth a smoke test before the demo: enroll one student, check-in, hold up a phone photo of them, confirm `spoof` state lights up.

## Steps 11-13 sketch

### Step 11 — Scheduler + weekly email
- `app/services/email.py` — stdlib `smtplib` + `email.message.EmailMessage`; reads `SMTP_*` from settings; one function `send(subject, html_body, to_addr)`
- `app/services/reporting.py` — `weekly_report()` queries last 7 days of attendance, renders Jinja2 `app/templates/weekly_email.html`, calls `email.send(...)`. Flag students below `MIN_ATTENDANCE_PCT` in red.
- `app/scheduler.py` — APScheduler `BackgroundScheduler`; register two cron jobs:
  - `weekly_report` — Fridays 17:00 local
  - `daily_threshold_check` — 18:00 every day (Step 12)
- `app/main.py` lifespan — start scheduler on startup, shutdown on exit
- Add a hidden `POST /admin/run-report` endpoint for the demo so the email arrives on cue

### Step 12 — Threshold alerts + privacy controls
- Threshold cron writes one `AlertLog` row per below-threshold student per day (dedup on `(student_id, date)`)
- Dashboard already wires `POST /api/spoof-log/clear`; just expose the button
- Per-student "Re-enroll" button in the roster page (calls `POST /api/enroll` again)
- Settings UI to edit `min_attendance_pct` (read/write the `AttendanceThreshold` k/v row)

### Step 13 — Polish + demo docs
- README "What works today" section reflects Steps 5-13
- `docs/demo.md` — the demo plan from this PLAN, plus a rehearsal checklist
- Verification table from PLAN's "Verification" section as a literal pre-demo checklist

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
