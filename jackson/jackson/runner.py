# SPDX-License-Identifier: Apache-2.0
"""All external commands go through a :class:`Runner` so tests can fake the OS."""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass
class RunResult:
    rc: int
    out: str = ""
    err: str = ""
    missing: bool = False
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.rc == 0 and not self.missing and not self.timed_out

    def why(self) -> str:
        if self.missing:
            return "command not found"
        if self.timed_out:
            return "timed out"
        return (self.err or self.out).strip().splitlines()[-1][:300] if (self.err or self.out).strip() \
            else f"exit code {self.rc}"


class Runner:
    """Thin wrapper around :mod:`subprocess` with timeouts and no shell."""

    def which(self, name: str) -> str | None:
        return shutil.which(name)

    def run(self, argv: Sequence[str], timeout: float = 5.0, env: Mapping[str, str] | None = None,
            cwd: str | None = None, input: str | None = None) -> RunResult:
        if not argv:
            return RunResult(127, missing=True)
        exe = argv[0] if os.path.isabs(argv[0]) else self.which(argv[0])
        if not exe:
            return RunResult(127, err=f"{argv[0]}: not found", missing=True)
        try:
            proc = subprocess.run(
                [exe, *argv[1:]], capture_output=True, text=True, timeout=timeout,
                env=dict(env) if env is not None else None, cwd=cwd, input=input,
                stdin=None if input is not None else subprocess.DEVNULL,
                errors="replace",
            )
        except subprocess.TimeoutExpired as exc:
            out = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", "replace")
            return RunResult(124, out=out, err="timeout", timed_out=True)
        except OSError as exc:
            return RunResult(126, err=str(exc), missing=isinstance(exc, FileNotFoundError))
        return RunResult(proc.returncode, proc.stdout, proc.stderr)

    def spawn(self, argv: Sequence[str], env: Mapping[str, str] | None = None,
              cwd: str | None = None) -> int | None:
        """Start a detached process (an application); returns its pid or None."""
        exe = argv[0] if os.path.isabs(argv[0]) else self.which(argv[0])
        if not exe:
            return None
        try:
            proc = subprocess.Popen(
                [exe, *argv[1:]], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, start_new_session=True, cwd=cwd,
                env=dict(env) if env is not None else None,
            )
        except OSError:
            return None
        # Reap the child when it exits so a long-running daemon never collects zombies.
        threading.Thread(target=proc.wait, name=f"reap-{proc.pid}", daemon=True).start()
        return proc.pid
