"""Report progress to the SOS bar without extra dependencies.

`sos run` sets SVOYA_JOB_FILE; outside of it these calls do nothing.
    from {{ project.package }}.sos_progress import report
    report(0.25, "эпоха 1/4")
"""
import json
import os
import tempfile
import time


def report(progress: float, message: str | None = None, eta_sec: int | None = None) -> None:
    path = os.environ.get("SVOYA_JOB_FILE")
    if not path:
        return
    try:
        with open(path, encoding="utf-8") as f:
            job = json.load(f)
    except (OSError, ValueError):
        return
    job["progress"] = max(0.0, min(1.0, float(progress)))
    job["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if message is not None:
        job["message"] = message
    if eta_sec is not None:
        job["etaSec"] = int(eta_sec)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False)
    os.replace(tmp, path)
