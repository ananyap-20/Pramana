"""Run one bounded sweep of expired private originals using configured backend secrets."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.audit_api import AuditRuntime
from app.config import get_settings


def main():
    runtime = None
    try:
        runtime = AuditRuntime(get_settings(), None)
        if runtime.files is None:
            print("FAIL: authenticated MongoDB and Bunny settings are required.")
            return 1
        runtime.start()
        runtime.sweep_files()
        print("PASS: completed a bounded expired-file cleanup sweep.")
        return 0
    except Exception as error:
        print("FAIL: cleanup stopped (" + type(error).__name__ + "). References are retained for retry.")
        return 1
    finally:
        if runtime:
            runtime.close()


if __name__ == "__main__":
    raise SystemExit(main())
