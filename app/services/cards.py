"""Printable ID card generation — PDF (reportlab) + HTML preview (Jinja2)."""
from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.config import PROJECT_ROOT
from app.models import Student


TEMPLATES_DIR = PROJECT_ROOT / "app" / "templates"
_jinja = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


# Standard business-card size, 4 per US-letter sheet.
CARD_W = 3.5 * inch
CARD_H = 2.0 * inch
MARGIN_X = (letter[0] - 2 * CARD_W) / 2
MARGIN_Y = (letter[1] - 4 * CARD_H) / 2


def _draw_one_card(c: canvas.Canvas, x: float, y: float, student: Student, qr_reader: ImageReader) -> None:
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.setLineWidth(1)
    c.rect(x, y, CARD_W, CARD_H)

    # Header strip
    c.setFillColorRGB(0.15, 0.35, 0.85)
    c.rect(x, y + CARD_H - 0.35 * inch, CARD_W, 0.35 * inch, fill=1, stroke=0)

    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x + 0.15 * inch, y + CARD_H - 0.22 * inch, "Attendance Tracker")

    # Name
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x + 0.15 * inch, y + CARD_H - 0.65 * inch, f"{student.first_name} {student.last_name}")

    # Student code
    c.setFont("Helvetica", 10)
    c.setFillColorRGB(0.35, 0.35, 0.35)
    c.drawString(x + 0.15 * inch, y + CARD_H - 0.85 * inch, f"ID: {student.student_code}")

    # QR — bottom-right, ~1.1 inch square
    qr_size = 1.1 * inch
    c.drawImage(
        qr_reader,
        x + CARD_W - qr_size - 0.15 * inch,
        y + 0.15 * inch,
        width=qr_size,
        height=qr_size,
        mask="auto",
    )

    # Instruction text bottom-left
    c.setFont("Helvetica-Oblique", 7)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawString(x + 0.15 * inch, y + 0.4 * inch, "Hold next to face at check-in.")
    c.drawString(x + 0.15 * inch, y + 0.28 * inch, "Do not share. Re-enroll if lost.")


def write_card_pdf(path: Path, student: Student, qr_png: bytes) -> None:
    """Write a US-letter PDF containing 4 identical cards for cutting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    qr_reader = ImageReader(BytesIO(qr_png))

    c = canvas.Canvas(str(path), pagesize=letter)
    for row in range(4):
        for col in range(2):
            x = MARGIN_X + col * CARD_W
            y = letter[1] - MARGIN_Y - (row + 1) * CARD_H
            _draw_one_card(c, x, y, student, qr_reader)

    c.setFont("Helvetica-Oblique", 8)
    c.setFillColorRGB(0.6, 0.6, 0.6)
    c.drawCentredString(
        letter[0] / 2,
        MARGIN_Y / 2,
        f"Print, then cut along the borders. Generated for {student.student_code}.",
    )
    c.showPage()
    c.save()


def write_card_html(path: Path, student: Student, qr_png: bytes, token: str) -> None:
    """Write an HTML preview with the QR inlined as data-URI."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmpl = _jinja.get_template("card.html")
    html = tmpl.render(
        student=student,
        qr_data_uri="data:image/png;base64," + base64.b64encode(qr_png).decode(),
        token=token,
    )
    path.write_text(html, encoding="utf-8")
