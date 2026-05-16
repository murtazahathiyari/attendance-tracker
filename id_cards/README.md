# id_cards/

Auto-generated printable QR ID cards live here, one PDF per enrolled
student (with an HTML preview alongside).

```
id_cards/
  S001_ava_patel.pdf      # 8.5×11 page, four cards per sheet for cutting
  S001_ava_patel.html     # browser preview
```

Each QR encodes the student's ID plus an HMAC signature, so a card cannot
be forged for a student who isn't enrolled in this system. Cards are
regenerated whenever a student is re-enrolled.

This folder is **gitignored**.
