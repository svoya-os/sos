"""Job files: ``~/.local/state/svoya/jobs/<id>.json`` — what the bar shows as ``обучение 62%``.

Schema v1 (one file per job, written atomically; unknown keys must be ignored by readers)::

    {
      "v": 1,
      "id": "train-1832",               # [a-z0-9-]+, unique among live jobs
      "label": "обучение",              # short, lowercase, already localized
      "state": "running",               # running | done | failed | cancelled
      "progress": 0.62,                 # 0..1, or null while unknown
      "etaSec": 1080,                   # optional explicit ETA, valid at updatedAt
      "message": "эпоха 2/3",           # optional one-line detail
      "pid": 12345,                     # process that owns the job (liveness check)
      "command": ["uv", "run", "python", "train.py"],
      "cwd": "/home/me/ai/projects/tts-finetune",
      "startedAt": "2026-09-24T18:32:00Z",
      "updatedAt": "2026-09-24T18:50:00Z",
      "finishedAt": null,
      "exitCode": null
    }

Anyone may create a job file (a training script, Jackson, ``sos run``); ``sos status`` lists
running jobs whose pid is alive and derives ``etaSec`` from progress when the writer gave none.
Progress updates: ``sos job progress <id> <0..1> [--eta S] [--message ...]``.
"""
from __future__ import annotations

import datetime as dt
import os
import re
from pathlib import Path

from . import i18n
from .util import iso, parse_iso, pid_alive, read_json, slug, write_json

SCHEMA = 1
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

_LABELS = (
    (r"train|finetune|fine-tune|sft|lora|dpo|grpo", "training", "обучение"),
    (r"eval|bench", "evaluation", "оценка"),
    (r"infer|generate|gen|render|sample", "generation", "генерация"),
    (r"convert|quant|export|merge", "conversion", "конвертация"),
    (r"download|pull|fetch", "download", "загрузка"),
    (r"prep|preprocess|tokeni", "preparation", "подготовка"),
)


def default_label(script: str) -> str:
    stem = Path(script).stem.lower()
    for pat, en, ru in _LABELS:
        if re.search(pat, stem):
            return i18n.tr(en, ru)
    return stem


def job_path(jobs_dir: Path, job_id: str) -> Path:
    if not ID_RE.match(job_id):
        raise ValueError(f"invalid job id: {job_id!r}")
    return jobs_dir / f"{job_id}.json"


def new_id(jobs_dir: Path, base: str, now: dt.datetime) -> str:
    stem = slug(base)[:40]
    local = now.astimezone()
    cand = f"{stem}-{local:%H%M}"
    n = 2
    while (jobs_dir / f"{cand}.json").exists():
        cand = f"{stem}-{local:%H%M}-{n}"
        n += 1
    return cand


def create(jobs_dir: Path, *, label: str, command: list[str], cwd: str, pid: int,
           now: dt.datetime, base: str | None = None) -> dict:
    jobs_dir.mkdir(parents=True, exist_ok=True)
    job = {
        "v": SCHEMA,
        "id": new_id(jobs_dir, base or label, now),
        "label": label,
        "state": "running",
        "progress": None,
        "pid": pid,
        "command": command,
        "cwd": cwd,
        "startedAt": iso(now),
        "updatedAt": iso(now),
        "finishedAt": None,
        "exitCode": None,
    }
    write_json(job_path(jobs_dir, job["id"]), job)
    return job


def load(jobs_dir: Path, job_id: str) -> dict | None:
    return read_json(job_path(jobs_dir, job_id))


def update(jobs_dir: Path, job_id: str, now: dt.datetime, **fields) -> dict:
    path = job_path(jobs_dir, job_id)
    job = read_json(path)
    if not isinstance(job, dict):
        raise FileNotFoundError(job_id)
    if "progress" in fields and fields["progress"] is not None:
        p = float(fields["progress"])
        if not 0.0 <= p <= 1.0:
            raise ValueError("progress must be within 0..1")
        fields["progress"] = round(p, 4)
    job.update({k: v for k, v in fields.items() if v is not None or k in ("etaSec",)})
    job["updatedAt"] = iso(now)
    write_json(path, job)
    return job


def finish(jobs_dir: Path, job_id: str, now: dt.datetime, exit_code: int) -> dict:
    state = "done" if exit_code == 0 else ("cancelled" if exit_code in (130, -2, 143, -15) else "failed")
    fields = {"state": state, "exitCode": exit_code, "finishedAt": iso(now)}
    if state == "done":
        fields["progress"] = 1.0
    return update(jobs_dir, job_id, now, **fields)


def eta(job: dict, now: dt.datetime) -> int | None:
    """Explicit ``etaSec`` (aged since updatedAt), else linear extrapolation from progress."""
    upd = parse_iso(job.get("updatedAt"))
    if isinstance(job.get("etaSec"), (int, float)):
        age = (now - upd).total_seconds() if upd else 0
        return max(0, int(job["etaSec"] - age))
    p = job.get("progress")
    start = parse_iso(job.get("startedAt"))
    if isinstance(p, (int, float)) and 0.01 <= p < 1 and start and upd:
        elapsed = (upd - start).total_seconds()
        remaining = elapsed * (1 - p) / p - (now - upd).total_seconds()
        return max(0, int(remaining))
    return None


def running(jobs_dir: Path, now: dt.datetime, check_pid=pid_alive) -> list[dict]:
    """Running jobs, oldest first. Files whose owner died are reported as not running."""
    out: list[dict] = []
    try:
        files = sorted(jobs_dir.glob("*.json"))
    except OSError:
        return out
    for f in files:
        job = read_json(f)
        if not isinstance(job, dict) or job.get("state") != "running":
            continue
        pid = job.get("pid")
        if isinstance(pid, int) and not check_pid(pid):
            continue
        out.append(job)
    out.sort(key=lambda j: j.get("startedAt") or "")
    return out


def for_status(jobs_dir: Path, now: dt.datetime, check_pid=pid_alive) -> list[dict]:
    """The §4.2 shape: ``{"id","label","progress","etaSec"}``."""
    out = []
    for j in running(jobs_dir, now, check_pid):
        item = {"id": j.get("id"), "label": j.get("label")}
        if isinstance(j.get("progress"), (int, float)):
            item["progress"] = j["progress"]
        e = eta(j, now)
        if e is not None:
            item["etaSec"] = e
        out.append(item)
    return out


def cleanup(jobs_dir: Path, now: dt.datetime, keep_hours: int = 24, check_pid=pid_alive) -> int:
    """Delete finished (or orphaned) job files older than ``keep_hours``."""
    n = 0
    for f in jobs_dir.glob("*.json") if jobs_dir.is_dir() else []:
        job = read_json(f)
        if not isinstance(job, dict):
            continue
        t = parse_iso(job.get("finishedAt") or job.get("updatedAt"))
        orphan = job.get("state") == "running" and isinstance(job.get("pid"), int) and not check_pid(job["pid"])
        if (job.get("state") != "running" or orphan) and t and (now - t).total_seconds() > keep_hours * 3600:
            try:
                os.unlink(f)
                n += 1
            except OSError:
                pass
    return n
