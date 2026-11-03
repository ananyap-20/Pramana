"""Safe, ordinary-paragraph DOCX extraction for the Day 2 draft-intake API."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import zipfile
import zlib
from pathlib import PurePosixPath
from lxml import etree

from docx import Document
from docx.opc.exceptions import PackageNotFoundError


MAX_DOCX_BYTES = 5 * 1024 * 1024
MAX_UNCOMPRESSED_DOCX_BYTES = 20 * 1024 * 1024
MAX_DOCX_ENTRIES = 200
MAX_EXTRACTED_CHARACTERS = 100_000
ALLOWED_DOCX_EXTENSION = ".docx"


class DocumentIntakeError(ValueError):
    """A client-safe extraction error that never exposes document internals."""


class DocumentIntakeTooLargeError(DocumentIntakeError):
    """Raised when compressed, expanded, or extracted document content is too large."""


@dataclass(frozen=True)
class ExtractedDocument:
    text: str
    paragraph_count: int


def validate_docx_upload(filename: str | None, content: bytes) -> None:
    if not filename or len(filename) > 255 or any(ord(c) < 32 for c in filename) or PurePosixPath(filename.replace("\\", "/")).name != filename or not filename.lower().endswith(ALLOWED_DOCX_EXTENSION):
        raise DocumentIntakeError("Only .docx documents are supported.")
    if not content:
        raise DocumentIntakeError("The uploaded document is empty.")
    if len(content) > MAX_DOCX_BYTES:
        raise DocumentIntakeTooLargeError("The uploaded document exceeds the 5 MiB limit.")
    try:
        with zipfile.ZipFile(BytesIO(content)) as package:
            entries = package.infolist()
            names = [entry.filename for entry in entries]
            if (len(set(names)) != len(names) or any(entry.flag_bits & 1 or
                    ".." in PurePosixPath(entry.filename).parts or entry.filename.startswith(("/", "\\")) or
                    "vbaproject" in entry.filename.lower() or entry.filename.startswith("word/embeddings/")
                    for entry in entries)):
                raise DocumentIntakeError("Encrypted, embedded or macro-enabled DOCX features are unsupported.")
    except DocumentIntakeError:
        raise
    except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, ValueError) as error:
        raise DocumentIntakeError("The upload is not a valid .docx document.") from error

    if len(entries) > MAX_DOCX_ENTRIES:
        raise DocumentIntakeTooLargeError("The document contains too many archive entries.")
    if sum(entry.file_size for entry in entries) > MAX_UNCOMPRESSED_DOCX_BYTES:
        raise DocumentIntakeTooLargeError("The expanded document exceeds the 20 MiB safety limit.")
def extract_docx_bytes(filename: str | None, content: bytes) -> ExtractedDocument:
    """Extract ordered paragraph text without interpreting macros or instructions."""

    validate_docx_upload(filename, content)
    try:
        document = Document(BytesIO(content))
        paragraphs = tuple(paragraph.text for paragraph in document.paragraphs)
    except (
        etree.LxmlError,
        PackageNotFoundError,
        zipfile.BadZipFile,
        zlib.error,
        EOFError,
        OSError,
        RuntimeError,
        ValueError,
        KeyError,
        TypeError,
    ) as error:
        raise DocumentIntakeError("The .docx document could not be read.") from error

    text = "\n".join(paragraphs)
    if len(text) > MAX_EXTRACTED_CHARACTERS:
        raise DocumentIntakeTooLargeError(
            "The extracted document exceeds the 100,000-character analysis limit."
        )
    if "\x00" in text or any(0xD800 <= ord(c) <= 0xDFFF for c in text):
        raise DocumentIntakeError("The document does not contain valid Unicode text.")
    if not any(paragraph.strip() for paragraph in paragraphs):
        raise DocumentIntakeError("The .docx document does not contain readable paragraph text.")
    return ExtractedDocument(text=text, paragraph_count=len(paragraphs))



def validate_docx_media_type(mime: str | None) -> None:
    if mime not in (None, "", "application/octet-stream", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"):
        raise DocumentIntakeError("Only .docx documents with a matching declared file type are supported.")


def extract_docx_isolated(filename: str | None, content: bytes) -> ExtractedDocument:
    """Reuse the existing disposable worker's deadline, memory and output limits."""
    from threading import Event
    from app.intake_models import IntakeLimits
    from app.services.intake_process import run_extraction
    validate_docx_upload(filename, content)
    result, _ = run_extraction(content, "docx", IntakeLimits(), "", None, Event())
    return result
