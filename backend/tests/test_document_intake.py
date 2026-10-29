from io import BytesIO

from docx import Document
import pytest

from app.services.document_intake import (
    DocumentIntakeError,
    DocumentIntakeTooLargeError,
    extract_docx_bytes,
    validate_docx_upload,
)


def _docx_bytes(*paragraphs: str) -> bytes:
    document = Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def test_extracts_ordered_paragraphs_without_modifying_them() -> None:
    extracted = extract_docx_bytes(
        "draft.docx",
        _docx_bytes("First paragraph.", "Second paragraph."),
    )

    assert extracted.paragraph_count == 2
    assert extracted.text == "First paragraph.\nSecond paragraph."


def test_rejects_empty_docx() -> None:
    with pytest.raises(DocumentIntakeError, match="does not contain readable paragraph text"):
        extract_docx_bytes("empty.docx", _docx_bytes())


def test_rejects_malformed_document_content() -> None:
    with pytest.raises(DocumentIntakeError, match="not a valid"):
        extract_docx_bytes("broken.docx", b"not a zip document")


def test_rejects_unsupported_extension() -> None:
    with pytest.raises(DocumentIntakeError, match="Only .docx"):
        validate_docx_upload("draft.txt", b"not a docx")


def test_rejects_upload_over_compressed_size_limit() -> None:
    with pytest.raises(DocumentIntakeTooLargeError, match="5 MiB"):
        validate_docx_upload("large.docx", b"x" * (5 * 1024 * 1024 + 1))


def test_rejects_document_over_expanded_size_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.document_intake.MAX_UNCOMPRESSED_DOCX_BYTES", 1)

    with pytest.raises(DocumentIntakeTooLargeError, match="expanded document"):
        extract_docx_bytes("draft.docx", _docx_bytes("A paragraph."))


def test_rejects_document_over_extracted_text_limit() -> None:
    with pytest.raises(DocumentIntakeTooLargeError, match="100,000-character"):
        extract_docx_bytes("large.docx", _docx_bytes("x" * 100_001))


def test_accepts_case_insensitive_docx_extension() -> None:
    extracted = extract_docx_bytes("draft.DOCX", _docx_bytes("A draft."))
    assert extracted.text == "A draft."

