"""Disposable renderer entry point. Only application-owned measurement code executes."""
import json
import os
from pathlib import Path
import sys


def main():
    if sys.stdin.buffer.read(1) != b"1":
        return
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    if os.name != "nt":
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
        resource.setrlimit(resource.RLIMIT_FSIZE, (48 * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    from app.services.rendered_visual import analyze_rendered
    from app.services.visual_checks import VisualInputError
    from app.visual_models import VisualManifest, VisualRequest
    try:
        payload = json.loads(sys.stdin.buffer.read(1024 * 1024 + 1))
        result = analyze_rendered(VisualRequest.model_validate(payload["request"]), VisualManifest.model_validate(payload["manifest"]))
        output = result.model_dump_json()
        if len(output.encode("utf-8")) > 2 * 1024 * 1024:
            raise VisualInputError("Rendered results exceed the 2 MiB output limit.")
        print(output)
    except VisualInputError as error:
        print(json.dumps({"error": str(error), "status": 422}))
    except Exception:
        print(json.dumps({"error": "The isolated renderer is unavailable. Install the locked Playwright Chromium runtime and retry.", "status": 503}))


if __name__ == "__main__":
    main()
