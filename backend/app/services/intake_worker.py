"""Disposable subprocess entry point. Never runs inside the API event loop."""

import json
from pathlib import Path
import sys

from app.intake_models import IntakeLimits
from app.services.document_intake import DocumentIntakeError, DocumentIntakeTooLargeError
from app.services.intake_process import worker_limits


def main() -> None:
    if sys.stdin.buffer.read(1) != b"1":
        return
    root = Path(sys.argv[1])
    request = json.loads((root / "request.json").read_text(encoding="utf-8"))
    limits = IntakeLimits.model_validate(request["limits"])
    worker_limits(limits)
    try:
        if request["kind"] == "docx":
            from dataclasses import asdict
            from app.services.document_intake import extract_docx_bytes
            output = json.dumps(asdict(extract_docx_bytes("draft.docx", (root / "input").read_bytes())))
        else:
            from app.services.pdf_image_intake import extract_pdf_image
            result = extract_pdf_image(root / "input", request["kind"], root, limits,
                                       request["executable"], request["tessdata"])
            output = result.model_dump_json()
        if len(output.encode("utf-8")) > limits.max_output_bytes:
            raise DocumentIntakeTooLargeError("The extraction output exceeds the safety limit.")
    except DocumentIntakeError as error:
        output = json.dumps({"error": str(error), "too_large": isinstance(error, DocumentIntakeTooLargeError)})
    except Exception:
        # Neither parser internals nor document contents are returned or logged.
        output = json.dumps({"error": "The file could not be safely extracted. Export a new PDF or image and retry."})
    (root / "result.json").write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
