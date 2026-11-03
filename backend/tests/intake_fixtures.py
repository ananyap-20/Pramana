"""Fictional printed fixtures; expected text is specified independently of parsers."""

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import reportlab
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pdfencrypt import StandardEncryption


PARAGRAPHS = (
    "Our dashboard helps the fictional LumaDesk team.",
    "Starter plan supports 50 team members.",
    "Features and pricing vary by plan.",
)
HELD_OUT = (
    ("Cedar studio reviews the release on Tuesday.", "The workspace contains twelve sample projects.",
     "Mira checks every heading before publication."),
    ("Northwind demo notes are ready for review.", "A clear sentence preserves the intended meaning.",
     "Please compare this page with the accepted text."),
    ("The sample campaign starts in November.", "Human reviewers keep control of the final decision.",
     "No original document is silently rewritten."),
)


def printed_image(paragraphs=PARAGRAPHS) -> Image.Image:
    image = Image.new("RGB", (1600, 1000), "white")
    font_path = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"
    font = ImageFont.truetype(str(font_path), 38)
    draw = ImageDraw.Draw(image)
    for index, text in enumerate(paragraphs):
        draw.text((75, 120 + index * 180), text, fill="black", font=font)
    return image


def image_bytes(kind="PNG", paragraphs=PARAGRAPHS) -> bytes:
    with printed_image(paragraphs) as image:
        output = BytesIO()
        image.save(output, kind)
        return output.getvalue()


def pdf_bytes(page_types=("text",), paragraphs=PARAGRAPHS, encrypted=False) -> bytes:
    output = BytesIO()
    pdf = Canvas(output, pagesize=(800, 500),
                 encrypt=StandardEncryption("secret", ownerPassword="owner") if encrypted else None)
    font_path = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"
    if "FixtureVera" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("FixtureVera", str(font_path)))
    for page_type in page_types:
        if page_type in ("text", "hybrid", "rotated"):
            pdf.setFont("FixtureVera", 16)
            for index, text in enumerate(paragraphs):
                pdf.drawString(38, 435 - index * 90, text)
            if page_type == "rotated":
                pdf.setPageRotation(90)
        if page_type in ("scan", "hybrid"):
            image_paragraphs = ("This raster note also needs transcription.",) if page_type == "hybrid" else paragraphs
            with printed_image(image_paragraphs) as image:
                if page_type == "hybrid":
                    pdf.drawImage(ImageReader(image), 38, 10, width=600, height=140)
                else:
                    pdf.drawImage(ImageReader(image), 0, 0, width=800, height=500)
        pdf.showPage()
    pdf.save()
    return output.getvalue()


def write_demo_fixtures(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    fixtures = {
        "text.pdf": pdf_bytes(("text", "text")),
        "scan.pdf": pdf_bytes(("scan",)),
        "mixed.pdf": pdf_bytes(("text", "scan", "hybrid")),
        "image.png": image_bytes(), "image.jpg": image_bytes("JPEG"),
        "encrypted.pdf": pdf_bytes(encrypted=True),
        "malformed.pdf": b"%PDF-1.7\nThis is not a PDF.",
    }
    for index, expected in enumerate(HELD_OUT, 1):
        fixtures[f"held-out-{index}.pdf"] = pdf_bytes(("text", "text"), expected)
    for name, content in fixtures.items():
        (directory / name).write_bytes(content)


if __name__ == "__main__":
    write_demo_fixtures(Path("tmp/intake-fixtures"))
