# SPDX-License-Identifier: Apache-2.0
"""bubblewrap sandbox for commands and MCP servers.

Layout inside the sandbox: the whole filesystem read-only, the project directory (and any
explicitly granted path) read-write, a private /tmp, no network unless granted, secrets
(ssh keys, keyrings, browser profiles, cloud credentials, Jackson's own state) hidden behind
empty tmpfs mounts, the user's runtime dir (D-Bus, Wayland, keyring sockets) hidden, and a
scrubbed environment.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Mapping, Sequence

from .paths import Paths
from .runner import Runner

# Relative to $HOME. Directories get an empty tmpfs, files get /dev/null.
SECRET_PATHS = (
    ".ssh", ".gnupg", ".local/share/keyrings", ".password-store", ".pki",
    ".mozilla", ".librewolf", ".thunderbird", ".config/google-chrome", ".config/chromium",
    ".config/BraveSoftware", ".config/vivaldi", ".config/microsoft-edge", ".config/opera",
    ".var/app/org.mozilla.firefox", ".var/app/com.google.Chrome", ".var/app/org.chromium.Chromium",
    ".var/app/com.brave.Browser", ".var/app/org.mozilla.Thunderbird",
    ".aws", ".azure", ".config/gcloud", ".kube", ".docker", ".config/gh", ".config/hub",
    ".config/svoya", ".local/share/svoya/jackson",
    ".netrc", ".git-credentials", ".pgpass", ".npmrc", ".pypirc", ".config/rclone",
)

ENV_ALLOW = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LANGUAGE", "TERM", "TZ", "SHELL", "COLORTERM")


def clean_env(source: Mapping[str, str] | None = None, extra: Mapping[str, str] | None = None) -> dict[str, str]:
    source = os.environ if source is None else source
    env = {k: v for k, v in source.items() if k in ENV_ALLOW or k.startswith("LC_")}
    env.setdefault("PATH", "/usr/local/bin:/usr/bin:/bin")
    if extra:
        env.update(extra)
    return env


class Sandbox:
    def __init__(self, paths: Paths, runner: Runner) -> None:
        self.paths = paths
        self.runner = runner
        self._probe: tuple[bool, str] | None = None
        self._lock = threading.Lock()

    def binary(self) -> str | None:
        return self.runner.which("bwrap")

    def probe(self) -> tuple[bool, str]:
        """Check that bwrap exists *and* can create namespaces here (cached)."""
        with self._lock:
            if self._probe is not None:
                return self._probe
            if not self.binary():
                self._probe = (False, "bwrap is not installed")
            else:
                res = self.runner.run(["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--unshare-all",
                                       "--die-with-parent", "true"], timeout=5.0)
                self._probe = (True, "ok") if res.ok else (False, f"bwrap cannot start: {res.why()}")
            return self._probe

    def available(self) -> bool:
        return self.probe()[0]

    def secret_paths(self) -> list[Path]:
        return [self.paths.home / rel for rel in SECRET_PATHS]

    def wrap(self, argv: Sequence[str], *, rw: Sequence[Path] = (), network: bool = False,
             cwd: Path | None = None) -> list[str]:
        args = ["bwrap", "--die-with-parent", "--new-session", "--unshare-all"]
        if network:
            args.append("--share-net")
        args += ["--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp"]
        if self.paths.runtime_base.is_dir():
            args += ["--tmpfs", str(self.paths.runtime_base)]
        hidden: list[Path] = []
        for p in self.secret_paths():
            if p.is_symlink():
                continue
            if p.is_dir():
                args += ["--tmpfs", str(p)]
                hidden.append(p)
            elif p.exists():
                args += ["--ro-bind", "/dev/null", str(p)]
                hidden.append(p)
        for path in rw:
            path = Path(path)
            if not path.exists() or any(path == h or h in path.parents for h in hidden):
                continue
            args += ["--bind", str(path), str(path)]
        if cwd is not None:
            args += ["--chdir", str(cwd)]
        return args + ["--", *argv]
