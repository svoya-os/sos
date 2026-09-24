"""The one door to the outside world: every external command goes through a Runner.

* ``Runner``      — real subprocess calls with timeouts; never raises for a missing binary.
* ``dry_run``     — mutating calls (``mutating=True``) are printed and recorded, not executed;
                    read-only probes still run so the plan is accurate.
* ``FakeRunner``  — table-driven fake for tests (fixtures), records every call.

Commands are always argv lists (no shell strings), so nothing is ever interpreted by a shell
unless a caller explicitly runs ``bash script.sh``.
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping, Sequence, Union


@dataclass
class Result:
    rc: int
    out: str = ""
    err: str = ""

    @property
    def ok(self) -> bool:
        return self.rc == 0


NOT_FOUND = 127
TIMEOUT = 124


class Runner:
    def __init__(self, dry_run: bool = False, echo: Callable[[str], None] | None = None):
        self.dry_run = dry_run
        self.echo = echo
        self.planned: list[list[str]] = []   # mutating calls skipped by dry-run
        self.calls: list[list[str]] = []     # every call (for debugging/tests)

    # ---- discovery ----
    def which(self, name: str) -> str | None:
        return shutil.which(name)

    def has(self, name: str) -> bool:
        return self.which(name) is not None

    # ---- execution ----
    def run(self, argv: Sequence[str], *, timeout: float | None = 30, input: str | None = None,
            env: Mapping[str, str] | None = None, cwd: str | os.PathLike | None = None,
            mutating: bool = False) -> Result:
        argv = [str(a) for a in argv]
        self.calls.append(argv)
        if mutating and self.dry_run:
            self._plan(argv)
            return Result(0, "", "")
        try:
            p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, input=input,
                               env=dict(env) if env is not None else None, cwd=cwd,
                               errors="replace")
        except FileNotFoundError:
            return Result(NOT_FOUND, "", f"{argv[0]}: not found")
        except PermissionError as e:
            return Result(126, "", str(e))
        except subprocess.TimeoutExpired:
            return Result(TIMEOUT, "", f"{argv[0]}: timed out after {timeout}s")
        return Result(p.returncode, p.stdout or "", p.stderr or "")

    def stream(self, argv: Sequence[str], *, env: Mapping[str, str] | None = None,
               cwd: str | os.PathLike | None = None, mutating: bool = True) -> int:
        """Run with inherited stdio (long operations: apt, scripts). Returns the exit code."""
        argv = [str(a) for a in argv]
        self.calls.append(argv)
        if mutating and self.dry_run:
            self._plan(argv)
            return 0
        try:
            return subprocess.call(argv, env=dict(env) if env is not None else None, cwd=cwd)
        except FileNotFoundError:
            return NOT_FOUND

    def spawn(self, argv: Sequence[str], *, env: Mapping[str, str] | None = None,
              cwd: str | os.PathLike | None = None, mutating: bool = True) -> bool:
        """Start a detached process (new session, no stdio). Returns False if it could not start."""
        argv = [str(a) for a in argv]
        self.calls.append(argv)
        if mutating and self.dry_run:
            self._plan(argv)
            return True
        try:
            subprocess.Popen(argv, env=dict(env) if env is not None else None, cwd=cwd,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True)
            return True
        except OSError:
            return False

    def _plan(self, argv: list[str]) -> None:
        self.planned.append(argv)
        if self.echo:
            self.echo(shlex.join(argv))


Response = Union[Result, str, Callable[[list[str]], Result]]


@dataclass
class FakeRunner(Runner):
    """Deterministic runner for tests.

    ``responses`` maps a command prefix (string like ``"nvidia-smi --query-gpu"`` or a tuple) to a
    Result, a stdout string, or a callable. The longest matching prefix wins. Unknown commands
    return rc=127 (as if the binary were missing). ``available`` lists binaries ``which`` finds.
    """
    responses: dict = field(default_factory=dict)
    available: Iterable[str] = field(default_factory=set)
    dry_run: bool = False
    echo: Callable[[str], None] | None = None

    def __post_init__(self) -> None:
        self.planned = []
        self.calls = []
        self.streamed: list[list[str]] = []
        self.spawned: list[list[str]] = []
        self.available = set(self.available)
        self._table: list[tuple[list[str], Response]] = []
        for key, resp in self.responses.items():
            argv = list(key) if isinstance(key, tuple) else shlex.split(key)
            self._table.append((argv, resp))
        self._table.sort(key=lambda kv: -len(kv[0]))

    def which(self, name: str) -> str | None:
        if name in self.available:
            return f"/usr/bin/{name}"
        return None

    def _lookup(self, argv: list[str]) -> Result:
        for prefix, resp in self._table:
            if argv[: len(prefix)] == prefix:
                if callable(resp):
                    return resp(argv)
                if isinstance(resp, str):
                    return Result(0, resp, "")
                return resp
        return Result(NOT_FOUND, "", f"{argv[0]}: not found (fake)")

    def run(self, argv, *, timeout=30, input=None, env=None, cwd=None, mutating=False) -> Result:
        argv = [str(a) for a in argv]
        self.calls.append(argv)
        if mutating and self.dry_run:
            self._plan(argv)
            return Result(0, "", "")
        return self._lookup(argv)

    def stream(self, argv, *, env=None, cwd=None, mutating=True) -> int:
        argv = [str(a) for a in argv]
        self.calls.append(argv)
        self.streamed.append(argv)
        if mutating and self.dry_run:
            self._plan(argv)
            return 0
        return self._lookup(argv).rc

    def spawn(self, argv, *, env=None, cwd=None, mutating=True) -> bool:
        argv = [str(a) for a in argv]
        self.calls.append(argv)
        self.spawned.append(argv)
        if mutating and self.dry_run:
            self._plan(argv)
        return True

    def called(self, *prefix: str) -> bool:
        p = list(prefix)
        return any(c[: len(p)] == p for c in self.calls)


def as_root(argv: Sequence[str], is_root: bool | None = None) -> list[str]:
    """Prefix with pkexec when not root (polkit shows the exact program being run)."""
    if is_root is None:
        is_root = os.geteuid() == 0
    return list(argv) if is_root else ["pkexec", *argv]


def svoya_argv() -> list[str]:
    """How to re-invoke this very program (for pkexec re-exec and background refreshes)."""
    exe = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else ""
    if exe.endswith("/svoya") or os.path.basename(exe) == "svoya":
        return [exe]
    return [sys.executable, "-m", "svoya_cli"]
