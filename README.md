# Attendance Tracker

An open-source attendance system for a single classroom. Uses face recognition
with passive liveness detection to defeat photo spoofing, plus printed QR ID
cards for student identification. Runs locally on a teacher's laptop — no cloud,
no subscription.

**Capstone status:** in active development. See [docs/](docs) when present, or
the plan file in `~/.claude/plans/` for the full roadmap.

---

## What works today (Day 1)

- Roster CRUD: add, list, and delete students at `http://localhost:8000/students-page`
- Webcam pipeline sanity check at `http://localhost:8000/camera-test`
- SQLite database created automatically; seedable with 5 fake students

Still to come (in order): face enrollment, signed QR ID cards, two-stage
check-in pipeline, liveness detection, dashboard, weekly email reports.

---

## Setup (Windows or Mac)

### 1. Install Python 3.11

**Windows:** download the installer from
[python.org/downloads](https://www.python.org/downloads/) — pick **3.11.9**.
On the first installer screen, check **"Add python.exe to PATH"**.

> Do **not** use the Microsoft Store version of Python. It sandboxes
> user-site paths in ways that break several ML libraries.

**Mac:** `brew install python@3.11`

Verify:
```
python --version    # should print Python 3.11.x
```

### 2. Create a virtual environment

From the project root:

```
python -m venv .venv
```

Activate it:

- **Windows (PowerShell):** `.\.venv\Scripts\Activate.ps1`
- **Windows (cmd):** `.\.venv\Scripts\activate.bat`
- **Mac/Linux:** `source .venv/bin/activate`

Your shell prompt should now show `(.venv)` at the start.

### 3. Install dependencies

```
pip install --upgrade pip
pip install -r requirements.txt
```

This pulls down FastAPI, SQLAlchemy, OpenCV, InsightFace, DeepFace, and
TensorFlow. Expect ~5–10 minutes the first time. Total install size ~1.5GB.

> **Apple Silicon (M1/M2/M3) note:** before running `pip install`, edit
> `requirements.txt` and replace `deepface==0.0.93` + `tf-keras==2.17.0` with
> `tensorflow-macos==2.17.0`, `tensorflow-metal==1.1.0`, `deepface==0.0.93`.

### 4. Set up environment variables

```
cp .env.example .env
```

Then open `.env` in a text editor and set at least `SECRET_KEY`. You can
generate a strong key with:

```
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

(SMTP credentials are only needed once we get to weekly email reports — Step
11. Leave them as-is for now.)

### 5. Seed the database

```
python seed.py
```

You should see:
```
Seeded:
  5 students
  1 class sessions
Ready. Run: python run.py
```

### 6. Run the server

```
python run.py
```

Open [http://localhost:8000](http://localhost:8000) in your browser. You'll
land on the roster page with 5 seeded students.

> **Always use `localhost`, never the LAN IP.** Browsers require HTTPS for
> camera access *except* on `localhost` / `127.0.0.1`. If you visit via IP,
> the camera test page will silently fail to access the webcam.

---

## Project layout

```
attendance_tracker/
  app/
    main.py               FastAPI entry point
    config.py             environment + paths
    database.py           SQLAlchemy engine + session
    models.py             database tables
    schemas.py            request/response shapes
    routers/              one router per feature
    static/               HTML/CSS/JS — served as-is by FastAPI
  enrollment_data/        per-student capture frames (gitignored)
  id_cards/               generated printable PDF cards (gitignored)
  spoof_log/              rejected-spoof frames for teacher review (gitignored)
  requirements.txt
  .env.example            copy to .env and fill in
  run.py                  `python run.py` to start the server
  seed.py                 `python seed.py` to add 5 fake students
  attendance.db           SQLite — created automatically (gitignored)
```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'app'"

You're running `python run.py` from the wrong directory. `cd` into the
project root (the folder containing `run.py`).

### Camera test page shows "Camera error: Permission denied"

**Windows:** Settings → Privacy & security → Camera → make sure "Allow apps
to access your camera" is on and your browser is allowed.

**Mac:** System Settings → Privacy & Security → Camera → enable your
browser.

### `pip install` fails with cryptic errors about NumPy

Make sure you're on Python 3.11 (not 3.8 or 3.12). The dependencies pin
`numpy<2` because the ML libraries break on NumPy 2.x.

### First server start looks frozen

Once we add face recognition (Step 5), the first run will download the
InsightFace `buffalo_l` model (~280MB) to `~/.insightface/models/`, then
the DeepFace anti-spoof model (~50MB), then TensorFlow weights. This can
take 5–10 minutes on a slow connection. Watch the terminal — there is
progress, just no spinner in the browser.

---

## Privacy

This project stores face data. Even though it never leaves the laptop, a
school deploying this needs parental opt-in for biometric data.

- The database stores only **embeddings** (512-float vectors), never raw photos
- The `enrollment_data/` folder retains the 5 capture frames per student for
  troubleshooting; the teacher can delete the folder at any time
- The "Delete student" button removes the student, their embedding, and all
  related rows (cascading)
- Spoof attempts are logged with the frame so the teacher can investigate.
  A "Clear spoof log" button purges them

---

## License

MIT — see [LICENSE](LICENSE) when present.
