"""Small shared helpers: atomic writes, time, JSON files, TOML emit, slugs."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(t: dt.datetime | None) -> str | None:
    if t is None:
        return None
    return t.astimezone(dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    try:
        t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t


def atomic_write(path: str | os.PathLike, data: str | bytes, mode: int | None = None) -> None:
    """Write via temp file + rename so readers (the shell polls these) never see half a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data.encode("utf-8") if isinstance(data, str) else data)
        if mode is not None:
            os.chmod(tmp, mode)
        elif path.exists():
            os.chmod(tmp, path.stat().st_mode & 0o7777)
        else:
            os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_json(path: str | os.PathLike, default: Any = None) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path: str | os.PathLike, data: Any, mode: int | None = None) -> None:
    atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n", mode=mode)


def read_text(path: str | os.PathLike, default: str | None = None) -> str | None:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return default


def slug(s: str, fallback: str = "job") -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s or fallback


def version_key(v: str) -> tuple:
    """Sort key for kernel/package versions: ``6.17.0-10-generic`` > ``6.17.0-9-generic``."""
    parts = re.split(r"(\d+)", v)
    return tuple((0, int(p)) if p.isdigit() else (1, p) for p in parts if p)


# ---------------------------------------------------------------- TOML emit (tiny subset)

def _toml_key(k: str) -> str:
    return k if re.fullmatch(r"[A-Za-z0-9_-]+", k) else json.dumps(k, ensure_ascii=False)


def _toml_value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{_toml_key(k)} = {_toml_value(x)}" for k, x in v.items()) + " }"
    if v is None:
        raise ValueError("TOML has no null")
    raise TypeError(f"cannot encode {type(v).__name__} as TOML")


def toml_dumps(data: dict, comments: dict[str, str] | None = None) -> str:
    """Emit scalars first, then ``[tables]`` and ``[[arrays of tables]]`` (one level of nesting
    plus inline tables) — enough for svoya.toml, never for arbitrary documents."""
    comments = comments or {}
    lines: list[str] = []

    def emit_table(prefix: str, table: dict) -> None:
        scalars = {k: v for k, v in table.items()
                   if not isinstance(v, dict) and not (isinstance(v, list) and v and all(isinstance(x, dict) for x in v))}
        for k, v in scalars.items():
            if v is None:
                continue
            lines.append(f"{_toml_key(k)} = {_toml_value(v)}")
        for k, v in table.items():
            name = f"{prefix}.{_toml_key(k)}" if prefix else _toml_key(k)
            if isinstance(v, dict):
                lines.append("")
                if name in comments:
                    lines.append(f"# {comments[name]}")
                lines.append(f"[{name}]")
                emit_table(name, v)
            elif isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
                for item in v:
                    lines.append("")
                    lines.append(f"[[{name}]]")
                    for ik, iv in item.items():
                        if iv is None:
                            continue
                        lines.append(f"{_toml_key(ik)} = {_toml_value(iv)}")

    emit_table("", data)
    return "\n".join(lines).lstrip("\n") + "\n"


def pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
