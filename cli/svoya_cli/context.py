"""Ctx bundles everything a command touches — paths, runner, clock, env — so tests can fake it."""
from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping

from .paths import Paths
from .runner import Runner
from .util import utcnow


@dataclass
class Ctx:
    paths: Paths = field(default_factory=Paths)
    runner: Runner = field(default_factory=Runner)
    env: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))
    now: Callable[[], dt.datetime] = utcnow
    uid: int = field(default_factory=os.geteuid)
    dry_run: bool = False

    @property
    def is_root(self) -> bool:
        return self.uid == 0

    def sys(self, path: str) -> Path:
        return self.paths.sys(path)

    def read(self, path: str, default: str | None = None) -> str | None:
        """Read a system file (``/sys``, ``/proc``, ``/etc``) through the fake root when testing."""
        try:
            with open(self.sys(path), encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return default

    def exists(self, path: str) -> bool:
        return self.sys(path).exists()

    def target_user(self) -> tuple[int, str, Path]:
        """The human behind this run: PKEXEC_UID / SUDO_UID when elevated, else ourselves."""
        import pwd
        uid_s = self.env.get("PKEXEC_UID") or self.env.get("SUDO_UID")
        try:
            uid = int(uid_s) if uid_s else os.getuid()
            pw = pwd.getpwuid(uid)
            return uid, pw.pw_name, Path(pw.pw_dir)
        except (ValueError, KeyError):
            return os.getuid(), self.env.get("USER", "user"), self.paths.home


def make(dry_run: bool = False, echo: Callable[[str], None] | None = None) -> Ctx:
    return Ctx(runner=Runner(dry_run=dry_run, echo=echo), dry_run=dry_run)
