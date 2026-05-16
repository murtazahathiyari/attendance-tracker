# enrollment_data/

Each subfolder here contains the 5 capture frames + averaged embedding for
one enrolled student.

```
enrollment_data/
  S001_ava_patel/
    frame_01_straight.jpg
    frame_02_left.jpg
    frame_03_right.jpg
    frame_04_up.jpg
    frame_05_down.jpg
    embedding.npy
    metadata.json
```

This folder is **gitignored** — student biometric data should never be
committed to a public repo. Deleting a subfolder is safe; the database still
holds the embedding the system uses for matching. Re-enroll the student
through the dashboard if you want to regenerate these files.
