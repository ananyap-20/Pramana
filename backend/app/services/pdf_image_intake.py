"""Offline PDF/image extraction. Imported only inside the bounded worker."""

from __future__ import annotations

import csv
from contextlib import closing
import hashlib
import math
from pathlib import Path
import subprocess
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError, __version__ as pillow_version
import pypdfium2 as pdfium

from app.intake_models import ExtractedPage, ExtractionResult, IntakeLimits, TextRegion
from app.services.document_intake import DocumentIntakeError, DocumentIntakeTooLargeError


def _pixels(width: float, height: float, limits: IntakeLimits) -> int:
    if not all(math.isfinite(v) and v > 0 for v in (width, height)):
        raise DocumentIntakeError("The document contains invalid page dimensions.")
    count = math.ceil(width) * math.ceil(height)
    if count > limits.max_pixels:
        raise DocumentIntakeTooLargeError("A page or image exceeds the decoded-pixel limit.")
    return count


def _preview(image: Image.Image, path: Path) -> None:
    preview = image.copy()
    preview.thumbnail((1000, 1000))
    preview.convert("RGB").save(path, "PNG")
    preview.close()


def _ocr(image: Image.Image, workdir: Path, limits: IntakeLimits, executable: str,
         tessdata: str | None) -> tuple[str, tuple[TextRegion, ...], str]:
    image.save(workdir / "ocr.png", "PNG")
    command = [executable, str(workdir / "ocr.png"), str(workdir / "ocr"),
               "-l", "eng", "--oem", "1", "--psm", "3", "--dpi", str(limits.render_dpi)]
    if tessdata:
        command += ["--tessdata-dir", tessdata]
    command += ["tsv"]
    try:
        version = subprocess.run([executable, "--version"], capture_output=True,
                                 timeout=5, check=True).stdout.decode("utf-8", "replace").splitlines()[0]
        # Outer supervisor kills the entire process tree at the job deadline.
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=limits.timeout_seconds)
    except FileNotFoundError as error:
        raise DocumentIntakeError("OCR is unavailable. Install Tesseract and English language data, then retry.") from error
    except (OSError, subprocess.SubprocessError) as error:
        raise DocumentIntakeError("OCR could not finish. Check the runtime or retry with fewer pages.") from error
    output = workdir / "ocr.tsv"
    if result.returncode != 0 or not output.exists():
        raise DocumentIntakeError("OCR failed. Check Tesseract English language data and the image orientation.")
    if output.stat().st_size > limits.max_output_bytes:
        raise DocumentIntakeTooLargeError("OCR output exceeds the extraction safety limit.")
    parts: list[str] = []
    regions: list[TextRegion] = []
    length = 0
    previous = None
    with output.open(encoding="utf-8", errors="strict", newline="") as stream:
        for row in csv.DictReader(stream, delimiter="\t", quoting=csv.QUOTE_NONE):
            word = row.get("text", "")
            if row.get("level") != "5" or not word or not word.strip():
                continue
            line = tuple(row.get(key) for key in ("block_num", "par_num", "line_num"))
            separator = "" if previous is None else (" " if previous == line else "\n")
            parts.extend((separator, word))
            start = length + len(separator)
            length = start + len(word)
            if length > limits.max_characters or len(regions) >= limits.max_regions:
                raise DocumentIntakeTooLargeError("OCR text or region count exceeds the analysis limit.")
            confidence = float(row.get("conf") or -1)
            if not math.isfinite(confidence) or not 0 <= confidence <= 100:
                confidence = None
            left, top, width, height = (int(row[key]) for key in ("left", "top", "width", "height"))
            regions.append(TextRegion(start=start, end=length, bounds=(left, top, left + width, top + height),
                                      confidence=confidence))
            previous = line
    return "".join(parts), tuple(regions), version


def _usable(text: str) -> bool:
    return bool(text.strip()) and not any(
        char == "\ufffd" or char == "\x00" or (ord(char) < 32 and char not in "\r\n\t")
        for char in text
    )


def extract_pdf_image(path: Path, kind: str, workdir: Path, limits: IntakeLimits,
                      executable: str, tessdata: str | None) -> ExtractionResult:
    pages: list[ExtractedPage] = []
    tools = {"pypdfium2": str(pdfium.PYPDFIUM_INFO), "pdfium": str(pdfium.PDFIUM_INFO),
             "pillow": pillow_version}
    offset = 0
    total_pixels = 0
    total_regions = 0

    def add_page(number: int, image: Image.Image, text: str, method: str, width: float,
                 height: float, coordinates: str, rotation: int, notices: list[str]) -> None:
        nonlocal offset, total_regions
        if method == "ocr":
            text, regions, version = _ocr(image, workdir, limits, executable, tessdata)
            tools["tesseract"] = version
            notices.append("OCR transcription requires comparison with the preview; scores are not factual certainty.")
            if any(r.confidence is None or r.confidence < 80 for r in regions):
                notices.append("Some words have low or missing OCR confidence. Check and correct them.")
        else:
            regions = (TextRegion(start=0, end=len(text), bounds=(0, 0, width, height)),) if text else ()
        if not text.strip():
            notices.append("No readable text was recovered on this page. Enter visible text or confirm that it is blank.")
        if pages:
            offset += 2
        if offset + len(text) > limits.max_characters:
            raise DocumentIntakeTooLargeError("Extracted text exceeds the character limit; nothing was truncated.")
        total_regions += len(regions)
        if total_regions > limits.max_regions:
            raise DocumentIntakeTooLargeError("The document exceeds the extracted-region limit.")
        regions = tuple(r.model_copy(update={"start": offset + r.start, "end": offset + r.end}) for r in regions)
        pages.append(ExtractedPage(page=number, text=text, start=offset, end=offset + len(text),
                                   method=method, width=width, height=height, coordinates=coordinates,
                                   rotation=rotation, regions=regions, warnings=tuple(notices)))
        offset += len(text)
        _preview(image, workdir / f"page-{number}.png")

    try:
        if kind == "pdf":
            with pdfium.PdfDocument(path) as document:
                if pdfium.raw.FPDF_GetSecurityHandlerRevision(document) != -1:
                    raise DocumentIntakeError("Encrypted or password-protected PDFs are not supported.")
                if not 0 < len(document) <= limits.max_pages:
                    raise DocumentIntakeTooLargeError("The PDF is empty or exceeds the page limit.")
                for index in range(len(document)):
                    with closing(document[index]) as page:
                        width, height = page.get_size()
                        scale = limits.render_dpi / 72
                        total_pixels += _pixels(width * scale, height * scale, limits)
                        if total_pixels > limits.max_total_pixels:
                            raise DocumentIntakeTooLargeError("The PDF exceeds the total rendered-pixel limit.")
                        # Inspect image dimensions before rendering. Bound object traversal too.
                        has_images = False
                        for object_count, obj in enumerate(page.get_objects(max_depth=20), 1):
                            if object_count > 10_000:
                                raise DocumentIntakeTooLargeError("The PDF page contains too many objects.")
                            if obj.type == pdfium.raw.FPDF_PAGEOBJ_FORM and obj.level >= 20:
                                raise DocumentIntakeError("PDF form nesting is too deep to inspect safely.")
                            if obj.type == pdfium.raw.FPDF_PAGEOBJ_IMAGE:
                                has_images = True
                                total_pixels += _pixels(*obj.get_px_size(), limits)
                                if total_pixels > limits.max_total_pixels:
                                    raise DocumentIntakeTooLargeError("The PDF exceeds the total decoded/rendered-pixel limit.")
                        with closing(page.get_textpage()) as textpage:
                            if textpage.count_chars() > limits.max_characters:
                                raise DocumentIntakeTooLargeError("The PDF text layer exceeds the character limit.")
                            text = textpage.get_text_bounded(errors="replace").replace("\r\n", "\n")
                        notices = ["PDF text order is parser order. Verify columns, tables, symbols and completeness."]
                        method = "pdf_text" if _usable(text) and not has_images else "ocr"
                        if has_images:
                            notices.append("Raster content detected: whole-page OCR replaces the text layer to avoid duplicates and omitted image text.")
                        elif text.strip() and method == "ocr":
                            notices.append("The text layer looks damaged; OCR replaces it.")
                        with closing(page.render(scale=scale)) as bitmap:
                            image = bitmap.to_pil().copy()
                        try:
                            add_page(index + 1, image, text, method,
                                     width if method == "pdf_text" else image.width,
                                     height if method == "pdf_text" else image.height,
                                     "pdf_points_bottom_left" if method == "pdf_text" else "pixels_top_left",
                                     page.get_rotation(), notices)
                        finally:
                            image.close()
        else:
            Image.MAX_IMAGE_PIXELS = limits.max_pixels
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(path) as source:
                    expected = "PNG" if kind == "png" else "JPEG"
                    if source.format != expected or getattr(source, "n_frames", 1) != 1:
                        raise DocumentIntakeError("The image type does not match, or it is animated. Use a single PNG/JPEG.")
                    _pixels(*source.size, limits)
                    source.verify()
                with Image.open(path) as source:
                    source.load()
                    image = ImageOps.exif_transpose(source).convert("RGB")
                try:
                    if image.width * image.height > limits.max_total_pixels:
                        raise DocumentIntakeTooLargeError("The image exceeds the total decoded-pixel limit.")
                    add_page(1, image, "", "ocr", image.width, image.height, "pixels_top_left", 0,
                             ["EXIF orientation applied. Sideways text without orientation metadata must be rotated before upload."])
                finally:
                    image.close()
    except DocumentIntakeError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise DocumentIntakeTooLargeError("The image exceeds the decoded-pixel safety limit.") from error
    except pdfium.PdfiumError as error:
        raise DocumentIntakeError("The PDF cannot be read. Check that it is valid and not encrypted or password-protected.") from error
    except (UnidentifiedImageError, OSError, ValueError, KeyError, RuntimeError) as error:
        raise DocumentIntakeError("The file could not be safely extracted. Export a new PDF or upright PNG/JPEG and retry.") from error
    if not any(page.text.strip() for page in pages):
        raise DocumentIntakeError("No readable text was recovered. Use a clearer upright English document; no analysis was run.")
    if tessdata and (Path(tessdata) / "eng.traineddata").is_file():
        tools["eng.traineddata_sha256"] = hashlib.sha256((Path(tessdata) / "eng.traineddata").read_bytes()).hexdigest()
    return ExtractionResult(pages=tuple(pages), tools=tools,
                            settings={"language": "eng", "ocr_psm": 3, "ocr_oem": 1,
                                      "render_dpi": limits.render_dpi, "page_separator": "two newlines"},
                            warnings=("English, upright printed text only. Complex columns, tables, handwriting and mathematical notation are not reliably reconstructed.",))
