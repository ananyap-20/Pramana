"""Bounded disposable processes, not a durable queue or a security sandbox."""

from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from threading import Event
import time

from app.intake_models import ExtractionResult, IntakeLimits
from app.services.document_intake import DocumentIntakeError, DocumentIntakeTooLargeError


class WindowsJob:
    """Kill descendants and cap their combined committed memory on Windows."""

    def __init__(self, process: subprocess.Popen, memory_mib: int) -> None:
        from ctypes import wintypes as w

        class Basic(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                        ("flags", w.DWORD), ("minimum", ctypes.c_size_t), ("maximum", ctypes.c_size_t),
                        ("active", w.DWORD), ("affinity", ctypes.c_size_t),
                        ("priority", w.DWORD), ("scheduling", w.DWORD)]

        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in
                        ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]

        class Extended(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", IO), ("process_memory", ctypes.c_size_t),
                        ("job_memory", ctypes.c_size_t), ("peak_process", ctypes.c_size_t),
                        ("peak_job", ctypes.c_size_t)]

        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = w.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        self.kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        self.kernel.CloseHandle.argtypes = [w.HANDLE]
        self.handle = self.kernel.CreateJobObjectW(None, None)
        limits = Extended()
        limits.basic.flags = 0x2000 | 0x200 | 0x8  # KILL_ON_JOB_CLOSE, JOB_MEMORY, ACTIVE_PROCESS
        limits.basic.active = 3
        limits.job_memory = memory_mib * 1024 * 1024
        if not self.handle or not self.kernel.SetInformationJobObject(
                self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)) or not self.kernel.AssignProcessToJobObject(
                self.handle, w.HANDLE(int(process._handle))):
            self.close()
            raise DocumentIntakeError("The Windows worker resource limits could not be established.")

    def close(self) -> None:
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def _stop(process: subprocess.Popen, job: WindowsJob | None) -> None:
    if job:
        job.close()
    elif os.name != "nt":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        process.kill()
    process.wait(timeout=5)


def run_extraction(content: bytes, kind: str, limits: IntakeLimits, executable: str,
                   tessdata: str | None, cancelled: Event, temp_root: str | None = None
                   ) -> tuple[ExtractionResult, dict[int, bytes]]:
    with tempfile.TemporaryDirectory(prefix="pramana-intake-", dir=temp_root) as directory:
        root = Path(directory)
        (root / "input").write_bytes(content)
        (root / "request.json").write_text(json.dumps({"kind": kind, "limits": limits.model_dump(),
                                                       "executable": executable, "tessdata": tessdata}), encoding="utf-8")
        # Inherit only runtime essentials, never cloud credentials or application secrets.
        env = {key: value for key, value in os.environ.items()
               if key.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "LANG", "LD_LIBRARY_PATH"}}
        env.update({"PYTHONPATH": str(Path(__file__).resolve().parents[2]),
                    "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1", "OMP_THREAD_LIMIT": "1",
                    "TEMP": directory, "TMP": directory, "TMPDIR": directory})
        process = subprocess.Popen([sys.executable, "-m", "app.services.intake_worker", directory],
                                   cwd=directory, env=env, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, start_new_session=os.name != "nt",
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        job = None
        started = time.monotonic()
        try:
            if os.name == "nt":
                job = WindowsJob(process, limits.memory_mib)
            # Worker waits for this byte before importing native parsers or starting descendants.
            process.stdin.write(b"1")
            process.stdin.close()
            while process.poll() is None:
                if cancelled.is_set():
                    raise DocumentIntakeError("Extraction cancelled; temporary files were removed.")
                if time.monotonic() - started > limits.timeout_seconds:
                    raise DocumentIntakeError("Extraction timed out. Use fewer pages or a smaller upright image.")
                for filename in ("result.json", "ocr.tsv"):
                    output = root / filename
                    if output.exists() and output.stat().st_size > limits.max_output_bytes:
                        raise DocumentIntakeTooLargeError("Worker output exceeds the extraction safety limit.")
                # Cap all temporary output, including rendered intermediates.
                if sum(p.stat().st_size for p in root.iterdir() if p.is_file()) > 96 * 1024 * 1024:
                    raise DocumentIntakeTooLargeError("Extraction exceeded its temporary-file limit.")
                cancelled.wait(0.03)
            output = root / "result.json"
            if not output.exists() or process.returncode != 0:
                raise DocumentIntakeError("The extraction worker stopped safely. The file may be malformed or exceed resource limits.")
            if output.stat().st_size > limits.max_output_bytes:
                raise DocumentIntakeTooLargeError("Worker output exceeds the extraction safety limit.")
            payload = json.loads(output.read_text(encoding="utf-8"))
            if "error" in payload:
                error_type = DocumentIntakeTooLargeError if payload.get("too_large") else DocumentIntakeError
                raise error_type(payload["error"])
            result = ExtractionResult.model_validate(payload)
            previews = {}
            for page in result.pages:
                preview = root / f"page-{page.page}.png"
                if preview.stat().st_size > 2 * 1024 * 1024:
                    raise DocumentIntakeTooLargeError("A page preview exceeds its safety limit.")
                previews[page.page] = preview.read_bytes()
            return result, previews
        finally:
            _stop(process, job)


def worker_limits(limits: IntakeLimits) -> None:
    if os.name != "nt":
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (limits.memory_mib * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_CPU, (max(1, int(limits.timeout_seconds)),) * 2)
        resource.setrlimit(resource.RLIMIT_FSIZE, (48 * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        os.umask(0o077)
