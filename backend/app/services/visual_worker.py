"""Disposable static analyzer; input is data, never executable code."""

import sys
from pathlib import Path


def forbid_io(event, args):
    if event.startswith(("socket.", "subprocess.", "os.exec", "os.spawn")) or event in {"os.system", "open"}:
        raise PermissionError("External operations disabled.")


def main():
    if sys.stdin.buffer.read(1) != b"1":
        return
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from app.intake_models import IntakeLimits
    from app.services.intake_process import worker_limits
    worker_limits(IntakeLimits(memory_mib=256, timeout_seconds=5))
    import json
    from app.services.visual_checks import analyze_visual, VisualInputError
    from app.visual_models import VisualRequest, VisualManifest
    from PIL import Image
    Image.init()  # Complete Pillow's lazy plugin imports before denying file access.

    # Imports finish before sealing. Only in-memory parsing and byte buffers follow.
    sys.addaudithook(forbid_io)
    try:
        payload = json.loads(sys.stdin.buffer.read(1024 * 1024 + 1))
        result = analyze_visual(VisualRequest.model_validate(payload["request"]), VisualManifest.model_validate(payload["manifest"]))
        output = result.model_dump_json()
        if len(output.encode("utf-8")) > 2 * 1024 * 1024:
            raise VisualInputError("Visual results exceed the 2 MiB output limit.")
        print(output)
    except VisualInputError as error:
        print(json.dumps({"error": str(error)}))
    except Exception:
        print('{"error":"Static visual analysis could not complete safely."}')


if __name__ == "__main__":
    main()
