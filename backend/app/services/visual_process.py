"""Hard-deadline process boundary around passive parsing. Not an OS security sandbox."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from app.services.intake_process import WindowsJob, _stop
from app.visual_models import VisualManifest, VisualRequest, VisualResponse


class VisualProblem(ValueError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def run_visual(request: VisualRequest, manifest: VisualManifest, timeout: float | None = None) -> VisualResponse:
    rendered = request.mode == "rendered"
    timeout = timeout if timeout is not None else 30 if rendered else 5
    payload = json.dumps({"request": request.model_dump(mode="json"), "manifest": manifest.model_dump(mode="json")}).encode()
    if len(payload) > 1024 * 1024:
        raise VisualProblem(413, "Expanded visual request exceeds the worker input limit.")
    worker = Path(__file__).with_name("rendered_visual_worker.py" if rendered else "visual_worker.py")
    env = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR", "LANG", "PLAYWRIGHT_BROWSERS_PATH", "LOCALAPPDATA", "PATH"}}
    temporary = tempfile.TemporaryDirectory(prefix="pramana-visual-") if rendered else None
    if temporary:
        env.update(TEMP=temporary.name, TMP=temporary.name, TMPDIR=temporary.name)
    process = None
    job = None
    try:
        process = subprocess.Popen([sys.executable, "-I", "-B", "-X", "utf8", str(worker)],
            env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            start_new_session=os.name != "nt",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if os.name == "nt":
            job = WindowsJob(process, 1024, max_processes=16) if rendered else WindowsJob(process, 256)
        output, _ = process.communicate(b"1" + payload, timeout=timeout)
        if process.returncode != 0 or len(output) > 2 * 1024 * 1024:
            raise VisualProblem(422, "Static visual worker stopped safely or exceeded its output limit.")
        result = json.loads(output)
        if "error" in result:
            raise VisualProblem(result.get("status", 422), result["error"])
        return VisualResponse.model_validate(result)
    except subprocess.TimeoutExpired:
        raise VisualProblem(408, "Visual analysis timed out.") from None
    except VisualProblem:
        raise
    except Exception:
        raise VisualProblem(503, "Static visual worker is unavailable.") from None
    finally:
        if process:
            _stop(process, job)
            for stream in (process.stdin, process.stdout):
                if stream:
                    stream.close()
        if temporary:
            temporary.cleanup()
